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
- 24 pytest tests (`backend/tests/`), DB and model layers mocked — unit tests, not
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
- **Retrieval**: `POST /chat/retrieve` embeds an incoming natural-language query with
  the same model and returns the nearest player summaries (`app/routers/chat.py`).
  `fastembed` is now a serving-time dependency, not just an offline-script one — added
  to `backend/requirements.txt` accordingly.
- **Generation**: `POST /chat/ask` retrieves via the same path, then calls Groq
  (`llama-3.3-70b-versatile`) with a system prompt constraining it to answer only from
  the retrieved player summaries (`backend/genai/llm.py`, `generate_answer()`) — not
  free-form guessing. Built behind a provider-agnostic function signature so swapping
  providers later means writing one new function, not touching the router. Token usage
  and latency logged per call. Requires `GROQ_API_KEY` in `backend/.env`
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
- Unit-tested: `backend/tests/test_genai_embeddings.py` (pure summary-text builder),
  `backend/tests/test_chat.py` (retrieval, generation, and rate limiting — all with the
  Groq/embedding calls mocked; the rate limiter's state is reset between tests via an
  autouse fixture in `conftest.py` so tests don't trip each other's limits).
- **While building the embeddings step earlier**, found and fixed a pre-existing bug in
  `etl/load.py`'s `apply_schema()`: naive `;`-splitting treated the comment block
  immediately before `create table player_embeddings` as making the whole statement
  comment-only, so the table was silently never created on any fresh load despite
  `load.py` reporting success. Fixed (`split_sql_statements`) and regression-tested
  (`etl/tests/test_load.py`).
- Not done yet: NL→chart and auto-generated/cached reports — see "Not started yet"
  below.

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

### Docs / process
- `docs/ARCHITECTURE.md` — living system reference.
- `docs/project_scope.md` — full target feature set.
- This file.
- Root `CLAUDE.md` — working agreement (50-60 min task sizing, disk-space discipline,
  conventions).

## Not started yet

- **Phase 3 (GenAI)**: embeddings, retrieval, grounded generation, rate limiting, and a
  frontend chat UI are all built (see above) — the core RAG feature works end-to-end,
  backend and frontend, with a real usage safety net. Still unbuilt: natural-language →
  chart, auto-generated/cached reports, and team-level summaries (`player_embeddings`
  is player-only; a question like "which team had the best defense?" has no team
  embeddings to retrieve against yet).
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
