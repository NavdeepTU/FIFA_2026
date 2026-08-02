# Architecture Reference

Living document. Read this first when you come back to the project after a break — it
explains what each piece does, how data flows through the system, and why the choices
were made. Update it whenever a decision changes; don't let it drift from reality.

For the phase-by-phase build plan and rationale history, see
`/Users/navdeep/.claude/plans/toasty-honking-kettle.md`. This file is the "how it fits
together" reference; that one is the "how we got here" log.

---

## 1. What this project is

An end-to-end analytics platform built on the FIFA World Cup 2026 player-performance
dataset (54,600 player-match rows, 48 teams, 1,248 players, 1,050 matches — see
`data/raw/dataset_info.txt`). It exists to demonstrate, in one coherent system:

- **Data engineering** — a real ETL pipeline, not a notebook
- **Backend/API design** — FastAPI serving analytics over Postgres
- **ML** — supervised + unsupervised models trained on the dataset, served live
- **GenAI** — a RAG assistant answering natural-language questions, grounded in real data
- **Cloud infrastructure** — Azure, provisioned via Terraform, cost-governed
- **Observability** — logging, metrics, alerting, error tracking

**A note on the data itself**: it's synthetic. Player IDs repeat across far more matches
than a real 48-team tournament allows, and the `total_*_tournament` / `tournament_rating`
columns are noisy, not true running totals (verified during ETL design — see §4). Treat
per-row stats as internally consistent and usable for pipeline/ML mechanics; don't treat
the tournament narrative (who "actually" won) as realistic. This is called out explicitly
because it shapes ETL and ML design decisions below (e.g., computing our own aggregates
instead of trusting the source's pre-computed tournament totals).

## 2. High-level architecture

```
data/raw/*.csv
      │
      ▼
  etl/  (pandas transform + Postgres load)
      │
      ▼
  Azure DB for PostgreSQL (+ pgvector)  ◄─────────────┐
   - players, teams, matches, player_match_stats       │
   - materialized views (standings, leaderboards,      │
     tournament progression)                           │
   - player_embeddings (Phase 3)                        │
      │                                                 │
      ▼                                                 │
  backend/  (FastAPI on Azure Container Apps)           │
   - /analytics/*  — reads from Postgres                │
   - /predict/*    — loads model artifacts (Phase 2) ───┘
   - /chat/*       — RAG via Groq (Phase 3)
      │
      ▼  HTTPS (CORS)
  frontend/  (Next.js, static export → Blob Storage)
   - Overview, Players, Teams pages
   - Charts via Recharts, styled to the dataviz skill's palette

  ml/ (backend/ml/) — offline training, artifacts → backend/ml/artifacts/, loaded by
  the API at request time; NOT retrained on every request.

  infra/ — Terraform (azurerm). Provisions everything above. Applied — see §7.
```

## 3. Repository layout

| Path | Purpose |
|---|---|
| `data/raw/` | Source CSV + dataset info. Gitignored (large, not committed) — see §4 for why. |
| `etl/` | `transform.py` (pure pandas, no I/O — testable), `load.py` (Postgres load, idempotent), `schema.sql` (DDL + materialized views). |
| `backend/app/` | FastAPI app: `main.py` (app wiring), `config.py` (env-based settings), `db.py` (SQLAlchemy engine), `rate_limit.py` (in-memory limiter shared by `/chat/*` and `/reports/*`), `routers/` (`analytics.py`, `predict.py`, `chat.py`, `reports.py`). |
| `backend/ml/` | Offline training scripts + saved model artifacts (Phase 2). |
| `backend/genai/` | RAG layer (Phase 3): `embeddings.py` (player + team summary text builders, shared fastembed wrapper), `generate_embeddings.py` / `generate_team_embeddings.py` (populate `player_embeddings` / `team_embeddings`, offline), `llm.py` (provider-agnostic `generate_answer()` / `generate_player_report()` / `generate_team_report()`, Groq today). |
| `backend/tests/` | pytest suite for the API. |
| `etl/tests/` | pytest suite for the transform logic. |
| `frontend/src/app/` | Next.js pages (App Router): `/`, `/players`, `/players/[id]`, `/teams`, `/teams/[team]`, `/predict`, `/chat`. |
| `frontend/src/components/` | Shared UI: `DataTable`, `StatTile`, `BarChartCard`, `Nav`, `MetricSelect`, `ScoutingReport` (`kind: "player" \| "team"`, used on both profile pages). |
| `frontend/src/lib/api.ts` | Typed fetch client for the backend API. |
| `infra/` | Terraform: `main.tf` (resource group), `postgres.tf`, `storage.tf`, `keyvault.tf`, `container_apps.tf`, `budget.tf`. |
| `.github/workflows/` | `ci.yml` — lint + test on push/PR (Phase 4, first slice; see §9). Docker build/push + `terraform apply` on merge not yet built. |
| `docs/` | This file, plus anything else worth keeping close to the code. |

## 4. Data flow, in detail

### 4.1 ETL (`etl/`)

1. `transform.py` reads the raw CSV and splits it into four normalized tables:
   `teams`, `players`, `matches`, `player_match_stats`. Player bio fields (age, team,
   position, etc.) are assumed constant per `player_id` and collapsed with `.first()`.
   `matches` is derived by pairing up the two per-player "sides" of each `match_id` and
   picking a canonical alphabetical ordering (`team_a < team_b`) so re-running the ETL
   produces identical rows (idempotency matters for the load step).
2. `load.py` applies `schema.sql`, truncates tables in reverse FK order, loads them in
   forward FK order (`teams → players/matches → player_match_stats`), then refreshes the
   materialized views (`mv_player_tournament_stats`, `mv_team_standings`,
   `mv_team_tournament_stats`, `mv_tournament_progression`). Safe to re-run end-to-end
   at any time.
3. **Why compute our own aggregates instead of using the CSV's tournament columns**:
   the source's `total_goals_tournament` / `tournament_rating` etc. don't behave as true
   cumulative running totals (checked directly against the data — a player's
   `total_minutes_tournament` fluctuates non-monotonically across their match rows).
   The materialized views instead `SUM`/`AVG` the granular per-match stats, which are
   internally consistent.
4. **Re-running the ETL wipes `player_embeddings`, `team_embeddings`, and
   `player_reports`, every time, not just on a first run**: `load_tables()`'s
   `truncate table ... cascade` cascades into *any* table with a foreign key into
   `players`/`teams` — that includes all three of those tables
   (`player_embeddings.player_id`, `team_embeddings.team_name`,
   `player_reports.player_id` are FKs), not just the four tables the ETL directly
   manages. `load.py` prints an explicit reminder at the end of every run: regenerate
   embeddings (`make genai-embed && make genai-embed-teams`); cached scouting reports
   regenerate on demand per-player (`POST /reports/players/{id}`), not in bulk, so
   there's nothing to re-run for those beyond visiting the player pages that need one
   again. Preserving any of these across an ETL rerun would need a different reload
   strategy (diff/upsert instead of truncate+reload) — not done, since
   truncate+reload's simplicity is what makes the ETL trivially idempotent in the
   first place.

### 4.2 Backend (`backend/`)

- Raw SQL via SQLAlchemy Core (`text()`), not a full ORM — this is a read-heavy
  analytics API over materialized views, so ORM object mapping would add ceremony
  without benefit. `db.py` exposes a `get_db()` FastAPI dependency yielding a
  connection per request.
- `routers/analytics.py` is the Phase 1 surface: standings, tournament progression,
  a metric-parameterized leaderboard (goals/assists/rating/tackles/saves — allowlisted,
  not a raw column passthrough, to avoid SQL injection via the query param), player and
  team profile endpoints, and a matches list.
- `routers/predict.py` serves Phase 2 model artifacts. `routers/chat.py` serves
  Phase 3 retrieval (`/chat/retrieve`, against `player_embeddings`); the Groq-backed
  generation half is still unbuilt — see §4.5.
- Config (`config.py`) is `pydantic-settings` reading from `.env` / real env vars:
  `DATABASE_URL`, `GROQ_API_KEY`, `CORS_ORIGINS`. No secrets are hardcoded anywhere.

### 4.3 Frontend (`frontend/`)

- Server Components fetch directly from the backend (`lib/api.ts`, `cache: "no-store"`
  since this is a live dashboard, not a blog). Every page catches fetch failures and
  renders a "could not reach the API" message rather than crashing — verified by
  building and hitting the pages with no backend running at all (see chat history / CI).
- Dynamic routes (`/players/[id]`, `/teams/[team]`) use the Next.js 16 async
  `params`/`searchParams` convention (`Promise<{...}>`, `await`ed) — confirmed against
  the docs shipped in `node_modules/next/dist/docs`, since this version is newer than
  general training data and the project's own `AGENTS.md` flags exactly that.
- Charts follow the `dataviz` skill: colors are the validated default palette (categorical
  slots in fixed order, sequential blue ramp, status colors reserved), wired in as CSS
  custom properties in `globals.css` for both light and dark mode, referenced by role
  (`var(--series-1)`, `var(--text-secondary)`, etc.) rather than raw hex in components.

### 4.4 ML (Phase 2, `backend/ml/`)

Trained offline against the ETL'd tables (or directly against the transformed CSV — no
live DB dependency required to retrain), artifacts saved to `backend/ml/artifacts/` and
loaded by `routers/predict.py` at request time. See §8 for the specific models and the
leakage consideration (composite score columns like `performance_score` are excluded from
inputs when predicting `player_rating`, since they're plausibly derived from it in the
synthetic data generation — using them as features would be leaking the target).

