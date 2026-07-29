---
description: Recommend the next 50-60 minute task for this project (read-only, no changes)
allowed-tools: Read
---

Read these three files in full before responding:

- @CLAUDE.md
- @docs/project_scope.md
- @docs/project_status.md

This command is **read-only planning/orientation only**. Do not edit any files, run any
other tools, install anything, or take any action beyond reading those three files. Your
job this turn is to recommend, not to do.

## What to produce

1. **One-line status**: where the project stands right now, from `project_status.md`.
2. **The single recommended next task** — the smallest next slice of an unstarted or
   partially-built item from `project_scope.md` that isn't yet marked done in
   `project_status.md`, sized to roughly 50-60 minutes of focused work per the pacing
   rule in `CLAUDE.md`. Prefer finishing a partially-started area over starting a
   brand-new one, and prefer the task that unblocks the most follow-on work (e.g. a
   blocked prerequisite) when a few options are otherwise equally valid.
3. **Why this one**: a short reason this is the right-sized next increment given what's
   already done — not a bigger multi-part sweep, not something trivially small.
4. If genuinely useful, name 1-2 reasonable alternatives in a single line, but be
   decisive about the top pick rather than listing options neutrally.

End by asking the user whether to proceed with the recommended task, and then wait for
their reply. Do not start the task, and do not call ExitPlanMode or any planning tool —
just state the recommendation and stop.
