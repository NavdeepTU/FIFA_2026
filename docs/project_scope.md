# Project Scope

What the finished project is meant to contain. This is the target — see
`project_status.md` for what's actually built right now, and `ARCHITECTURE.md` for how
the pieces fit together.

## 1. Data pipeline

- ETL from the raw FIFA World Cup 2026 CSV into a normalized Postgres schema
  (`teams`, `players`, `matches`, `player_match_stats`) plus materialized views for
  standings, player leaderboards, and tournament progression.
- Idempotent, re-runnable end to end.

## 2. Backend API (FastAPI)

- **Analytics**: team standings, tournament progression, player/team leaderboards
  (goals, assists, rating, tackles, saves), player and team profile pages, match listings.
- **ML predictions**: player rating "what-if" predictor, match outcome (W/D/L)
  predictor, player archetype/playstyle lookup.
- **GenAI**: a chat endpoint answering natural-language questions about the tournament,
  grounded in the real data (RAG, not free-form LLM guessing); a natural-language →
  chart feature; auto-generated player scouting reports / match recaps.
- Structured logging, request correlation IDs, consistent error responses, liveness +
  readiness health checks.

## 3. Frontend (Next.js dashboard)

- Overview page: tournament stat tiles, standings, top scorers, progression by stage.
- Player explorer: leaderboard with metric selection, individual player profile pages
  with full match log.
- Team explorer: standings table, individual team profile pages with roster.
- Rating predictor page: live what-if panel against the ML model.
- GenAI chat assistant: ask questions about the tournament in plain English.
- Charts throughout follow a validated, accessible color system (the `dataviz` skill's
  palette) — consistent light/dark styling, legends, tooltips.

## 4. ML models

- Player rating regressor (trained on genuine box-score actions, not derived/leaky
  composite scores).
- Match outcome classifier (W/D/L from team-aggregated match stats).
- Player archetype clustering (unsupervised playstyle groups from per-90 stats).
- Every model's honest performance is documented, not just its existence — including
  where the signal turns out to be weak.

## 5. GenAI layer

- RAG assistant over player/team season summaries (pgvector embeddings + Groq for
  generation), answering natural-language questions with numbers pulled from the real
  database, not hallucinated.
- Constrained natural-language → chart feature (an allowlisted query spec the backend
  validates and executes — never LLM-generated SQL run directly).
- Auto-generated, cached scouting reports / match recaps.
- Rate limiting and token-usage logging on every GenAI endpoint.
- Built behind a provider-agnostic interface (Groq now; swappable to another LLM
  provider later without a rewrite).

## 6. Cloud infrastructure (Azure, via Terraform)

- Resource group, Postgres Flexible Server (B1MS, free-tier eligible, `pgvector`
  enabled), Blob Storage (data lake layers + static frontend hosting, no CDN),
  Key Vault (secrets via managed identity, not env vars in state), Container Apps
  (API + self-hosted Grafana, consumption plan / always-free grant).
- An actual Azure Budget + cost alert (not just careful SKU sizing) as the real
  spend safety net.
- Applied deliberately (not automatically) given cost sensitivity — see the working
  agreement in the root `CLAUDE.md`.

## 7. CI/CD

- GitHub Actions: lint + test on every PR; build/push Docker images and
  `terraform apply` on merge, authenticated via OIDC federated credentials (no
  long-lived Azure secrets in GitHub).

## 8. Observability

- Azure Monitor + Application Insights for logs/metrics/traces from the deployed API.
- Self-hosted Grafana dashboards on top (chosen over paid Azure Managed Grafana).
- Sentry for frontend + backend error tracking.
- A Groq token-usage / cost dashboard (FinOps angle, even though the API itself is free).

## 9. Quality / engineering practices

- pytest suites for the ETL transform logic and the backend API (unit-tested against
  mocked dependencies; a separate integration suite against a real ephemeral Postgres
  is a CI-only concern).
- ruff linting.
- A living architecture reference (`ARCHITECTURE.md`) kept up to date as the system changes.

## Explicitly out of scope (for now)

- User authentication / accounts.
- Real-time/live match data (the dataset is a static, synthetic snapshot).
- Mobile app (web dashboard only).
- Multi-tenant or multi-tournament support — this is scoped to the one dataset.
