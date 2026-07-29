---
description: Sync docs with what changed this session, commit, and push to GitHub
allowed-tools: Bash, Read, Edit, Grep
---

Wrap up the current working session. Do these steps in order.

## 1. Establish ground truth on what actually changed

Run `git status` and `git diff HEAD` (and check for untracked files) to see exactly
what's changed since the last commit — this is the ground truth for "what happened
this session," not a recollection of the conversation. If the working tree is clean
(nothing to commit), say so and skip straight to step 5 (do not create an empty commit,
do not push if there's nothing new).

## 2. Update the docs to match reality

Cross-reference the actual diff against:

- `docs/project_status.md` — move newly-completed work into "Done and verified" (with
  the same level of honesty already established there — call out weak results or
  limitations rather than glossing over them), update "Not started yet" if something
  moved out of it, and update the "Last updated" date at the top.
- `docs/ARCHITECTURE.md` — update if the diff changed the system design, data flow,
  tech stack, or a documented decision (e.g. a new component, a changed schema, a new
  service). Don't touch it if the diff was purely internal (bug fixes, refactors) with
  no architectural implication.
- `docs/project_scope.md` — only touch this if the *target* feature set itself changed
  (scope added/removed/reworded), which should be rare. Most sessions won't need this.
- Root `CLAUDE.md` — only touch if a new working convention was established this
  session (like the pacing rule already in there), not for routine progress.

Skip any file that doesn't need a change rather than editing for the sake of it. After
editing, briefly state which docs you updated and why.

## 3. Review before staging

Run `git status` again and look at the actual diff of anything unexpected (new
untracked files, anything that could contain a secret or credential despite an innocuous
name, unusually large files). Flag anything suspicious to the user before staging it
rather than silently including it. Do not run `git add -A`/`git add .` without having
looked at what it would pick up.

## 4. Commit

Stage the relevant files by name. Write a commit message following this repo's existing
style (see `git log`): a short summary line focused on *why*, not a changelog of every
file. End the message with the required trailer:

```
Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

Never amend an existing commit, never force anything, never skip hooks.

## 5. Push to GitHub

Remote: `git@github.com:NavdeepTU/FIFA_2026.git`.

- Check if `origin` is already configured (`git remote -v`). If not, add it:
  `git remote add origin git@github.com:NavdeepTU/FIFA_2026.git`.
- Push the current branch, setting upstream if it isn't tracking yet
  (`git push -u origin <branch>` on the first push, `git push` after that).
- Never force-push. If the push is rejected (e.g. the remote has commits this branch
  doesn't, or the repo doesn't exist yet on GitHub), stop and report the exact error to
  the user rather than working around it — this needs a human decision, not an
  automatic retry with `--force`.

## 6. Report

End with a short summary: what was committed (one line), whether docs were updated and
which ones, and the push result (success + commit URL if you can construct one from the
remote, or the exact error if it failed).
