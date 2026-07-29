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

  infra/ — Terraform (azurerm). Provisions everything above. Not yet applied — see §7.
```

## 3. Repository layout

| Path | Purpose |
|---|---|
| `data/raw/` | Source CSV + dataset info. Gitignored (large, not committed) — see §4 for why. |
| `etl/` | `transform.py` (pure pandas, no I/O — testable), `load.py` (Postgres load, idempotent), `schema.sql` (DDL + materialized views). |
| `backend/app/` | FastAPI app: `main.py` (app wiring), `config.py` (env-based settings), `db.py` (SQLAlchemy engine), `routers/` (`analytics.py`, `predict.py`, `chat.py`). |
| `backend/ml/` | Offline training scripts + saved model artifacts (Phase 2). |
| `backend/genai/` | RAG layer (Phase 3): `embeddings.py` (summary text + fastembed wrapper), `generate_embeddings.py` (populates `player_embeddings`, offline), `llm.py` (provider-agnostic `generate_answer()`, Groq today). |
| `backend/tests/` | pytest suite for the API. |
| `etl/tests/` | pytest suite for the transform logic. |
| `frontend/src/app/` | Next.js pages (App Router): `/`, `/players`, `/players/[id]`, `/teams`, `/teams/[team]`. |
| `frontend/src/components/` | Shared UI: `DataTable`, `StatTile`, `BarChartCard`, `Nav`, `MetricSelect`. |
| `frontend/src/lib/api.ts` | Typed fetch client for the backend API. |
| `infra/` | Terraform: `main.tf` (resource group), `postgres.tf`, `storage.tf`, `keyvault.tf`, `container_apps.tf`, `budget.tf`. |
| `.github/workflows/` | CI/CD (Phase 4). |
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
   three materialized views. Safe to re-run end-to-end at any time.
3. **Why compute our own aggregates instead of using the CSV's tournament columns**:
   the source's `total_goals_tournament` / `tournament_rating` etc. don't behave as true
   cumulative running totals (checked directly against the data — a player's
   `total_minutes_tournament` fluctuates non-monotonically across their match rows).
   The materialized views (`mv_player_tournament_stats`, `mv_team_standings`,
   `mv_tournament_progression`) instead `SUM`/`AVG` the granular per-match stats, which
   are internally consistent.

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

**Embeddings built**: `backend/genai/generate_embeddings.py` populates
`player_embeddings` from `mv_player_tournament_stats` — one natural-language summary
per player, embedded locally via `fastembed` (`BAAI/bge-small-en-v1.5`, ONNX, 384-dim).
Local rather than a hosted API deliberately: Groq has no embeddings endpoint, and this
avoids a second API key/cost just for retrieval — the interface (`embed_texts()`) is
still small enough to swap later if needed. Idempotent, re-run via `make genai-embed`
after every ETL load.

**Retrieval built**: `POST /chat/retrieve` (`backend/app/routers/chat.py`) embeds an
incoming query with the same `embed_texts()` used to build the embeddings, then does a
pgvector `<->` distance search joined against `players` for the nearest summaries.
Using the same embedding model for queries and documents isn't a style choice — vector
similarity is only meaningful if both sides came from the same model. This makes
`fastembed` a serving-time dependency of the API now, not just an offline-script one
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

**Not yet built**: NL→chart, auto-generated/cached reports, rate limiting on the GenAI
endpoints, and team-level embeddings (`player_embeddings` is player-only per
`schema.sql` — there's no `team_embeddings` table, so team-level questions have nothing
to retrieve against yet).

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

Not yet applied. See `infra/README.md` for the exact bootstrap steps (Cloud Shell login,
remote state bootstrap, `terraform apply`). Summary of the cost posture: every resource
is sized to the free tier / always-free grant (Postgres B1MS, Container Apps consumption
plan, Blob Storage under 5GB, no CDN), and an actual Azure Budget + alert
(`infra/budget.tf`) is the real backstop — not just careful sizing.

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

**Still Phase 4**: Azure Monitor + Application Insights wired to the deployed
Container App (the `APPLICATIONINSIGHTS_CONNECTION_STRING` env var is already passed
in `infra/container_apps.tf`, just not consumed by the app yet), self-hosted Grafana
dashboards on top, Sentry for frontend/backend error tracking, and a Groq token-usage
dashboard (cost/FinOps angle even though the API itself is free).

## 10. Status checklist

- [x] Repo scaffolding, `.gitignore`, directory structure
- [x] ETL: transform + load + schema, validated against real data, unit-tested
- [x] Backend: FastAPI skeleton, analytics endpoints, structured logging, request
      correlation IDs, global exception handling, health/readiness checks, unit-tested
- [x] Frontend: dashboard pages, charts, verified build + graceful no-backend fallback
- [x] Terraform: full minimal-cost Azure stack written
- [x] Architecture reference doc (this file)
- [ ] Azure resources actually provisioned (blocked on your `az login` / Cloud Shell step)
- [x] Phase 2: ML models trained + served (rating regressor, outcome classifier,
      archetype clustering) + frontend what-if predictor, verified end-to-end
- [ ] Phase 3: GenAI RAG layer (Groq)
- [ ] Phase 4: CI/CD, Azure Monitor wiring, Grafana, Sentry