### 4.5 GenAI (Phase 3, RAG loop complete)

RAG over `player_embeddings` (pgvector column added in `schema.sql`), Groq for
generation, a constrained NL→query-spec translator (never raw LLM-generated SQL — see
the plan file's Phase 3 notes for the injection/cost-blowup reasoning).

**Embeddings built — player and team**: `backend/genai/generate_embeddings.py`
populates `player_embeddings` from `mv_player_tournament_stats`; the newer
`generate_team_embeddings.py` populates `team_embeddings` the same way, from
`mv_team_standings` (W/D/L/points) joined with `mv_team_tournament_stats` (a new
materialized view — box-score aggregates by team: tackles, interceptions, clearances,
saves, clean sheets, summed/averaged from `player_match_stats`, `schema.sql`). Team
embeddings exist specifically so retrieval isn't player-only — a question like "which
team has the best defense" needs a team-shaped summary to match against, not just
goals for/against. Both embedded locally via `fastembed` (`BAAI/bge-small-en-v1.5`,
ONNX, 384-dim). Local rather than a hosted API deliberately: Groq has no embeddings
endpoint, and this avoids a second API key/cost just for retrieval — the interface
(`embed_texts()`) is shared and still small enough to swap later if needed. Both
idempotent, re-run via `make genai-embed` / `make genai-embed-teams` after every ETL
load.

**Retrieval built — unified across both**: `POST /chat/retrieve`
(`backend/app/routers/chat.py`, `_retrieve_similar_entities`) embeds an incoming query
with the same `embed_texts()` used to build the embeddings, then does a single pgvector
`<->` distance search that's a `union all` over `player_embeddings` (joined against
`players`) and `team_embeddings`, ranked together and cut off at `top_k`. Deliberately
one ranked list rather than separate player/team result buckets: similarity alone
decides what's relevant, so a team-shaped query naturally surfaces only teams, a
player-shaped one only players, and a genuinely mixed query ("tell me about France, the
team and their players") surfaces both — verified live, all three cases. Using the same
embedding model for queries and documents isn't a style choice — vector similarity is
only meaningful if both sides came from the same model. This makes `fastembed` a
serving-time dependency of the API now, not just an offline-script one
(`backend/requirements.txt`).

**Generation built**: `POST /chat/ask` runs the same retrieval, then calls
`generate_answer()` (`backend/genai/llm.py`), which is the entire provider-agnostic
surface the router depends on — a Groq implementation today (`llama-3.3-70b-versatile`,
via the official `groq` Python SDK), swappable later by writing one new function with
the same signature rather than touching `chat.py`. The system prompt constrains the
model to answer only from the summaries it was given, rather than free-form guessing;
verified live that cited numbers (save counts, clean sheets) matched the retrieved
sources exactly. Each call logs model name, prompt/completion/total token counts, and
latency (`app.genai` logger) — the raw material for the FinOps token-usage dashboard in
§8, not that dashboard itself. `/chat/status` reports whether `GROQ_API_KEY` is
configured; `/chat/ask` returns 503 (not a bare 500) if generation fails, matching how
`/predict` handles missing model artifacts.

**Rate limiting built**: `backend/app/rate_limit.py` is a small in-memory, per-client-IP
fixed-window limiter (20 requests / 60s, shared across `/chat/retrieve` and
`/chat/ask`, and later `POST /reports/players/{id}` — see below), wired in as a
FastAPI dependency. Hand-rolled rather than a dependency like `slowapi` — same call
already made for structured logging (`logging_config.py`): the payoff for one more
package isn't there yet at this project's size. In-memory means it only tracks hits
within a single process; fine for the single Container Apps instance this project
targets, but a multi-instance deployment would need a shared store (Redis) instead.
Returns `429` with a `Retry-After` header once tripped; verified live. Tests reset the
limiter's state between runs via an autouse fixture (`conftest.py`) so they don't
trip each other's limits.

**Auto-generated, cached scouting reports built — player and team**: `POST
/reports/players/{id}` (`backend/app/routers/reports.py`) calls
`generate_player_report()` (`backend/genai/llm.py`) with the player's
`build_summary_text()` season summary (reused as-is from the embeddings pipeline — no
duplicated stats-formatting logic) plus their 5 most recent matches, and caches the
result in a new `player_reports` table. `POST /reports/teams/{team}` mirrors this
exactly for teams (`build_team_summary_text()`, `generate_team_report()`,
`team_reports` table) — recent matches for a team come from a `case when team_a =
:team ...` query over `matches`, since that table has no single "this side's
perspective" column the way `player_match_stats` does for players. `GET` on either
serves the cached version, 404 if none exists yet — repeat views cost nothing.
`generate_answer()`, `generate_player_report()`, and `generate_team_report()` all
share a `_complete()` helper in `llm.py` for the actual Groq call + token-usage
logging, so every generation path logs consistently; each still has its own system
prompt (player vs. team framing). Both share the chat rate limiter (same
cost-protection budget across every Groq-calling endpoint). Frontend:
`ScoutingReport.tsx`, a client component taking `kind: "player" | "team"` + `id` (it
only ever renders `report_text`/`generated_at`, so generalizing from the player-only
version needed no new logic, just picking which `lib/api.ts` fetch/generate functions
to call), embedded on both the player and team profile pages. Verified live,
end-to-end: two players and one team (fresh generation + pre-cached load each),
player page re-verified for regressions after the shared-component refactor.

**Auto-generated match recaps** extend the same pattern to a third entity level:
`POST /reports/matches/{match_id}` calls `generate_match_report()` with
`build_match_summary_text()`'s output (a new summary builder in
`genai/embeddings.py`, alongside the player/team ones — but with no matching
embeddings table, since matches aren't retrieved via `/chat`, only players and
teams are) and caches the result in a new `match_reports` table. Structurally
simpler than the player/team versions: there's no separate "recent matches"
fetch to append, since the match itself — plus its own full box score, sourced
from a new `GET /analytics/matches/{match_id}` endpoint — is the entire
subject rather than one data point in a season-long narrative. `ScoutingReport.tsx`
generalized again, from `kind: "player" | "team"` to a third `"match"` variant,
embedded on a new `/matches/[id]` detail page (`/matches` list mirrors `/teams`'s
plain server-rendered pattern; `generateStaticParams()` reuses the already-uncapped
`/analytics/matches` list rather than needing a dedicated `/ids` endpoint the
way `/players/[id]` does). Verified live against the real deployed Postgres and
a real Groq call; not yet deployed to the Azure Container App or the static
frontend export — see `project_status.md`.

