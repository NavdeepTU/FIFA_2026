# Project Status

Last updated: 2026-07-30. Update this file whenever a task completes or scope changes —
it should always reflect what's actually working right now, not what's planned (that's
`project_scope.md`).

## Done and verified

### Data pipeline
- ETL (`etl/transform.py`, `etl/load.py`, `etl/schema.sql`) validated against the real
  54,600-row CSV: produces 48 teams, 1,248 players, 1,050 matches, full fact table.
  Unit-tested (`etl/tests/`, 5 tests) against a small synthetic CSV fixture.
- Confirmed the dataset is synthetic (players appear in far more matches than a real
  tournament allows; `total_*_tournament` columns are noisy, not true running totals) —
  documented in `ARCHITECTURE.md` §1 so this isn't rediscovered later.

### Backend (FastAPI)
- `/analytics/*`: standings, tournament progression, leaderboard (metric-parameterized,
  allowlisted), player profile, team profile, matches list.
- `/predict/*`: rating regressor, outcome classifier, archetype lookup + distribution,
  status check. All smoke-tested live against real trained artifacts.
- `/chat/status`, `/chat/retrieve`, `/chat/ask`: full RAG loop. `/retrieve` embeds the
  query with the same local model used to build `player_embeddings` and returns the
  nearest player summaries by pgvector distance; `/ask` does that same retrieval and
  then asks Groq to answer grounded only in the retrieved summaries. Smoke-tested live:
  asking "Who are the best goalkeepers based on saves and clean sheets?" returned an
  answer citing the exact save/clean-sheet counts from the retrieved players, correctly
  ranked, with no invented numbers.
- Structured JSON logging with per-request correlation IDs (`X-Request-ID`), a global
  exception handler with a consistent, non-leaky error shape, `/health` (liveness) vs
  `/health/ready` (checks Postgres connectivity). Groq calls additionally log
  model/prompt/completion/total token counts and latency per request (`app.genai`
  logger) — the raw material for a future token-usage dashboard.
- 39 pytest tests (`backend/tests/`), DB and model layers mocked — unit tests, not
  integration tests against a real Postgres (that's a Phase 4/CI concern).
- ruff-clean (`pyproject.toml` at repo root, `make lint`).

### ML (Phase 2)
- Checked for target leakage before building anything: `tournament_rating`,
  `performance_score`, `distance_covered_km`, `sprint_distance_km` all correlate
  0.83-0.997 with `player_rating` — excluded from every model's inputs.
- **Rating regressor** (XGBoost): R²=0.22, MAE=0.52 on held-out test data.
- **Outcome classifier** (XGBoost, W/D/L): 40% accuracy (3-class, near-chance) —
  documented honestly rather than dressed up.
- **Archetype clustering** (KMeans, k=4 via silhouette selection): recovered football
  positions almost exactly from per-90 stats alone, unsupervised.
- Artifacts committed to `backend/ml/artifacts/` (~1.7MB) so a fresh clone works
  without retraining. Retrain via `make ml-train`.
- Unit-tested (`backend/tests/test_predict.py`) with mocked model objects.

### Frontend (Next.js 16)
- Pages: overview (`/`), player leaderboard + profile (`/players`, `/players/[id]`),
  team standings + profile (`/teams`, `/teams/[team]`), live rating predictor (`/predict`),
  chat assistant (`/chat`).
- Chat page: chat-bubble UI (user messages right-aligned, assistant answers left with
  source player chips underneath), example prompt suggestions for an empty chat,
  animated "thinking" indicator while waiting on Groq, calls `POST /chat/ask`.
- Charts styled to the `dataviz` skill's validated palette (light/dark, CSS custom
  properties by role).
- Verified: type-checks clean, builds clean, renders correctly with a graceful
  "API unreachable" fallback when the backend isn't running (checked on both `/predict`
  and `/chat`), and end-to-end against a live local backend — including a real
  grounded chat answer rendered in the browser with matching source players shown.

