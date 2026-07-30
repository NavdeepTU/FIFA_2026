---
description: Randomly deep-dive one piece of the codebase for interview prep (read-only, no changes)
allowed-tools: Read, Bash, Grep
---

This command is **read-only interview-prep only**. Do not edit, create, or delete any
files, and do not run anything beyond what's needed to pick a target and read/search the
codebase. Your job this turn is to teach, not to build.

## 1. Build the candidate pool

List tracked source files with `git ls-files` (this naturally skips `.venv/`,
`node_modules/`, build artifacts, and anything else already gitignored). Filter to real
code and keep it broad across the whole stack — Python (`etl/`, `backend/`, including
tests), TypeScript/TSX (`frontend/src/`), SQL (`etl/schema.sql`), and infrastructure
(`infra/*.tf`).

Exclude trivial/non-conceptual files that wouldn't make an interesting deep-dive: empty
`__init__.py`, lockfiles/manifests (`package-lock.json`, `.terraform.lock.hcl`,
`requirements*.txt`), binary/generated assets (`favicon.ico`, anything under
`backend/ml/artifacts/`), and pure config with no logic (`.gitignore`, `.env.example`).
Everything else is fair game, including tests — how something is tested is legitimate
interview material too.

## 2. Pick one at random

Use a real random selection (e.g. `python3 -c "import random; ..."` over the filtered
list) — don't let recency or "what we just talked about" bias the pick. If the file
picked is very short or thin (e.g. a small config module), that's fine: explain the
concept it represents rather than padding with unrelated context.

## 3. Research it properly before writing anything

- Read the full file.
- `Grep` for where it's imported/called from, so you understand its role in the system,
  not just its contents in isolation.
- Check whether `docs/ARCHITECTURE.md`, `docs/project_status.md`, or comments in the
  file itself already document *why* it was built this way — this project has a lot of
  real "why not X instead" reasoning already written down (inline comments, ADR-style
  notes). Use and cite that genuine history rather than inventing generic reasoning.

## 4. Write the deep-dive

Structure the answer with these sections, as clear prose (not fragment-y bullet dumps) —
this should read like a well-written mini technical article, the kind of explanation
that actually builds understanding rather than a dry summary:

- **What it is** — one paragraph, plain language, what this code does and where it
  sits in the overall system (reference the file path).
- **How it's implemented** — walk through the actual mechanics: key functions, the
  data flow through it, any non-obvious logic. Specific enough that reading this
  alone would let someone explain the code without having it open.
- **Concept(s) it demonstrates** — name the underlying CS/engineering concept(s)
  explicitly and by their real name (e.g. "dependency injection," "fixed-window rate
  limiting," "idempotent upsert," "vector similarity search," "Infrastructure as
  Code," "the strategy pattern") so there's real vocabulary to reach for in an
  interview, not just a vague gesture at "good practice."
- **Why this approach, and what else was considered** — pull genuine alternatives
  already reasoned about in this project's own history where they exist, plus 1-2
  additional industry-standard alternatives if worth knowing, each with an honest
  trade-off (not "the alternative is worse" — say specifically worse *how*, and in
  what situation it would actually be the better choice).
- **What could be better next time** — a candid, specific critique. Prefer a real,
  already-known limitation (this project documents several honestly, e.g. in-memory
  state that won't survive multiple instances, no integration tests against a real
  DB, row-by-row writes instead of batched ones) over a generic "add more tests."
- **Likely interview questions** — 2-3 concrete questions this code could prompt in
  an interview, each with a one-line pointer to the answer you'd give.

## 5. Close out

End with one line naming the file covered, and invite the user to run the command
again for a different random pick.