**Natural-language → chart** (`POST /charts/ask`, `backend/app/routers/charts.py`) —
backend only so far, chart rendering on the frontend is a separate later piece. This
is the one GenAI feature in this project where "constrain the LLM to something safe"
matters most, since the naive version of this feature (ask an LLM to write SQL, run
it) is a textbook prompt-injection/SQL-injection risk. The actual design, matching
`project_scope.md` §5 exactly: `backend/genai/chart_specs.py` defines a **fixed
allowlist of pre-written, parameter-free queries** (`CHART_SPECS`, e.g.
`top_scorers`, `team_points`, `goals_by_stage` — 9 total). The LLM's only job
(`genai/llm.py`'s `classify_chart_template()`, using Groq's JSON mode —
`response_format={"type": "json_object"}`, for reliable structured output instead of
parsing free text) is to pick one allowlist entry **by name**. It never sees, writes,
or influences any SQL. The router parses that JSON and checks the name against the
real dictionary; anything that isn't an exact key — malformed JSON, a hallucinated
name, `{"template": null}` when nothing fits — is rejected with a 422 before it gets
anywhere near a database call. This means the worst a fully compromised or
adversarially-prompted LLM response can do is name something outside the allowlist,
which is simply rejected — there is no code path where LLM output becomes part of a
query string. Shares the same rate limiter as `/chat/*` and `/reports/*`. Verified
live against real Groq and the real database across several phrasings ("who are the
top goal scorers" → `top_scorers`, "which teams are winning the most" →
`team_points`, "best defense based on clean sheets" → `team_clean_sheets`), plus a
deliberately off-topic question ("what is the capital of France?") correctly
producing a 422 rather than a guess.