### GenAI (Phase 3, in progress)
- **Embeddings**: `backend/genai/generate_embeddings.py` populates `player_embeddings`
  (pgvector): reads `mv_player_tournament_stats`, builds a natural-language summary per
  player (`backend/genai/embeddings.py`), embeds it locally via `fastembed`
  (`BAAI/bge-small-en-v1.5`, ONNX, 384-dim — matches the column's declared dimension),
  and upserts. Local/offline rather than a hosted API: Groq (the project's LLM
  provider) has no embeddings endpoint, and this avoids a second API dependency just
  for retrieval. Idempotent — re-run via `make genai-embed` after every ETL load.
  Verified against the real dataset: all 1248 players embedded; a pgvector similarity
  query for "a goalkeeper who makes a lot of saves and keeps clean sheets" returned
  only goalkeepers as nearest neighbors, confirming the embeddings are semantically
  meaningful and not just populated.
- **Team embeddings** (extends the above): `backend/genai/generate_team_embeddings.py`
  populates a new `team_embeddings` table the same way, from a new
  `mv_team_tournament_stats` materialized view (box-score aggregates by team — tackles,
  interceptions, clearances, saves, clean sheets — joined with the existing
  `mv_team_standings` for W/D/L/points) via `build_team_summary_text()`. Closes a gap
  that existed since Phase 3 first shipped: `player_embeddings` was player-only, so a
  question like "which team had the best defense?" had nothing to retrieve against.
  Idempotent, re-run via `make genai-embed-teams` after every ETL load. Verified: all
  48 teams embedded; asking "which team has the best defense based on tackles and
  clean sheets?" returned only team results (Canada correctly ranked first on both
  metrics — 1014 tackles, 15 clean sheets), and a deliberately mixed query ("tell me
  about France, the team and their players") returned a genuine mix of one team result
  and several player results — confirming retrieval ranks by similarity across both
  entity types in one list rather than needing separate buckets or manual routing.
- **Retrieval**: `POST /chat/retrieve` embeds an incoming natural-language query with
  the same model and returns the nearest player **and team** summaries together, one
  ranked list (`app/routers/chat.py`, `_retrieve_similar_entities` — a `union all`
  over both embedding tables). `fastembed` is now a serving-time dependency, not just
  an offline-script one — added to `backend/requirements.txt` accordingly. Response
  shape changed to `entity_type`/`entity_id`/`name`/`team`/`position` (nullable for
  teams) to represent both kinds of result — frontend (`lib/api.ts`, `/chat` page)
  updated to match, chip rendering shows "· Team" for team sources.
- **Generation**: `POST /chat/ask` retrieves via the same path, then calls Groq
  (`llama-3.3-70b-versatile`) with a system prompt constraining it to answer only from
  the retrieved player/team summaries (`backend/genai/llm.py`, `generate_answer()`) —
  not free-form guessing. Built behind a provider-agnostic function signature so
  swapping providers later means writing one new function, not touching the router.
  Token usage and latency logged per call. Requires `GROQ_API_KEY` in `backend/.env`
  (`/chat/status` reports whether it's set); without it, `/ask` returns 503 rather than
  failing opaquely.
- **Rate limiting**: `backend/app/rate_limit.py` — a small hand-rolled, in-memory,
  per-client-IP limiter (20 requests / 60 seconds, shared across `/chat/retrieve` and
  `/chat/ask`), applied as a FastAPI dependency. No new package — same "the payoff for
  one more dependency isn't there yet" call already made for structured logging.
  In-memory only, so it resets on restart and doesn't coordinate across multiple API
  processes — fine for the single-instance Container Apps deployment this project
  targets; a real multi-instance deployment would need a shared store (Redis) instead.
  Returns `429` with a `Retry-After` header once the limit is hit. `/chat/status` now
  reports the configured limit. Verified live: the 21st request within a minute got
  `429` with `retry-after: 50`, requests 1-20 all succeeded.
- Unit-tested: `backend/tests/test_genai_embeddings.py` (pure summary-text builders,
  player and team), `backend/tests/test_chat.py` (retrieval — including a mixed
  player+team result set, generation, and rate limiting — all with the Groq/embedding
  calls mocked; the rate limiter's state is reset between tests via an autouse fixture
  in `conftest.py` so tests don't trip each other's limits).
- **While building the embeddings step earlier**, found and fixed a pre-existing bug in
  `etl/load.py`'s `apply_schema()`: naive `;`-splitting treated the comment block
  immediately before `create table player_embeddings` as making the whole statement
  comment-only, so the table was silently never created on any fresh load despite
  `load.py` reporting success. Fixed (`split_sql_statements`) and regression-tested
  (`etl/tests/test_load.py`).
- **Auto-generated, cached scouting reports**: `POST /reports/players/{id}`
  (`backend/app/routers/reports.py`) generates a 3-4 paragraph scouting report via
  Groq — playing style/strengths, weaknesses, a notable recent performance — grounded
  in the player's real season summary (`build_summary_text()`, reused from the
  embeddings pipeline) plus their 5 most recent matches for form/narrative color.
  Cached in a new `player_reports` table (`etl/schema.sql`); `GET
  /reports/players/{id}` returns the cached version (404 if none yet) without
  spending a Groq call. `generate_player_report()` (`backend/genai/llm.py`) shares the
  Groq client/logging helper `generate_answer()` uses, refactored into a common
  `_complete()` so both go through the same token-usage logging. Shares the same
  rate limiter as `/chat/*` (same cost-protection budget). Frontend:
  `ScoutingReport.tsx`, embedded on the player profile page — shows a "Generate
  report" button when none exists, "Regenerate" once one does, with a loading state
  while Groq responds. Verified live end-to-end, two players: a fresh player showed
  the empty state, generated a report citing exact stats (goals, xG, tackles, a
  specific recent match with rating), and cached it (confirmed via a second request
  returning instantly with the same timestamp, no new Groq call); a player with an
  existing report loaded it immediately on page visit. Schema pushed to the deployed
  Azure Postgres too (`player_reports` table now exists there — empty, as expected,
  since reports generate on demand rather than in bulk); the CASCADE-wipe re-ran
  `etl/load.py` triggered again on `player_embeddings`/`team_embeddings` as documented
  above, both regenerated against Azure and reverified (1248 players, 48 teams).
- **Team scouting reports** (extends the above): `POST`/`GET /reports/teams/{team}`
  mirror the player endpoints exactly — `build_team_summary_text()` (reused from team
  embeddings) plus the team's 5 most recent matches (a `case when team_a = :team ...`
  query over `matches` giving a team-centric opponent/goals-for/goals-against view,
  since `matches` itself has no single "this team's perspective" column the way
  `player_match_stats` does), cached in a new `team_reports` table.
  `generate_team_report()` (`backend/genai/llm.py`) is a second thin wrapper around
  the shared `_complete()` helper, with its own team-focused system prompt. Frontend:
  `ScoutingReport.tsx` generalized to take `kind: "player" | "team"` + `id` instead of
  a player-specific prop (it only ever rendered `report_text`/`generated_at`, so no
  business logic needed duplicating — just which fetch/generate functions to call),
  embedded on the team profile page the same way. Verified live: generated a report
  for Brazil citing exact numbers (947 tackles, 761 interceptions, 53 goals conceded
  in 45 matches, specific match results "2-0 win over the Netherlands", "1-3 loss to
  Italy"), confirmed cached on a second request (13ms, same timestamp); player page
  re-verified for regressions after the shared-component refactor — none. Schema
  pushed to the deployed Azure Postgres too (`team_reports` table now exists there —
  empty, as expected); the CASCADE-wipe fired again on `player_embeddings`/
  `team_embeddings` as documented, both regenerated against Azure and reverified
  (1248 players, 48 teams).
- Not done yet: natural-language → chart, auto-generated match recaps (the last
  remaining "scouting reports / match recaps" item — match-level rather than
  player/team-level, would need a per-match cache key and likely a frontend matches
  page, which doesn't exist yet) — see "Not started yet" below.

### Infrastructure (Terraform, azurerm) — APPLIED, real resources live in Azure
- All 23 planned resources exist and are `Succeeded`: resource group (`rg-fifa26-dev`),
  Postgres Flexible Server, storage account + 3 containers, Key Vault + 2 secrets,
  Container Apps environment + 2 apps (API, Grafana), Log Analytics, Application
  Insights, managed identity + 2 role assignments, and the $10/month budget alert
  (navdeep98.sharma@gmail.com). Verified live via `az resource list -g rg-fifa26-dev`.
- Local tooling: Azure CLI + Terraform installed via `brew`/`hashicorp/tap` (disk
  constraint eased, see `CLAUDE.md`). Remote state lives in a separate bootstrap
  resource group (`rg-fifa-tfstate`, storage account `fifatfstatend26`, container
  `tfstate`) so a laptop and future CI share the same state — backend config is
  uncommented in `infra/versions.tf`.
- **Postgres is in `eastus2`, everything else in `eastus`** (`var.postgres_location`,
  `infra/variables.tf`) — not the original design. Azure rejected the first Postgres
  create attempt with `LocationIsOfferRestricted`: brand-new subscriptions are blocked
  from provisioning Postgres Flexible Server in some high-demand regions (`eastus`
  included) until the subscription has some usage history. Everything else provisioned
  in `eastus` without issue, so only the database moved rather than the whole stack.
- **Two secrets pre-generated, not user-supplied**: a random Postgres admin password
  (`openssl rand`, stored in `infra/.env.secrets`, gitignored) and the existing
  `GROQ_API_KEY` from `backend/.env`, both fed to Terraform via `TF_VAR_*` env vars
  rather than the tracked `terraform.tfvars` file, and both landed in Key Vault as the
  real secret store — never committed to git.
- **What's still placeholder**: the `api` Container App is running Microsoft's
  `containerapps-helloworld` image, not the project's actual FastAPI code — building
  and pushing a real image is Phase 4 (CI/CD) work, not done yet. The database is live
  but empty — the ETL hasn't been pointed at it yet. Both are natural next tasks.
- **Provisioning was rocky and is worth documenting honestly**: the very first
  `terraform plan` hung for 3.5+ hours (not actually frozen, just an unrelated Azure
  resource provider — `Microsoft.DataMigration`, never used by this project — stuck
  retrying its own auto-registration). Fixed by setting
  `resource_provider_registrations = "none"` in the `azurerm` provider block
  (`infra/versions.tf`) and relying on the providers already registered manually via
  `az provider register`. Several stale Terraform state locks came from having to
  force-kill that hang before the root cause was found — cleared via
  `terraform force-unlock`. One `azurerm_container_app_environment` and (briefly) one
  `azurerm_postgresql_flexible_server` ended up existing in Azure without being in
  Terraform's state (created successfully server-side, but the client lost track —
  once from an interrupted poll, once from an expired `az login` token mid-poll) —
  both recovered with `terraform import` rather than destroying and recreating.
- **Deployed database is populated**: ran `etl/load.py` and
  `backend/genai/generate_embeddings.py` directly against the real Azure Postgres
  Flexible Server (connecting from a laptop across the `allow-dev-ip` firewall rule).
  Verified via row counts matching the local dataset exactly: 48 teams, 1248 players,
  1050 matches, 54600 stat rows, 1248 embeddings. The embeddings step hit a genuine
  transient network stall on the first attempt (confirmed server-side via
  `pg_stat_activity` — the connection was `idle in transaction` waiting on
  `ClientRead` for several minutes on one row, not a slow-but-progressing case like
  the earlier Terraform hangs) and succeeded cleanly on a straight retry — worth
  knowing this can happen on a single-row-per-round-trip upsert to a database that's
  geographically distant from the client, and that checking `pg_stat_activity` is the
  fast way to tell "stalled" from "just slow" server-side.
- **Team-embeddings schema pushed to the deployed database too**: re-ran `etl/load.py`
  against Azure (adds `team_embeddings` + `mv_team_tournament_stats`), then both
  `generate_embeddings.py` and `generate_team_embeddings.py`. Verified: 48 teams, 1248
  players, 1050 matches, 54600 stat rows, 1248 player embeddings, 48 team embeddings —
  all present on the real deployed Postgres. **Found a real bug in the process**:
  re-running `etl/load.py` had silently wiped `player_embeddings` back to 0 (confirmed
  before regenerating) — `load_tables()`'s `truncate table ... cascade` cascades into
  *any* table with a foreign key into `players`/`teams`, which includes both embeddings
  tables, not just the four tables the ETL manages directly. This means **every** ETL
  re-run wipes both embeddings tables, not just the very first one — previously
  undocumented. Fixed by making it visible rather than silent: `load.py` now prints an
  explicit reminder at the end of every run to regenerate embeddings, and
  `load_tables()` has a comment explaining why. The underlying behavior (cascade wipes
  embeddings) is unchanged — this is a workflow-visibility fix, not a schema redesign;
  a `make etl-run` that preserves embeddings across reruns would need a different reload
  strategy (diff/upsert instead of truncate) and wasn't in scope tonight.

### Docs / process
- `docs/ARCHITECTURE.md` — living system reference.
- `docs/project_scope.md` — full target feature set.
- This file.
- Root `CLAUDE.md` — working agreement (50-60 min task sizing, disk-space discipline,
  conventions).

## Not started yet

- **Phase 3 (GenAI)**: embeddings (player and team), retrieval, grounded generation,
  rate limiting, auto-generated/cached scouting reports (player and team), and a
  frontend chat UI are all built (see above) — the core RAG feature works end-to-end,
  backend and frontend, answers both player- and team-level questions, with a real
  usage safety net. Still unbuilt: natural-language → chart, auto-generated match
  recaps (the one remaining "reports" item — match-level, not player/team-level).
- **Phase 4 (observability/CI/CD)**: GitHub Actions workflows, building/pushing a real
  Docker image for the API (Container App currently runs a placeholder hello-world
  image — the database behind it is populated and ready, but nothing is actually
  serving it yet), Azure Monitor/App Insights wiring (env var is already passed to the
  container, just unused), Grafana dashboards, Sentry, load testing.

## Known limitations / honest caveats

- The dataset's match outcomes and tournament totals are close to random — this is
  called out rather than hidden, and shapes what claims the ML section can honestly make.
- No integration tests against a real Postgres yet (only mocked-DB unit tests).
- No authentication anywhere (out of scope — see `project_scope.md`).
