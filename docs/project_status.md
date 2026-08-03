# Project Status

Last updated: 2026-08-03 (match recaps deployed and verified live on Azure;
Sentry error tracking added for both backend and frontend, deployed, and
verified live against real production infrastructure — confirmed via a real
triggered error on the actual deployed API and the actual deployed frontend
site, not just locally). Update this file whenever a task completes or scope
changes — it should always reflect what's actually working right now, not
what's planned (that's `project_scope.md`).

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
  team standings + profile (`/teams`, `/teams/[team]`), match list + detail
  (`/matches`, `/matches/[id]`), live rating predictor (`/predict`), chat assistant
  (`/chat`), natural-language chart builder (`/charts`).
- Chat page: chat-bubble UI (user messages right-aligned, assistant answers left with
  source player chips underneath), example prompt suggestions for an empty chat,
  animated "thinking" indicator while waiting on Groq, calls `POST /chat/ask`.
- Charts styled to the `dataviz` skill's validated palette (light/dark, CSS custom
  properties by role).
- Verified: type-checks clean, builds clean, renders correctly with a graceful
  "API unreachable" fallback when the backend isn't running (checked on both `/predict`
  and `/chat`), and end-to-end against a live local backend — including a real
  grounded chat answer rendered in the browser with matching source players shown.
- **Deployed to Azure as a static export** (see "Frontend deployment" below) — live at
  https://stfifa266q3jm1.z13.web.core.windows.net/.

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
- **Natural-language → chart** (`POST /charts/ask`, `GET /charts/catalog`,
  `backend/app/routers/charts.py`): backend-only this session — frontend rendering
  is a separate, later checkpoint. Constrained end to end, matching
  `project_scope.md` §5's requirement exactly: `backend/genai/chart_specs.py`
  defines a **fixed allowlist of 9 pre-written, parameter-free queries**
  (`CHART_SPECS`, e.g. `top_scorers`, `team_points`, `goals_by_stage`). The LLM's
  only job (`genai/llm.py`'s `classify_chart_template()`, using Groq's JSON mode —
  `response_format={"type": "json_object"}` — for reliable structured output) is
  to pick one allowlist **key by name**; it never generates or contributes to SQL
  text. The router parses that JSON and validates the name against the real dict
  — anything not an exact key (malformed JSON, a hallucinated name, `null` when
  nothing fits) is rejected with a 422, never reaching the database. Shares the
  same rate limiter as `/chat/*` and `/reports/*` (same cost-protection budget,
  consistent with the rest of the GenAI surface).
  Unit-tested (`backend/tests/test_charts.py`) including the actual security
  property: a well-formed JSON response naming a template *outside* the allowlist
  must still be rejected. Verified live against real Groq + the real database:
  "who are the top goal scorers in the tournament?" → `top_scorers` with real
  player names/goal counts; "which teams are winning the most in the league
  table?" → `team_points`; "which teams have the best defense based on clean
  sheets?" → `team_clean_sheets`; a deliberately off-topic question ("what is the
  capital of France?") correctly got a 422, not a guess.
- **Frontend rendering** (`frontend/src/app/charts/page.tsx`, new `/charts` nav
  entry): a `"use client"` page mirroring `/chat`'s input/loading/result pattern —
  example-prompt buttons, a text input, and the result rendered via the existing
  `BarChartCard` component (reused as-is, no new chart component needed since
  every template is `chart_type: "bar"`). `askChart()` added to `lib/api.ts`
  as a bespoke fetch wrapper (not the shared `apiPost` helper) because a 422
  rejection from the allowlist carries a real, user-facing `detail` message
  ("couldn't match that question...") worth surfacing directly rather than
  hiding behind a generic error. `ChartDataPoint.value` is `number | null` from
  the API (a stat can legitimately be absent for a given row) but `BarChartCard`'s
  recharts data expects `string | number` — mapped `null → 0` at the page level
  rather than loosening the shared chart component's type for one caller.
  **Required rebuilding and redeploying the backend image** (`fifa26-api:v4` via
  `az acr build` + `terraform apply`) — the previously-deployed `v3` image
  predated the charts backend work, confirmed via a live `404` on
  `/charts/catalog` before the redeploy, `200` after.
  Verified live end-to-end in a real browser: page loads, an example prompt
  ("who scored the most goals?") returns real ranked player data rendered as a
  bar chart, and an off-topic question correctly surfaces the backend's 422
  message instead of a chart. Live at
  https://stfifa266q3jm1.z13.web.core.windows.net/charts/.