**Not yet built**: chart *rendering* on the frontend (next checkpoint for the above),
auto-generated match recaps (the one remaining "reports" item — match-level rather
than player/team-level; would need a per-match cache key and likely a frontend
matches page, which doesn't exist yet).

## 5. Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + SQLAlchemy Core | Async-friendly, typed, minimal ceremony for a read-heavy analytics API. |
| Frontend | Next.js 16 (App Router) | Server Components fetch data without a client-side loading waterfall; static-export friendly for Blob Storage hosting. |
| DB | Postgres (Azure Flexible Server, B1MS) | `pgvector` extension means no separate vector DB for the RAG layer; free-tier eligible. |
| ML | scikit-learn / XGBoost | Lightweight (no GPU/TensorFlow footprint — mattered given this machine's disk constraints), well-understood, sufficient for tabular data this size. |
| GenAI | Groq (Llama models) | Free tier, fast inference; called through a provider-agnostic interface so swapping to Claude/OpenAI later is a config change, not a rewrite. |
| IaC | Terraform (azurerm) | Real infra-as-code story for the resume; written to be applied deliberately, not automatically, given cost sensitivity. |
| CI/CD | GitHub Actions + OIDC | No long-lived Azure secrets in GitHub; cloud runners also do all Docker builds so the local laptop never has to. |
| Observability | Azure Monitor + App Insights + self-hosted Grafana + Sentry | Managed Grafana has no free tier; self-hosting is more hands-on anyway. |

## 6. Local development

No Docker, no local Postgres, no local Terraform/Azure CLI installed — by design, given
this machine's limited disk space. Instead:

```bash
# one shared venv for etl/ + backend/ (see backend/.venv)
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r etl/requirements.txt -r backend/requirements.txt

# ETL, once a Postgres instance exists (Azure free-tier, or any Postgres you point it at)
export DATABASE_URL=postgresql://user:pass@host:5432/fifa
python etl/load.py

# backend
cd backend && cp .env.example .env  # fill in DATABASE_URL
uvicorn app.main:app --reload

# frontend
cd frontend && cp .env.local.example .env.local
npm run dev
```

Run `df -h /` before any dependency install session if disk space has been an issue —
it's a recurring constraint on this machine, not a one-time fix.

## 7. Cloud deployment (Azure, via Terraform)

**Applied** — all 23 resources exist in Azure under `rg-fifa26-dev` (verified via
`az resource list`). See `infra/README.md` for the bootstrap steps (remote state setup,
`terraform apply`); local Azure CLI + Terraform, not Cloud Shell (see `CLAUDE.md`'s
disk-constraint note). Cost posture: every resource is sized to the free tier /
always-free grant (Postgres B1MS, Container Apps consumption plan, Blob Storage under
5GB, no CDN), and an actual Azure Budget + alert (`infra/budget.tf`) is the real
backstop — not just careful sizing.

**Postgres lives in a different region than everything else** (`eastus2` vs. `eastus`,
`var.postgres_location` in `variables.tf`/`postgres.tf`) — a deliberate deviation from
the original single-region design, forced by Azure rejecting Postgres Flexible Server
creation in `eastus` for this (brand-new) subscription with `LocationIsOfferRestricted`.
Every other resource type provisioned in `eastus` without issue, so only the database
moved. This is specific to new subscriptions in high-demand regions, not a permanent
property of the account — worth revisiting (`var.postgres_location` back to matching
`var.location`) once the subscription has some age/usage history, if consolidating
everything into one region becomes worthwhile (mainly: no real latency concern for a
low-traffic portfolio project as-is).

**The `api` Container App now runs the project's real code**, not a placeholder.
`backend/Dockerfile` builds a lean serving image (`python:3.13-slim` + `libgomp1` for
xgboost + `requirements.txt` installed as its own cached layer + just `app/`,
`genai/`, `ml/artifacts/` — no tests, no training scripts); `backend/.dockerignore`
keeps the 519MB local `.venv` out of the build context and excludes `.env` so real
secrets can't accidentally land in an image layer. The image is built and pushed with
`az acr build` (cloud-side build via Azure Container Registry's build service —
`infra/container_registry.tf`, Basic SKU, ~$5/month, the one resource in this stack
with a real ongoing cost and no free tier), so no Docker install was needed locally.
The Container App pulls from ACR using its existing managed identity (`AcrPull` role
grant) rather than a stored registry credential — the same "no secret at all, just an
identity + role" pattern already used for Key Vault access.

**Verified genuinely live**, not just "terraform apply succeeded": hit the real
deployed URL and got real responses back — `/health`, `/health/ready` (a live
Postgres ping from inside the container), and `/analytics/standings` (real data from
the deployed database). While verifying, found that `container_apps.tf`'s
`api_fqdn`/`grafana_fqdn` outputs used `latest_revision_fqdn` — an attribute scoped to
a specific revision that only resolves with an explicit traffic label (not used in
this stack) — so visiting it returned Azure's generic "stopped or does not exist"
page even though the app was healthy. Fixed both outputs to use `ingress[0].fqdn`,
the stable app-level hostname that always routes to whichever revision holds current
traffic. **Not yet automated**: this session's build/push/deploy was done by hand;
doing it on every merge via CI (needing a registry step + OIDC federated credentials)
is the remaining Phase 4 piece. The app also scales to zero when idle
(`min_replicas = 0`), so the first request after a quiet period has a real cold-start
delay — worth knowing before a live demo.

**The frontend is deployed too, not just the API** — as a Next.js static export
(`output: "export"` + `trailingSlash: true`, `frontend/next.config.ts`) to the Blob
Storage static website hosting `infra/storage.tf` already provisioned. Static export
was the right fit, not a shortcut: the dataset is a fixed synthetic snapshot rather
than live data, so baking every page at build time is correct, and it needs no
running compute at all (unlike the API's Container App) — just files served directly
from storage, which is why it lives on a completely different Azure service.

Getting there required fixing real incompatibilities with static export, not just
flipping the config flag: the player/team profile pages fetched server-side with
`cache: "no-store"`, which has no meaning once there's no server left at request
time (switched to `force-cache` — fetched once at build time, appropriate given the
static dataset). The two dynamic routes needed `generateStaticParams()`, since
static export must know every route to pre-render upfront (`dynamicParams: true` —
"render one later, on demand" — isn't supported at all in this mode). That required
a **new backend endpoint**, `GET /analytics/players/ids` (`backend/app/routers/
analytics.py`) — an uncapped directory listing of every player ID, distinct from
`/leaderboard`'s deliberately-capped top-N — since nothing existing returned the
full 1248-player list. Shipped as `fifa26-api:v2`, redeployed the same way as the
first image. The `/players` leaderboard page also read `?metric=` server-side
(same problem) — converted to client-side handling via `useSearchParams()` +
`router.push()` (the pattern `MetricSelect.tsx` already used to *write* the param),
wrapped in the `Suspense` boundary Next requires for that hook. Hit the same
`react-hooks/set-state-in-effect` lint rule from the CI session again in the
process; fixed with the same `key`-based remount pattern rather than resetting
state manually inside the effect.

**CORS** needed real wiring once the frontend and API landed on different
hostnames: added the frontend's real URL to the API's `CORS_ORIGINS` env var
(`infra/container_apps.tf`, `jsonencode(...)` of the storage account's
`primary_web_endpoint` with the trailing slash trimmed — a browser's `Origin` header
never has one) — verified with an actual CORS preflight request, not assumed.
`var.api_image`'s default was also hardened to the real image tag (was the
Microsoft placeholder) so a bare `terraform apply` can no longer silently roll the
live deployment backward if `TF_VAR_api_image` is forgotten.

**Verified genuinely live, end-to-end**: built with `NEXT_PUBLIC_API_URL` pointed at
the real deployed API, uploaded all 1,304 generated pages (~568MB — Next's App
Router static export ships RSC client-navigation payloads alongside the HTML, not
just `.html` files) to the storage account's `$web` container via `az storage blob
upload-batch`, then confirmed live in the browser and via `curl`: the homepage
renders real baked-in data, player/team pages load, and a full CORS preflight +
actual request from the deployed frontend's real origin to the deployed API both
succeed.

## 8. ML models (Phase 2)

Status: **built and served**. Code: `backend/ml/features.py` (shared feature engineering)
+ `backend/ml/train_*.py` (offline training, run via `make ml-train`) + `backend/app/ml_models.py`
(lazy artifact loading) + `backend/app/routers/predict.py` (serving). Artifacts are
committed to the repo (`backend/ml/artifacts/`, ~1.7MB total) so a fresh clone works
without retraining first.

**The leakage finding that shaped this** (see §4.1's note on the dataset being
synthetic): checking correlation against `player_rating` before picking features
showed `tournament_rating` (r=0.997), `performance_score` (r=0.997),
`distance_covered_km` (r=0.837), and `sprint_distance_km` are all effectively the same
underlying synthetic formula wearing different column names — not independent signal.
All composite/derived scores and physical-tracking columns were excluded from every
model's inputs; only genuine box-score actions (goals, passes, tackles, etc.) and
minutes played are used. This is why the numbers below are modest rather than
suspiciously perfect — that's the honest result once the leaky shortcut is removed.

| Model | Type | Target | Result (test set) |
|---|---|---|---|
| Player rating predictor | XGBoost Regressor | `player_rating` from raw box-score stats | R²=0.22, MAE=0.52 — genuine but weak signal, consistent with a mostly-random rating in this synthetic data |
| Match outcome predictor | XGBoost Classifier | W/D/L from team-aggregated match stats | 40% accuracy (3-class; near-chance) — team box scores carry very little signal for who wins in this dataset, worth stating plainly rather than dressing up |
| Player archetype clustering | KMeans (k auto-selected via silhouette, k=4) | Playstyle clusters from per-90 stats | Silhouette=0.417; clusters recovered football positions almost exactly from stats alone (Forward: shots+goals; Midfielder: passing+key passes; Defender: clearances+aerials; Goalkeeper: saves) without being told position — a good validation that the box-score stats themselves are meaningful even where the rating/outcome signal is weak |

Endpoints: `POST /predict/rating`, `POST /predict/outcome`, `GET /predict/archetypes/{player_id}`,
`GET /predict/archetypes` (distribution), `GET /predict/status` (artifact availability
check — returns 503 from the prediction endpoints if artifacts haven't been trained yet).

**Frontend**: `/predict` page — a live "what-if" panel that calls `/predict/rating` as
you edit a stat line, verified end-to-end against the real trained model.

## 9. Observability & engineering hardening

**Already built** (ahead of Phase 4, since it costs nothing to do from the start):
- Structured JSON logging (`backend/app/logging_config.py`) with a per-request
  correlation ID (`request_id_var`, a `ContextVar`), echoed back as `X-Request-ID`.
- `backend/app/middleware.py`: logs method/path/status/duration for every request.
- A global exception handler (`main.py`) returns a consistent `{"detail", "request_id"}`
  shape for anything unhandled — never leaks a traceback to the client, but logs the
  full traceback server-side keyed by that request ID.
- `GET /health` (liveness) vs `GET /health/ready` (actually pings Postgres) — the
  distinction matters once this runs behind Container Apps health probes: liveness
  should never depend on a downstream service, readiness should.
- Test suites: `backend/tests/` (pytest + FastAPI `TestClient`, DB layer mocked via
  `dependency_overrides` — unit tests, not integration tests; see the docstring in
  `backend/tests/conftest.py` for why real Postgres-specific SQL correctness is a
  separate, later concern) and `etl/tests/` (pandas transform logic against a small
  synthetic CSV fixture, not the full dataset — fast and isolated).
- `ruff` configured at the repo root (`pyproject.toml`) — `make lint` runs it.
- `Makefile` with `install`/`test`/`lint`/`etl-run`/`api`/`frontend-dev` targets so
  the exact commands don't need to be re-derived each session.
- **CI** (`.github/workflows/ci.yml`): lint + test on every push/PR, two parallel
  jobs (backend: `make install && make lint && make test`; frontend: `npm ci && npm
  run lint && npm run build`) that call the exact same commands used locally rather
  than a parallel CI-only script, so the two can't drift apart. Setting this up
  caught a real bug: `npm run lint` (ESLint) had never actually been run on this
  project before — `tsc --noEmit` and `npm run build` don't run it — and it failed
  immediately on a `react-hooks/set-state-in-effect` violation in `ScoutingReport.tsx`
  (a redundant `setLoading(true)` inside a `useEffect`, when `loading` already
  defaults to `true`). Fixed by adding `key={id}` where the component is used, so a
  changed entity remounts it fresh (React's documented pattern for this) instead of
  needing the effect to manually reset state. The first real push then caught a
  second issue only CI itself could surface: `make install`/`make lint`/`make test`
  all passed, but the job still failed, because `setup-python`'s automatic post-job
  step tries to save a pip cache and `make install` runs `pip install --no-cache-dir`
  (kept deliberately) — so there was nothing to save. Fixed by dropping `cache: pip`
  from the workflow rather than changing the install step; a concrete example of a
  class of failure ("green locally, red in CI") that's specific to steps CI runs but
  local development never touches.

- **Azure Monitor / Application Insights** (`backend/app/main.py`, `backend/app/
  config.py`): `configure_azure_monitor()` from the `azure-monitor-opentelemetry`
  package runs at startup when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set (no-op
  locally without it). This is Microsoft's OpenTelemetry Distro for Azure Monitor —
  one call configures the OpenTelemetry SDK to export to Application Insights *and*
  auto-instruments FastAPI, `requests`, and `psycopg2` via their standard OTel
  instrumentation packages (pulled in automatically as sub-dependencies), so request
  traces and DB spans need no per-route code changes. Called after
  `configure_logging()` specifically because it *adds* a handler to the `"app"`
  logger rather than replacing root's handler list, so stdout JSON logs and the
  Application Insights export both stay active. Verified against the real
  `appi-fifa26-dev` resource: ran the API locally with the live connection string,
  hit a few endpoints, confirmed every exported batch got `200` from the ingestion
  endpoint, and confirmed the requests were queryable via `az monitor app-insights
  query`. Now also confirmed live through the actual deployed Container App (§7) —
  the same `azure.monitor.opentelemetry` export traffic shows up in the real
  container's logs. No code changes were needed to make that happen once a real
  image shipped, since the app already read the connection string from the
  environment that `infra/container_apps.tf` was already passing in.

**CI/CD: the backend image build/push is now automated**, not manual. A new
`build-push-image` job in `.github/workflows/ci.yml` runs `az acr build` on every
push to `master` (after lint+test passes), authenticated via GitHub Actions OIDC —
a federated identity credential (Azure AD app registration, bootstrapped once via
`az ad`, `infra/README.md`) lets GitHub mint a short-lived token scoped to this
repo's `master` branch, which Azure AD exchanges for an access token that expires
with the job. No `AZURE_CLIENT_SECRET` exists anywhere. Deliberately still
build-and-push only — the Container App still only picks up a new image via a
manual `TF_VAR_api_image` + `terraform apply`.

Getting this working took four distinct, real failures, each root-caused rather
than worked around — a genuinely instructive sequence about how Azure RBAC for ACR
actually works:
1. The federated credential's `subject` used the plain
   `repo:<owner>/<repo>:ref:refs/heads/<branch>` format from Microsoft's docs, but
   GitHub actually presents a newer format with stable numeric IDs attached
   (`repo:<owner>@<id>/<repo>@<id>:ref:...`, surviving a repo/owner rename) — fixed
   by reading the exact subject out of the failed run's own logs rather than
   guessing.
2. `az acr build --registry <name>` without `--resource-group` resolves the
   registry via a subscription-wide name lookup needing broader permissions than a
   narrowly-scoped role has — fixed by passing `--resource-group` explicitly.
3. `AcrPush` (data-plane push/pull) doesn't include the management-plane actions
   `az acr build` also needs to read the registry resource, schedule an ACR Tasks
   run, and generate a build-context upload URL — each surfaced as a separate
   `AuthorizationFailed` in turn before switching to `Contributor` scoped to just
   the one registry resource (Microsoft's documented recommendation), kept
   alongside `AcrPush` since `Contributor` explicitly excludes `dataActions`.
4. Separately, the frontend CI job failed too — a latent bug from the static-export
   work, not this change: `next build` needs a real reachable backend at build time
   now, and CI had neither one running nor `NEXT_PUBLIC_API_URL` set. Fixed with a
   new repository *Variable* (not a Secret — it's a public URL).

Verified with an actual successful run, not just a clean `terraform apply`: all
three CI jobs passed together, and the resulting commit-SHA-tagged image was
confirmed present in ACR.

**Grafana now has a real, working dashboard on real telemetry**, not just an
untouched stock image. The Grafana Container App (`ca-fifa26-dev-grafana`) has
`min_replicas = 0` and no persistent disk, so any config set up by clicking around
its own UI would be wiped on the next scale-to-zero cycle — used Grafana's
"provisioning" feature instead (config files baked into a custom image,
`infra/grafana/Dockerfile` + `infra/grafana/provisioning/`, built via
`az acr build` the same way the backend image is) rather than a paid
persistent-disk add-on. Authenticated via its own user-assigned managed identity
(`id-fifa26-dev-grafana`, separate from the API's, scoped to only
`Log Analytics Reader` + `Key Vault Secrets User` + `AcrPull`) — no client secret,
no connection string. Admin password generated and landed in Key Vault, same
pattern as every other secret in this stack.

Four real issues surfaced while building this, each root-caused:
1. `azureAuthType: msi` in the datasource config alone wasn't enough — Grafana
   gates managed-identity auth behind a separate server-wide opt-in
   (`GF_AZURE_MANAGED_IDENTITY_ENABLED=true` + `GF_AZURE_MANAGED_IDENTITY_CLIENT_ID`
   for a user-assigned identity), confirmed from Grafana's own source rather than
   guessed.
2. Querying the raw Log Analytics workspace directly (what Grafana's datasource
   does) needs the underlying `App*`-prefixed table names, not the
   `requests`/`traces` aliases that only exist in Application Insights' own query
   surface.
3. The datasource's `uid` was never pinned, so Grafana would assign a new random
   one on every fresh provisioning pass — and since there's no persistent disk,
   *every* scale-to-zero-and-back is a fresh pass. Left unpinned, the next cold
   start would have silently broken any dashboard panel referencing it. Fixed
   before building the dashboard on top of it (`uid: azuremonitor`).
4. **A genuinely deeper finding**: what looked like "eventual consistency lag" in
   the previous session turned out to be a real bug once actually chased down —
   `AppRequests` (the table Azure Monitor's request-span data lands in) has
   **zero rows total, ever**, while `AppTraces`, `AppDependencies`, and every
   other table are populated normally (confirmed via `search * | summarize
   count() by $table` across the whole workspace). Root-caused and fixed in the
   next slice of work (see below) — the `BaseHTTPMiddleware` theory that seemed
   most plausible at the time turned out to be wrong.

**Dashboard built on data that actually exists**: at the time, `AppRequests` was
empty, so `infra/grafana/provisioning/dashboards/api-overview.json`'s 6 panels
(total requests, avg latency, 5xx count, request rate over time, latency
avg/p95, status code breakdown) query `AppTraces` instead, parsing the app's own
structured request-log line (`middleware.py`'s `"request method=%s path=%s
status=%s duration_ms=%.1f"`) via KQL's `parse` operator. Verified against real
data spanning multiple sessions: 10,469 parsed requests, 10,422 `200`s, 47
`404`s (root-path platform probes), zero `5xx` — confirmed by running the
actual panel queries through Grafana's `/api/ds/query`, not just checking the
dashboard loads. Still works today even after the fix below — switching these
panels to query `AppRequests` directly is optional cleanup, not required.

**The FastAPI request-span gap is now fixed.** The real cause was a Python
import-binding gotcha in `backend/app/main.py`, not `BaseHTTPMiddleware`:
`from fastapi import FastAPI` at the top of the file binds the *original* class
into that module's namespace at import time. `configure_azure_monitor()`'s
"auto-instrumentation" for FastAPI works by later reassigning the `fastapi`
module's `FastAPI` attribute to an instrumented subclass — but that reassignment
can't retroactively update a name already bound elsewhere. So `app = FastAPI(...)`
was silently constructing a plain, uninstrumented app the entire time, no error
raised. Fixed by calling `FastAPIInstrumentor.instrument_app(app)` explicitly on
the actual `app` instance right after creating it, sidestepping the import-order
trap entirely. `RequestContextMiddleware`'s rewrite to pure ASGI (from the
original, wrong hypothesis) was kept anyway — it's a legitimate, independently
correct improvement, matching Starlette's own documented guidance, even though
it turned out not to be the actual fix.

Verified twice, not assumed: first locally by patching
`AzureMonitorTraceExporter.export()` directly to print exactly what spans it
receives (found a genuine `SpanKind.SERVER` span for `GET /health`, confirming
the fix before any cloud round-trip), then by a real KQL query finding the exact
test requests in `AppRequests` — the first rows that table has ever had. Shipped
as `fifa26-api:v3` and re-verified against the actual deployed Container App:
real traffic through the live URL, confirmed queryable with matching URLs,
status codes, and durations.

**Still Phase 4**: switching the Grafana dashboard from the `AppTraces` workaround
to `AppRequests` directly (optional, the dashboard already works); automating the
*deploy* half on merge (`terraform apply` still a deliberate manual step, same
for the frontend build/upload); Sentry for frontend/backend error tracking; a
Groq token-usage dashboard (cost/FinOps angle even though the API itself is
free).

## 10. Status checklist

- [x] Repo scaffolding, `.gitignore`, directory structure
- [x] ETL: transform + load + schema, validated against real data, unit-tested
- [x] Backend: FastAPI skeleton, analytics endpoints, structured logging, request
      correlation IDs, global exception handling, health/readiness checks, unit-tested
- [x] Frontend: dashboard pages, charts, verified build + graceful no-backend fallback
- [x] Terraform: full minimal-cost Azure stack written
- [x] Architecture reference doc (this file)
- [x] Azure resources actually provisioned (23 resources, `rg-fifa26-dev` — see §7)
- [x] Phase 2: ML models trained + served (rating regressor, outcome classifier,
      archetype clustering) + frontend what-if predictor, verified end-to-end
- [x] Phase 3: GenAI RAG layer (Groq) — embeddings, retrieval, generation, rate
      limiting, player/team/match scouting reports + recaps, NL→chart backend
      (allowlisted spec) and frontend rendering, all built. Chart rendering and
      everything above is live on Azure; match recaps are verified locally only,
      not yet deployed (see §4.5)
- [ ] Phase 4: CI/CD, Azure Monitor wiring, Grafana, Sentry — lint+test CI,
      Application Insights wiring, the real backend + frontend both deployed and
      verified live end-to-end, automated backend image build/push via GitHub
      Actions OIDC, and a working Grafana dashboard on real telemetry (see §9) are
      all built; automating the deploy half on merge, `terraform apply` on merge,
      and Sentry not yet
