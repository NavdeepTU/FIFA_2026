# Working agreement for this project

**Pace: work in small increments, roughly 50-60 minutes of work at a time, not large
end-to-end sweeps.** Pick one focused task, finish and verify it, report back, then
stop rather than chaining many phases together in one go. This project is a learning
exercise for the user (cloud, ML, GenAI, monitoring) as much as it is a deliverable —
they want to follow along with what's happening, not review a huge diff after the
fact. When a task is clearly bigger than that window, break it into checkpoints and
pause between them rather than pushing through to the end.

Disk space on this machine is limited — check `df -h /` before installing new
dependencies (see `docs/ARCHITECTURE.md` §6).

## Reference docs (read these before making changes)

- `docs/ARCHITECTURE.md` — how the system fits together: data flow, tech stack
  rationale, repo layout, local dev, cloud deployment, current design decisions.
- `docs/project_scope.md` — the full feature set the finished project is meant to have.
- `docs/project_status.md` — what's actually built and verified right now. Update this
  whenever a task completes.
- `/Users/navdeep/.claude/plans/toasty-honking-kettle.md` — the original phased build
  plan and the reasoning behind cost/tooling decisions (Azure, Groq, no local Docker).

## Communication & design preferences

- Keep responses in plain, simple language. Only go technical/in-depth if the user
  specifically asks for that level of detail.
- The frontend must be elegant, aesthetic, modern, and as user-friendly as possible —
  not just functional.

## Conventions already established

- No Docker, no local Postgres, no local Terraform/Azure CLI — installed dependencies
  stay minimal given disk constraints; cloud tooling runs via Cloud Shell / GitHub
  Actions instead.
- Python: one shared venv at `backend/.venv` for both `etl/` and `backend/`. Lint with
  `make lint` (ruff, configured in `pyproject.toml`). Test with `make test`.
- ML training scripts (`backend/ml/train_*.py`) exclude any column found to correlate
  suspiciously highly with a target (see the leakage note in `docs/ARCHITECTURE.md` §8)
  — check correlations before trusting a feature, don't assume the dataset is clean.
- Only commit to git when explicitly asked.