- **Deploy tooling note discovered while shipping this**: `az storage blob
  upload-batch` (used for every prior frontend deploy) stalled badly on this
  export's ~11.7k files — only ~1,800 uploaded in 34 minutes before basically
  flatlining. Switched to `azcopy sync` (installed via `brew install azcopy`,
  authenticated with an account-key-derived SAS token since the logged-in CLI
  identity lacks the data-plane RBAC role `azcopy`'s `--auth-mode login` needs)
  — finished the same 9,869-file transfer in 2 minutes with zero failures.
  `az storage blob upload-batch` is fine for a few hundred files; `azcopy sync`
  is the right tool once a static export grows this large (driven by the
  per-player/per-team static pages).
- Built next (same "reports" family) — see "Auto-generated match recaps" below,
  which closes out this item.

### Auto-generated match recaps (Phase 3, closing slice)
- **`POST`/`GET /reports/matches/{match_id}`** (`backend/app/routers/reports.py`):
  the last remaining "scouting reports / match recaps" item from
  `project_scope.md` §5, mirroring the player/team report pattern exactly —
  `build_match_summary_text()` (new, `backend/genai/embeddings.py`) turns a
  match's real box score into natural-language context, `generate_match_report()`
  (`backend/genai/llm.py`) sends it to Groq with a sports-journalism system
  prompt, cached in a new `match_reports` table. Unlike player/team reports,
  there's no separate "recent matches" fetch appended — the match itself, plus
  its full box score, is the entire subject rather than one data point in a
  longer-form narrative. Shares the same rate limiter as the rest of the GenAI
  surface.
- **New `GET /analytics/matches/{match_id}`** (`backend/app/routers/analytics.py`):
  returns a match plus its full box score (every `player_match_stats` row for
  that match, joined to `player_name`, sorted by rating) — used both as the
  match-recap generation context and as the frontend detail page's data source.
- **`match_reports` schema pushed to the deployed Azure Postgres via
  `apply_schema()` only** (`etl/load.py`), not a full `etl/load.py` run —
  deliberately avoided the documented `truncate ... cascade` behavior that wipes
  `player_embeddings`/`team_embeddings` on every full reload (see "Infrastructure"
  below), since only a new `create table if not exists` was needed, not a data
  reload.
- **Frontend**: new `/matches` (list, mirrors `/teams`'s plain server-rendered
  `DataTable` pattern — no client-side filtering) and `/matches/[id]` (detail,
  mirrors `/players/[id]`'s `generateStaticParams()` + build-time fetch
  pattern) pages. `generateStaticParams()` reuses the existing, already-uncapped
  `getMatches()` list call instead of needing a new dedicated `/ids` endpoint
  (unlike players, `/analytics/matches` was never capped to a top-N). `<ScoutingReport>`
  generalized from `kind: "player" | "team"` to a third `"match"` variant
  (reused as-is — it only ever rendered `report_text`/`generated_at`, so no new
  component needed, just new fetch/generate functions and copy per kind).
- Unit-tested: 6 new tests for `build_match_summary_text()` (scorers, top-rated
  performer, cards, empty-performers edge case), 2 for the new analytics
  endpoint, 8 for the reports router (cache hit/miss, generation, 503 on Groq
  failure, rate limiting) — 62 backend tests total, up from 39. `make lint` clean.
- **Verified live end-to-end against the real deployed Postgres + a real Groq
  call** (not mocked, not yet the deployed Container App): generated a recap for
  a real match (Chile 1-1 Ecuador) that correctly cited the exact goal scorers
  (Mauricio Isla, Gonzalo Mena), all 7 correctly-named carded players, and the
  correct top-rated performer (Diego Pacho, rating 8.40) — then confirmed
  caching (13ms round-trip on a second request, same timestamp, no new Groq
  call). Local static export built cleanly against the real running backend:
  2,356 pages total, including all 1,050 new match detail pages.
- **Deployed and verified live**: shipped as `fifa26-api:v5` via `az acr build` +
  `terraform apply`; `match_reports` schema applied directly to the real Azure
  Postgres via `apply_schema()` (not a full `etl/load.py` run, to avoid the
  documented truncate-cascade wipe of the embeddings tables). Frontend static
  export rebuilt and uploaded via `azcopy sync` (~9.9k files, 2 minutes, zero
  failures). Confirmed live: `/matches` and `/matches/{id}` return real data,
  and `POST /reports/matches/{id}` generated a real recap against the deployed
  API. **Found and fixed a stale Postgres firewall rule while deploying**: the
  `allow-dev-ip` rule still had an old IP from a previous network change,
  causing the schema-apply connection to time out — updated via `az postgres
  flexible-server firewall-rule update`, and `infra/terraform.tfvars`'s
  `dev_ip_address` was also updated to match, since it had silently drifted
  from the manually-applied fix and a future plain `terraform apply` would
  have reverted it back to the stale IP.

### CI/CD (Phase 4, first slice)
- `.github/workflows/ci.yml`: lint + test on every push to `main`/`master` and every
  PR, in two parallel jobs. **Backend**: `make install && make lint && make test` —
  literally the same targets used locally, not a separately-maintained CI-only
  command list, so CI can't quietly drift from what a developer runs on their own
  machine. **Frontend**: `npm ci && npm run lint && npm run build` (`next build`
  type-checks as part of building, so a separate `tsc` step isn't needed).
- **Caught a real, pre-existing bug while setting this up**: `npm run lint` had never
  actually been run on this project before (only `tsc --noEmit` and `npm run build`,
  neither of which run ESLint) — it failed immediately on `ScoutingReport.tsx` with
  `react-hooks/set-state-in-effect` (calling `setLoading(true)` synchronously at the
  top of a `useEffect`). Root cause: `loading` already defaults to `true` in
  `useState`, so the call was only ever needed to reset state when the component's
  `id`/`kind` changes without remounting (e.g. navigating from one player's profile
  to another). Fixed properly rather than just silencing the rule: both call sites
  (`players/[id]/page.tsx`, `teams/[team]/page.tsx`) now pass `key={id}` to
  `ScoutingReport`, so a change in entity forces a real remount — React's own
  documented pattern for "reset state when a prop changes" — making the redundant
  `setLoading(true)` removable entirely.
- Originally scoped to lint + test only, since building/pushing Docker images needed
  a container registry and OIDC federated credentials that didn't exist yet at the
  time — both now exist and the automation is built (see "CI/CD automation" below).
- **Verified with a real run on GitHub** — and it caught something local runs never
  would: the first push reported the backend job as failed even though `make install`,
  `make lint`, and `make test` all individually succeeded. The actual failure was in
  `setup-python`'s own automatic post-job step, which tries to save a pip cache — but
  `make install` runs `pip install --no-cache-dir` (a deliberate, disk-conscious
  choice worth keeping), so pip's cache directory is never populated and there was
  nothing for that step to save. Fixed by dropping the `cache: pip` option from the
  workflow entirely rather than changing how `make install` works — a genuine example
  of "passes every local check, still red in CI," specifically because CI exercises a
  step (cache save/restore) that local development never touches at all.

### Observability (Phase 4, second slice)
- `backend/app/main.py` now calls `configure_azure_monitor()` (the
  `azure-monitor-opentelemetry` package — Microsoft's OpenTelemetry distro for Azure
  Monitor) at startup, but only when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set
  (`backend/app/config.py`). Local dev without the env var is an explicit no-op —
  confirmed via the full test suite passing with it unset. One call auto-instruments
  FastAPI, `requests`, and `psycopg2` via their standard OpenTelemetry instrumentation
  packages (all pulled in automatically as sub-dependencies), so request traces and DB
  spans need no per-route code. It's called after `configure_logging()`, not before —
  it *adds* a handler to the `"app"` logger rather than replacing it, so stdout JSON
  logs (for local dev / `az containerapp logs`) and the Application Insights export
  stay active together rather than one clobbering the other.
- Verified live against the real deployed `appi-fifa26-dev` resource (not just
  locally): ran the API locally with the real connection string (fetched via `az
  monitor app-insights component show`) for one verification pass, hit `/health`,
  `/health/ready`, and `/analytics/standings`, and confirmed every exported telemetry
  batch got `Response status: 200` from the ingestion endpoint; a KQL query
  (`az monitor app-insights query`) against the workspace found the requests queryable
  shortly after (a couple of retries returned 0 rows in between — Log Analytics query
  nodes have some eventual-consistency lag right after ingestion, not a sign of a
  problem, since the HTTP 200s and the eventual successful query already confirm data
  landed). The connection string was **not** added to local `backend/.env` — only the
  deployed Container App should export telemetry by default, so local dev traffic
  doesn't mix into the same Application Insights resource as production data.
- Not yet true end-to-end: the Container App itself still runs the placeholder
  hello-world image (see Infrastructure section below), so this is verified via a
  local process talking to the real Application Insights resource, not yet via the
  actually-deployed container. Once the Docker/registry piece of Phase 4 ships a real
  image, this wiring needs no further changes — it already reads the connection string
  from the environment, which `infra/container_apps.tf` already passes in.

### Containerization & real deployment (Phase 4, third slice)
- **`backend/Dockerfile`**: builds a lean serving image for the FastAPI backend —
  `python:3.13-slim` base, `libgomp1` (xgboost's compiled extension needs it at
  runtime and it's not in the slim base — a real "builds fine, crashes on first
  `/predict` call" gotcha caught before it shipped), `requirements.txt`/`pip install`
  as its own layer before the code is copied in (so code-only changes reuse the
  cached dependency layer on rebuild), then just `app/`, `genai/`, and
  `ml/artifacts/` — no tests, no training scripts, no dev venv.
  **`backend/.dockerignore`** keeps the build context small (excludes the 519MB
  `.venv`) and, more importantly, excludes `.env` so real secrets can never
  accidentally get baked into an image layer.
- **`infra/container_registry.tf`**: provisions Azure Container Registry (Basic SKU,
  ~$5/month — the one resource in this stack with a real ongoing cost and no free
  tier; confirmed with the user before provisioning). The Container App environment's
  existing managed identity was granted the `AcrPull` role, so the deployed app
  authenticates to the registry with zero stored credentials — no registry
  username/password exists anywhere in Terraform state or Key Vault.
- **Image built and pushed via `az acr build`** (`fifa26-api:v1`) — builds in Azure
  itself, not locally, so no Docker install was needed on the laptop at all.
  `infra/container_apps.tf`'s `api` app was then repointed from the Microsoft
  placeholder hello-world image to this real one via `TF_VAR_api_image` +
  `terraform apply`.
- **Verified genuinely live**, not just "applied without error": hit the real
  deployed Container App's URL and got back real responses —
  `/health` → `{"status":"ok"}`, `/health/ready` → `{"status":"ready"}` (a live
  Postgres ping from inside the container, not mocked), `/analytics/standings` →
  real team data from the deployed database. This is also the first true end-to-end
  verification of the Application Insights wiring from last session — the container
  logs show the same `azure.monitor.opentelemetry` traffic as the earlier local
  test, now coming from the actual deployed app rather than a local process.
- **Found and fixed a real deployment bug while verifying**: `infra/container_apps.tf`'s
  `api_fqdn`/`grafana_fqdn` outputs used `latest_revision_fqdn`, which is scoped to a
  specific revision and only resolves if that revision has an explicit traffic label
  assigned — this stack doesn't use per-revision labels, so hitting that hostname
  returned Azure's generic "This Container App is stopped or does not exist" page
  even though the app was running perfectly fine underneath. Root-caused via
  `az containerapp ingress show`, which surfaced the real stable, app-level hostname
  (`ingress[0].fqdn`) that always routes to whichever revision holds 100% traffic.
  Fixed both outputs; a good example of "the resource applied successfully" not being
  the same thing as "the thing Terraform told you to visit actually works."
- **Still placeholder/todo**: the image is built and pushed manually this session,
  not yet automated — building/pushing on every merge (needs a container registry
  step in CI, OIDC federated credentials for `terraform apply` from GitHub Actions)
  is the next natural Phase 4 piece. The Container App also scales to zero when
  idle (`min_replicas = 0`), so the first request after any idle period has a real
  cold-start delay — acceptable for a portfolio project, worth knowing before
  demoing it live.

### Frontend deployment (Phase 4, fourth slice)
- **The whole dashboard is now live**, not just the API — deployed as a Next.js
  static export (`output: "export"` + `trailingSlash: true` in `next.config.ts`) to
  the Blob Storage static website hosting already provisioned in `infra/storage.tf`.
  Chosen because the dataset is a fixed synthetic snapshot rather than live data, so
  pre-rendering everything at build time is the correct fit, not a compromise — and
  because it needs no running server/compute at all (unlike the API), just files
  served directly from storage.
- **Several real incompatibilities with static export were found and fixed**, not
  just a config flip: the player/team profile pages did per-request server-side
  fetching (`cache: "no-store"`), which has no meaning once there's no server left at
  request time — switched to `force-cache` (fetched once at build time). The two
  dynamic routes (`/players/[id]`, `/teams/[team]`) needed `generateStaticParams()`
  so Next knows every page to pre-render upfront (`dynamicParams: true`, i.e.
  "render one on demand later," isn't supported in static export at all). This
  required a **new backend endpoint**, `GET /analytics/players/ids`
  (`backend/app/routers/analytics.py`) — a plain directory listing of all 1248
  player IDs, distinct from `/leaderboard`'s deliberately-capped top-N — since
  nothing existing returned the full uncapped list. Shipped as a new image
  (`fifa26-api:v2`) via `az acr build`, redeployed the same way as the first image.
  The `/players` leaderboard page also read `?metric=` server-side (also
  incompatible) — converted to client-side query-param handling via
  `useSearchParams()` + `router.push()` (the pattern `MetricSelect.tsx` already used
  to *write* the param), wrapped in a `Suspense` boundary as Next requires. Hit the
  same `react-hooks/set-state-in-effect` ESLint rule from an earlier session in the
  process; fixed with the same pattern (`key`-based remount instead of manually
  resetting state inside the effect).
- **CORS**: the frontend and API now live on different hostnames, so browser
  requests between them are cross-origin. Added the frontend's real URL to the
  deployed API's `CORS_ORIGINS` env var (`infra/container_apps.tf`, `jsonencode(...)`
  of the storage account's `primary_web_endpoint` with its trailing slash trimmed,
  since a browser's `Origin` header never has a path) — verified via a real CORS
  preflight request against the deployed API, not just assumed to be correct.
- **Hardened `var.api_image`'s default** to the real image tag instead of the
  original Microsoft placeholder, so a future plain `terraform apply` (without
  remembering to pass `TF_VAR_api_image`) can't silently roll the live deployment
  back to hello-world.
- **Verified genuinely live, end-to-end**: built the static export with
  `NEXT_PUBLIC_API_URL` pointed at the real deployed API, uploaded all 1,304
  generated pages (~568MB — Next's App Router static export includes RSC
  navigation payloads alongside the HTML, not just `.html` files) to the storage
  account's `$web` container via `az storage blob upload-batch`, then confirmed
  live: the homepage renders real baked-in data, individual player and team pages
  load (spot-checked), and a full CORS preflight + actual request from the deployed
  frontend's real origin to the deployed API both succeed.
- **Not yet automated**: this build+upload was done by hand this session, same as
  the backend image — folding both into the CI/CD-on-merge pipeline is still the
  remaining Phase 4 piece (see below).

### CI/CD automation (Phase 4, fifth slice)
- **Every backend deploy up to this point was done by hand** (`az acr build` run
  locally, three times). `.github/workflows/ci.yml` now has a `build-push-image` job
  that does the same `az acr build` automatically on every push to `master`, after
  the lint+test job passes — tagged with the commit SHA, not `latest`, so a human
  can trace exactly which commit produced a given image. Deliberately still
  build-and-push only, not deploy: the Container App only picks up a new image via a
  manual `TF_VAR_api_image` + `terraform apply`, same as before.
- **Authenticated via GitHub Actions OIDC**, not a stored Azure secret: a federated
  identity credential (Azure AD app registration, bootstrapped once via `az ad`,
  documented in `infra/README.md`) lets GitHub mint a short-lived token scoped to
  this repo's `master` branch, which Azure AD exchanges for an access token that
  expires with the job. No `AZURE_CLIENT_SECRET` exists anywhere to rotate or leak.
- **Took four real, distinct failures to get working — each one root-caused and
  fixed, not worked around**, a genuinely useful debugging trail:
  1. The federated credential's `subject` used the plain
     `repo:<owner>/<repo>:ref:refs/heads/<branch>` format from Microsoft's own docs
     — but GitHub actually presents a newer format with stable numeric IDs attached
     (`repo:<owner>@<id>/<repo>@<id>:ref:...`, so the trust relationship survives a
     repo/owner rename). Fixed by reading the exact subject out of the failed run's
     own logs and matching it verbatim, not guessing at the format.
  2. `az acr build --registry <name>` without `--resource-group` resolves the
     registry by a subscription-wide name lookup, which needs broader list/read
     permissions than a narrowly-scoped role grants. Fixed by passing
     `--resource-group` explicitly, skipping the lookup entirely.
  3. `AcrPush` (data-plane push/pull) turned out not to include the management-plane
     actions `az acr build` also needs (`registries/read`, `.../scheduleRun`,
     `.../listBuildSourceUploadUrl`) — each surfaced as a separate
     `AuthorizationFailed` in turn. Rather than keep chasing individual actions,
     switched to `Contributor` scoped to just the one registry resource (Microsoft's
     own documented recommendation for `az acr build` under RBAC), kept alongside
     `AcrPush` since Contributor excludes `dataActions`.
  4. Separately, the *frontend* CI job also failed — a latent bug from the previous
     session's static-export work, not caused by this one: `next build` now needs a
     real reachable backend at build time (`generateStaticParams`), and CI had
     neither a running backend nor `NEXT_PUBLIC_API_URL` set. Fixed with a new
     GitHub repository *Variable* (not Secret — it's a public URL) pointing at the
     real deployed API.
- **Verified with an actual successful run**, not just "no errors on `terraform
  apply`": all three jobs (backend lint+test, frontend lint+build, build-push-image)
  passed together, and the resulting commit-SHA-tagged image was confirmed present
  in ACR (`az acr repository show-tags`) — not just "the job said success."
- **Tooling note**: installed GitHub CLI (`gh`) locally mid-session specifically to
  read raw Actions job logs directly (the GitHub REST API's log-download endpoint
  requires repo-admin auth even for public repos, so the earlier debugging rounds
  relied on the user manually copy-pasting error text out of the browser) — sped up
  the last two fix-verify cycles considerably.

### Observability dashboarding (Phase 4, sixth slice)
- **Grafana (`ca-fifa26-dev-grafana`, provisioned since the very first Terraform
  apply) is finally configured**, not just running an untouched stock image. Scope
  deliberately limited to this checkpoint: get the Azure Monitor datasource
  genuinely connected and verified against real telemetry. Building actual
  dashboard panels is the next, separate checkpoint.
- **Config had to be code, not UI clicks**: the Grafana Container App has
  `min_replicas = 0` and no persistent disk, so anything configured by clicking
  around in Grafana's own web UI would be wiped on the next scale-to-zero cycle.
  Used Grafana's "provisioning" feature instead — `infra/grafana/provisioning/
  datasources/azure-monitor.yaml` baked into a custom image (`infra/grafana/
  Dockerfile`, built via `az acr build`, same pattern as the backend image) so the
  config re-applies from scratch on every container start.
- **Credential-free auth, same pattern as everywhere else in this stack**: Grafana
  got its own user-assigned managed identity (`id-fifa26-dev-grafana`, separate
  from the API's — least-privilege, scoped to only what Grafana needs), granted
  `Log Analytics Reader` on the workspace and `Key Vault Secrets User` (so the
  Container Apps platform itself can resolve the admin-password secret reference)
  and `AcrPull` on the registry. No client secret, no connection string with
  embedded credentials.
- **Admin password**: generated (`openssl rand`) and landed in Key Vault, same as
  every other secret in this project, injected via `GF_SECURITY_ADMIN_PASSWORD`.
  Deliberately not left at the image's `admin`/`admin` default on a
  publicly-reachable ingress — and since there's no persistent disk, "changing it"
  via Grafana's own UI wouldn't have stuck anyway.
- **Three real, distinct issues found and fixed while verifying, not assumed away**:
  1. The datasource health check failed with `managed identity authentication is
     not enabled in Grafana config` — turns out `azureAuthType: msi` in a
     datasource's own config isn't enough; Grafana gates managed-identity auth
     behind a separate *server-wide* opt-in (`GF_AZURE_MANAGED_IDENTITY_ENABLED=true`
     + `GF_AZURE_MANAGED_IDENTITY_CLIENT_ID` for a user-assigned identity), a
     deliberate security guardrail so a datasource plugin can't silently ride
     whatever identity happens to be attached without the operator explicitly
     allowing it. Confirmed the exact config keys from Grafana's own source
     (`pkg/setting/setting_azure.go`) rather than guessing at env var names.
  2. A real KQL query against `requests` (the table name used inside Application
     Insights' own Logs blade) failed with `Failed to resolve table or column
     expression named 'requests'` — querying the *raw* Log Analytics workspace
     directly (which is what Grafana's Azure Monitor datasource does) uses the
     underlying `App*`-prefixed table names (`AppRequests`, `AppTraces`, etc.);
     `requests`/`traces` are aliases that only exist in the App Insights resource's
     own query surface, not the workspace itself.
  3. Fresh traffic generated against the live API to verify real data flowing
     through stayed at `0` far longer than "eventual consistency" could explain —
     initially assumed to be ingestion lag (last session's note), but this
     session's dashboard-building work found the real cause: `AppRequests` has
     **zero rows, total, ever** — not delayed, genuinely empty — while `AppTraces`
     (10,491 rows), `AppDependencies` (2,206), and every other Azure Monitor table
     are populated normally. Confirmed via `search * | summarize count() by
     $table` across the whole workspace. The FastAPI/ASGI OpenTelemetry
     auto-instrumentation wasn't producing request spans at all. Not chased
     further in this slice of work, since the dashboard doesn't need
     `AppRequests` to succeed — genuinely root-caused and fixed in the very next
     session slice below ("FastAPI request-span instrumentation fix"), which
     found the real cause was different from the `BaseHTTPMiddleware` theory
     that seemed most likely at the time.
- **Dashboard built on data that actually exists**: `AppTraces` already captures
  every request via the app's own structured log line
  (`backend/app/middleware.py`'s `"request method=%s path=%s status=%s
  duration_ms=%.1f"`), so the dashboard's KQL parses that message text
  (`parse Message with "request method=" Method " path=" Path " status="
  StatusCode:int " duration_ms=" DurationMs:double`) instead of depending on the
  broken `AppRequests` path. Verified against real historical data spanning
  multiple sessions: 10,469 total parsed requests, 10,422 `200`s, 47 `404`s
  (root-path platform health probes), zero `5xx`.
- **`infra/grafana/provisioning/dashboards/`**: `dashboards.yaml` (the provider
  config, same "load from this folder" pattern as the datasource) +
  `api-overview.json` — 6 panels (total requests, avg latency, 5xx count, request
  rate over time, latency avg/p95 over time, status-code breakdown), each a real
  KQL query against the workspace, `uid: fifa26-api-overview` pinned so the URL is
  stable across redeploys. Shipped as `grafana-custom:v2`.
- **Found and fixed one more real bug while building this**: the datasource's
  `uid` was never pinned in `azure-monitor.yaml` — Grafana auto-generates a random
  one on each fresh provisioning pass when none is set, and since this container
  has no persistent disk, *every* scale-to-zero-and-back is a fresh pass. Left
  unpinned, the very next cold start after checkpoint 1 would have silently broken
  every panel referencing that datasource by UID. Fixed by adding `uid:
  azuremonitor` before building the dashboard on top of it.
- **Verified live, not just "provisioned without error"**: `/api/search` confirms
  the dashboard is loaded; ran the actual panel queries through `/api/ds/query`
  and got back the real counts above, not empty frames.
- Dashboard: https://ca-fifa26-dev-grafana.livelyground-6362aca7.eastus.azurecontainerapps.io/d/fifa26-api-overview/fifa-26-api-overview
  (admin credentials in Key Vault / `infra/.env.secrets`, not committed).

### FastAPI request-span instrumentation fix (Phase 4, seventh slice)
- **The real root cause was different from what last session's investigation
  concluded.** The `BaseHTTPMiddleware`/ASGI-context-propagation theory was a
  reasonable, well-documented hypothesis — but rewriting `RequestContextMiddleware`
  as pure ASGI middleware (`backend/app/middleware.py`) and re-testing showed the
  same result: still zero request spans. The actual cause was a classic Python
  import-binding gotcha in `backend/app/main.py`: `from fastapi import FastAPI` at
  the top of the file binds the *original*, unpatched class into that module's
  namespace at import time. `configure_azure_monitor()`'s FastAPI
  auto-instrumentation works by later reassigning the `fastapi` module's `FastAPI`
  attribute to an instrumented subclass — but reassigning `fastapi.FastAPI`
  doesn't retroactively update a name `main.py` already bound elsewhere. So
  `app = FastAPI(...)` was silently building a plain, uninstrumented app the
  entire time, no error, just no request span, ever.
- **Fix**: explicitly call `FastAPIInstrumentor.instrument_app(app)` on the actual
  `app` object right after constructing it, instead of relying on the global
  "patch the class, hope every future instance picks it up" auto-instrumentation
  trick. This sidesteps the import-order trap entirely by instrumenting the
  concrete instance directly. The `RequestContextMiddleware` rewrite to pure ASGI
  (from the earlier hypothesis) was kept — it's a legitimate, independently
  correct improvement (matches Starlette's own documented guidance for avoiding
  `BaseHTTPMiddleware`'s context-propagation limitations) even though it wasn't
  the actual fix.
- **Debugging approach**: rather than trust cloud ingestion timing again after
  last session got burned by it, verified locally and directly at each step —
  first via a console span exporter (initially gave a false negative due to a
  disconnected tracer provider, a red herring), then definitively by patching
  `AzureMonitorTraceExporter.export()` itself to print exactly what spans it
  receives. That showed a genuine `SpanKind.SERVER` span for `GET /health` with
  full HTTP attributes, proving the fix before waiting on any cloud round-trip.
- **Verified for real, twice**: locally (a real KQL query against Log Analytics
  found the exact 3 test requests in `AppRequests` — the first rows that table
  has ever had in this project's history) and then again against the actual
  deployed Container App after shipping `fifa26-api:v3` — real traffic through
  the live URL, confirmed queryable in `AppRequests` with matching URLs, status
  codes, and durations.
- **Not done**: switching the Grafana dashboard's panels from the `AppTraces`
  workaround back to querying `AppRequests` directly — the current dashboard
  already works correctly, so this is optional cleanup, not a fix, for a future
  session.

### Sentry error tracking (Phase 4, eighth slice)
- **Backend**: `sentry_sdk.init(dsn=..., traces_sample_rate=0)` in `app/main.py`,
  gated on `settings.sentry_dsn` (`SENTRY_DSN` env var) — same env-var-gated,
  no-op-when-unset pattern as Application Insights. `traces_sample_rate=0`
  deliberately: this project already has dedicated tracing via Application
  Insights/OpenTelemetry, so Sentry here is scoped to error tracking only, not
  a second, redundant tracing pipeline. `sentry-sdk[fastapi]==2.66.1` added to
  `backend/requirements.txt`.
- **Found and corrected a wrong assumption while wiring the exception handler**:
  initially added an explicit `sentry_sdk.capture_exception(exc)` call inside
  the existing global `@app.exception_handler(Exception)`, reasoning (by analogy
  with the earlier `FastAPIInstrumentor.instrument_app()` lesson) that a custom
  handler swallowing the exception into a `JSONResponse` would prevent Sentry's
  auto-instrumentation from ever seeing it. A live test showed the error reached
  Sentry either way — the traceback revealed Sentry's Starlette integration
  specifically patches `ExceptionMiddleware.__call__` to re-raise after a custom
  handler runs, purely so its own outer capture point still observes it. Removed
  the redundant explicit call (it would have double-reported every error) and
  documented the actual mechanism in a comment instead.
- **Frontend**: `@sentry/nextjs@10.69.0`. Since this site is a static export
  (`output: "export"`, no Node/edge server at request time), skipped the
  standard `@sentry/nextjs` wizard's server/edge config files and
  `withSentryConfig()` build wrapper entirely — deliberate, not an oversight:
  those exist for source-map upload and request tunneling on a running Next.js
  server, neither of which applies here. Client-side capture is what's
  relevant, and `Sentry.init({dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0})` in a new `instrumentation-client.ts` (Next's
  auto-loaded client-instrumentation convention) is sufficient on its own —
  installs global handlers for uncaught exceptions and unhandled promise
  rejections with no further config. Added `src/app/global-error.tsx`
  (Sentry's documented App Router pattern) on top, since React render errors
  don't reach `window.onerror` the same way.
- **`npm audit` flagged 4 high-severity vulnerabilities after installing** —
  investigated rather than blindly running `--force`: 3 of the 4 are nested
  inside `next`'s own dependency tree (`postcss`, `sharp`), and the suggested
  fix would downgrade Next.js from 16 to 9, a massive breaking change wildly
  disproportionate to the actual risk on a fixed-dataset static site with no
  user uploads or attacker-controlled CSS. Applied only the one safe,
  non-breaking fix (`brace-expansion`) via plain `npm audit fix`; left the rest.
- **Verified live, twice over, not just "no errors on deploy"**: triggered a
  real unhandled exception against a local backend (temporary debug route,
  removed immediately after) and a real uncaught browser error against the
  local frontend dev server — both confirmed landing in their respective
  Sentry project dashboards by direct visual check, not just "the SDK didn't
  throw." Repeated both checks against the actual deployed infrastructure
  after shipping: the live Container App's startup log (`sentry_configured`)
  confirmed via a direct Log Analytics KQL query (`az containerapp logs show`
  wasn't reliably capturing the cold-start window, since `min_replicas = 0`
  means the container can scale to zero between checks — the workspace query
  is the durable source of truth, same lesson as the Grafana dashboarding
  session), and a real triggered browser error against the live production
  URL was confirmed in the Sentry dashboard too.
- **Infra**: new `var.sentry_dsn_backend` (`infra/variables.tf`), passed as a
  plain Container App env var (`infra/container_apps.tf`) rather than a Key
  Vault secret — deliberately, unlike `groq_api_key`: a Sentry DSN is a
  write-only ingest endpoint meant to be embeddable/public (the same value
  ends up baked directly into the frontend's public JS bundle for the Next.js
  project), not credential material. Shipped as `fifa26-api:v6`.
  `NEXT_PUBLIC_SENTRY_DSN` added to the CI frontend build step
  (`.github/workflows/ci.yml`), mirroring `NEXT_PUBLIC_API_URL`'s existing
  pattern — the actual GitHub repository Variable itself hasn't been set yet,
  so this wiring is inert in CI until that one manual step happens.
- **Deploy tooling note**: `azcopy sync` and even `azcopy copy` both hit a
  persistent connection-reset failure this session on the `$web` container's
  destination-listing call (now ~21k blobs across all deploys) — unlike the
  match-recap deploy, a fresh restart didn't clear it this time, pointing to a
  genuinely flaky network window rather than a one-off blip. Fell back to `az
  storage blob upload-batch`, which doesn't do this large listing call and
  isn't affected by this specific failure mode (its own known weakness is
  being slow, not failing outright). To unblock verification immediately
  rather than waiting ~15-20 minutes for the full 21,217-file batch, uploaded
  just the ~13 files the homepage actually needs via individual `az storage
  blob upload` calls first, verified Sentry live within a minute, then let the
  full batch finish in the background for total site consistency. Also found
  and killed a genuine zombie process from the earlier match-recap deploy: an
  `azcopy sync` invocation that was believed killed had actually orphaned and
  kept retrying with an expired SAS token for 90+ minutes, silently competing
  for bandwidth with this session's uploads.

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
- **No longer placeholder**: the `api` Container App now runs the project's real
  FastAPI image (see "Containerization & real deployment" above), and the database
  has been populated since an earlier session. Building/pushing that image
  automatically on every merge (rather than by hand, as done this session) is the
  remaining Phase 4 CI/CD piece.
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

- **Phase 3 (GenAI) is fully built and fully deployed**: embeddings (player and
  team), retrieval, grounded generation, rate limiting, auto-generated/cached
  scouting reports and recaps (player, team, and match), a frontend chat UI,
  and the natural-language → chart feature (allowlisted backend spec +
  frontend rendering) — every item in `project_scope.md` §5 has shipped and is
  live on Azure, nothing left in this phase.
- **Phase 4 (observability/CI/CD) is nearly fully built**: lint + test CI,
  Application Insights wiring, the real FastAPI backend, the real Next.js
  frontend, automated build/push of the backend image on every merge (via
  GitHub Actions OIDC), a working Grafana dashboard on real telemetry, correct
  FastAPI request-span instrumentation, and Sentry error tracking (backend +
  frontend, deployed, verified live) are all built. Still unbuilt: automating
  the *deploy* half of CI/CD (`TF_VAR_api_image` + `terraform apply` on merge —
  still a deliberate manual step), automating the frontend build/upload the
  same way, load testing. One loose end: the `NEXT_PUBLIC_SENTRY_DSN` GitHub
  repository Variable hasn't actually been set yet, so CI's frontend build
  step (already wired to read it) is currently a no-op for Sentry until that
  one manual step happens.

## Known limitations / honest caveats

- The dataset's match outcomes and tournament totals are close to random — this is
  called out rather than hidden, and shapes what claims the ML section can honestly make.
- No integration tests against a real Postgres yet (only mocked-DB unit tests).
- No authentication anywhere (out of scope — see `project_scope.md`).
