# Working agreement for this project

**Pace: work in small increments, roughly 50-60 minutes of work at a time, not large
end-to-end sweeps.** Pick one focused task, finish and verify it, report back, then
stop rather than chaining many phases together in one go. This project is a learning
exercise for the user (cloud, ML, GenAI, monitoring) as much as it is a deliverable —
they want to follow along with what's happening, not review a huge diff after the
fact. When a task is clearly bigger than that window, break it into checkpoints and
pause between them rather than pushing through to the end.

Disk space and cost were tight constraints early on and shaped several decisions below
(Cloud Shell instead of local Azure CLI, no local Docker/Postgres, free-tier-only Azure
SKUs). Both have eased: the user now has room to install local tooling and is open to
paid Azure resources where they genuinely help the learning goal, not just free tier.
Still worth a quick `df -h /` sanity check before a large install as good practice, but
it's no longer a hard blocker.

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

- Local Azure CLI and Terraform are now fine to install (previously avoided only for
  disk-space reasons, using Cloud Shell instead). Docker and a local Postgres install
  stay the default to avoid — not a disk constraint anymore, just no clear need so far;
  revisit if that changes.
- Azure resources can include paid-tier SKUs where they meaningfully help the learning
  goal, not just always-free/free-tier options — but confirm with the user before
  provisioning anything with a real ongoing cost. "Applied deliberately, not
  automatically" still holds regardless of tier.
- Python: one shared venv at `backend/.venv` for both `etl/` and `backend/`. Lint with
  `make lint` (ruff, configured in `pyproject.toml`). Test with `make test`.
- ML training scripts (`backend/ml/train_*.py`) exclude any column found to correlate
  suspiciously highly with a target (see the leakage note in `docs/ARCHITECTURE.md` §8)
  — check correlations before trusting a feature, don't assume the dataset is clean.
- Only commit to git when explicitly asked.

## AI-assisted development & interview readiness

- This project is also for interview preparation, not just building a working application.
- Prefer teaching over simply generating code.
- Whenever introducing a new library, framework, language feature, design pattern, cloud service, or architectural concept:
  - Explain what problem it solves.
  - Explain why it was chosen.
  - Mention 2–3 common alternatives and their trade-offs.
  - Explain where it fits into the application's architecture.
- If multiple reasonable approaches exist, recommend one and briefly justify the decision.
- Avoid introducing unnecessary dependencies. Reuse existing libraries whenever practical.
- Assume I may later need to explain every important technology in a senior software engineering, GenAI, or data science interview.
- If the implementation uses advanced language features or framework-specific concepts, explain them the first time they appear.
- Whenever you introduce a new dependency, briefly explain:
  - Why it is needed.
  - Whether it is an industry standard or just one possible choice.
  - The minimum knowledge I should have to discuss it confidently in an interview.
- After completing a meaningful feature or milestone, include a short section titled **Interview & Revision Notes** containing:
  - Technologies introduced
  - Why each technology was chosen
  - Key architecture decisions
  - Common interview questions related to the implementation
  - Topics I should study further to gain deeper understanding
- Keep explanations concise and practical unless I explicitly ask for a deep dive.
- At the end of every implementation, assume I may be asked to explain this work in an interview. Proactively point out any technologies, design decisions, or code that I should understand before I claim experience with them.
- Do not optimize only for getting the feature working. Optimize for production-quality engineering. Explain important trade-offs, scalability concerns, security implications, performance considerations, and testing strategy whenever they are relevant.