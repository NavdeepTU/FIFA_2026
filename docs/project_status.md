# Project Status

Last updated: 2026-07-29. Update this file whenever a task completes or scope changes —
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
- `/chat/*`: stubbed (Phase 3, not built yet).
- Structured JSON logging with per-request correlation IDs (`X-Request-ID`), a global
  exception handler with a consistent, non-leaky error shape, `/health` (liveness) vs
  `/health/ready` (checks Postgres connectivity).
- 13 pytest tests (`backend/tests/`), DB and model layers mocked — unit tests, not
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
  team standings + profile (`/teams`, `/teams/[team]`), live rating predictor (`/predict`).
- Charts styled to the `dataviz` skill's validated palette (light/dark, CSS custom
  properties by role).
- Verified: type-checks clean, builds clean, renders correctly with a graceful
  "API unreachable" fallback when the backend isn't running, and end-to-end against a
  live local backend with real trained models.

### Infrastructure (Terraform, azurerm)
- Full minimal-cost stack written: resource group, Postgres Flexible Server (B1MS),
  Blob Storage (data lake + static site, no CDN), Key Vault, Container Apps
  (API + self-hosted Grafana), Azure Budget + cost alert.
- **Not yet applied** — no resources actually exist in Azure yet. Blocked on the user
  running `az login` (via Cloud Shell, to avoid installing the CLI locally) and
  providing an alert email + region confirmation.

### Docs / process
- `docs/ARCHITECTURE.md` — living system reference.
- `docs/project_scope.md` — full target feature set.
- This file.
- Root `CLAUDE.md` — working agreement (50-60 min task sizing, disk-space discipline,
  conventions).

## Not started yet

- **Phase 3 (GenAI)**: RAG chat endpoint, pgvector embeddings, natural-language → chart,
  auto-generated reports. Schema already has a `player_embeddings` table ready
  (`etl/schema.sql`) but nothing populates or queries it yet.
- **Phase 4 (observability/CI/CD)**: GitHub Actions workflows, Azure Monitor/App
  Insights wiring (env var is already passed to the container, just unused), Grafana
  dashboards, Sentry, load testing.
- **Azure provisioning**: `terraform apply` hasn't been run. Everything currently runs
  locally only.

## Known limitations / honest caveats

- The dataset's match outcomes and tournament totals are close to random — this is
  called out rather than hidden, and shapes what claims the ML section can honestly make.
- No integration tests against a real Postgres yet (only mocked-DB unit tests).
- No authentication anywhere (out of scope — see `project_scope.md`).
