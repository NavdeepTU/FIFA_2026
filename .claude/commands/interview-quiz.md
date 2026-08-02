---
description: Randomly deep-dive one piece of the codebase for interview prep; appends a formatted entry (with an architecture diagram) to docs/interview_quiz_log.html
allowed-tools: Read, Bash, Grep, Write, Edit
---

This command researches and teaches. The **only** file it may create or modify is the
HTML log at `docs/interview_quiz_log.html`, written per the template in step 5. Do not
edit, create, or delete any other file, and do not run anything beyond what's needed to
pick a target, research it, and write that one log file. Do not `git add`/`git commit`
anything — only commit when explicitly asked (see CLAUDE.md).

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
  not just its contents in isolation — this also feeds the architecture diagram in
  step 4.
- Check whether `docs/ARCHITECTURE.md`, `docs/project_status.md`, or comments in the
  file itself already document *why* it was built this way — this project has a lot of
  real "why not X instead" reasoning already written down (inline comments, ADR-style
  notes). Use and cite that genuine history rather than inventing generic reasoning.

## 4. Write the deep-dive

**Keep every section short and in plain, everyday language.** This is the most important
rule in this step: 2-4 short sentences per section, not a technical essay. Write like
you're explaining it to a smart friend who isn't a programmer — avoid jargon where a
plain word works just as well, avoid stacking multiple technical terms in one sentence,
and skip background explanation of things not central to the point. Where a real
technical term is genuinely necessary (interview vocabulary matters — see "Concept(s)"
below), use it but briefly gloss what it means in plain words right next to it, don't
assume it's already understood. Shorter and clearer beats thorough and dense. These
sections become the `<section class="block sec-*">` blocks in the HTML template below,
in this order:

- **What it is** (`sec-what`) — 2-3 short sentences, plain language: what this code does
  and where it sits in the overall system (reference the file path).
- **How it's implemented** (`sec-how`) — 3-4 short sentences on the key steps and data
  flow. Enough that someone could describe roughly what happens without having the file
  open — not a line-by-line walkthrough.
- **Architecture visualization** (`sec-arch`) — a Mermaid diagram (flowchart or sequence
  diagram, whichever fits better) showing this file's place in the system: what
  calls/imports it, what it calls out to (DB, other modules, external services), and
  where it sits in the request/data flow — built from what you found via `Grep` in step
  3, not invented. Use these fixed class colors so every entry in the log stays visually
  consistent (put this `classDef` block in every diagram):

  ```
  classDef frontend fill:#38bdf8,stroke:#0369a1,color:#0f172a;
  classDef backend fill:#a78bfa,stroke:#5b21b6,color:#0f172a;
  classDef ml fill:#fbbf24,stroke:#92400e,color:#0f172a;
  classDef data fill:#34d399,stroke:#065f46,color:#0f172a;
  classDef infra fill:#fb923c,stroke:#9a3412,color:#0f172a;
  classDef external fill:#f87171,stroke:#7f1d1d,color:#0f172a;
  classDef target fill:#2dd4bf,stroke:#134e4a,color:#0f172a,stroke-width:3px;
  ```

  Assign the node for the file being covered the `target` class; assign every other node
  the class matching its layer (frontend/backend/ml/data/infra/external). Keep the
  diagram focused — the file's direct neighbors, not the whole system. Keep node labels
  short and in plain words (e.g. "loads data into the database" rather than a function
  signature).
- **Concept(s) it demonstrates** (`sec-concept`) — 1-2 sentences. Name the real
  CS/engineering term(s) (e.g. "dependency injection," "fixed-window rate limiting,"
  "idempotent upsert," "vector similarity search," "Infrastructure as Code," "the
  strategy pattern") since that's genuine interview vocabulary — but follow each term
  with a short plain-English gloss of what it actually means.
- **Why this approach, and what else was considered** (`sec-why`) — 2-3 short sentences.
  Pull a genuine alternative already reasoned about in this project's own history where
  one exists, plus at most one more industry-standard alternative if worth knowing, with
  a one-line honest trade-off (not "the alternative is worse" — say specifically worse
  *how*, and when it would actually be the better choice).
- **What could be better next time** (`sec-better`) — 1-2 short sentences, one candid,
  specific critique. Prefer a real, already-known limitation (this project documents
  several honestly, e.g. in-memory state that won't survive multiple instances, no
  integration tests against a real DB, row-by-row writes instead of batched ones) over a
  generic "add more tests."
- **Likely interview questions** (`sec-questions`) — 2-3 concrete questions this code
  could prompt in an interview, each with a one-line pointer (not a paragraph) to the
  answer you'd give. Render as an `<ol>`.

## 5. Render into the HTML log

Output file: `docs/interview_quiz_log.html`. It's a running log, newest entry first, so
every run adds one entry rather than replacing the file.

**Compute an entry id**: slugify the file path (non-alphanumeric → `-`) and prefix with
today's date, e.g. `backend/ml/train_rating_model.py` on 2026-08-02 becomes
`entry-2026-08-02-backend-ml-train-rating-model-py`.

**If `docs/interview_quiz_log.html` does not exist**, create it with `Write` using the
full skeleton below, with your one entry already placed inside `<div id="entries">` and
its matching `<li>` already placed inside `<ol id="toc-list">`.

**If it already exists**, use `Read` then `Edit` to insert — do not touch any existing
entries or the CSS:
- A new `<li><a href="#{id}">{file path}</a> <span class="meta">— {date}</span></li>`
  as the *first* child of `<ol id="toc-list">`.
- A new `<article class="entry" id="{id}">...</article>` as the *first* child of
  `<div id="entries">`.

HTML skeleton (use verbatim for the surrounding page; only the TOC list and entries
list grow over time):

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Interview Quiz Log — FIFA World Cup 26</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  :root {
    --bg: #0f172a; --card: #1e293b; --card-border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --code-bg: #0b1222;
    --what: #38bdf8; --how: #a78bfa; --arch: #34d399; --concept: #fbbf24;
    --why: #fb923c; --better: #f87171; --questions: #2dd4bf;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
    line-height: 1.6; }
  header.page-header { padding: 2rem 1.5rem 1rem; border-bottom: 1px solid var(--card-border); }
  header.page-header h1 { margin: 0 0 .25rem; font-size: 1.5rem; }
  header.page-header p { margin: 0; color: var(--muted); font-size: .9rem; }
  main { width: 100%; margin: 0; padding: 1.5rem 2.5rem 3rem; }
  nav.toc { background: var(--card); border: 1px solid var(--card-border);
    border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 2rem; }
  nav.toc h2 { font-size: .95rem; text-transform: uppercase; letter-spacing: .05em;
    color: var(--muted); margin: 0 0 .5rem; }
  nav.toc ol { margin: 0; padding-left: 1.25rem; }
  nav.toc a { color: var(--what); text-decoration: none; }
  nav.toc a:hover { text-decoration: underline; }
  nav.toc .meta { color: var(--muted); font-size: .85rem; }
  article.entry { background: var(--card); border: 1px solid var(--card-border);
    border-radius: 12px; padding: 1.5rem 1.75rem; margin-bottom: 2.5rem;
    display: grid; grid-template-columns: 1fr 1fr; gap: 0 2.5rem; }
  article.entry > header { grid-column: 1 / -1; margin-bottom: 1.25rem; }
  article.entry > header h2 { margin: 0 0 .25rem; font-size: 1.25rem; font-family: monospace; }
  article.entry > header .meta { color: var(--muted); font-size: .85rem; }
  section.block { border-left: 4px solid var(--muted); padding: .25rem 0 .25rem 1rem;
    margin-bottom: 1.5rem; }
  section.sec-arch { grid-column: 1 / -1; }
  section.block h3 { margin: 0 0 .5rem; font-size: 1rem; }
  section.block p { margin: 0 0 .75rem; }
  section.block p:last-child { margin-bottom: 0; }
  @media (max-width: 760px) {
    article.entry { grid-template-columns: 1fr; }
  }
  section.sec-what    { border-color: var(--what); }    section.sec-what h3    { color: var(--what); }
  section.sec-how      { border-color: var(--how); }     section.sec-how h3     { color: var(--how); }
  section.sec-arch     { border-color: var(--arch); }    section.sec-arch h3    { color: var(--arch); }
  section.sec-concept  { border-color: var(--concept); } section.sec-concept h3 { color: var(--concept); }
  section.sec-why      { border-color: var(--why); }     section.sec-why h3     { color: var(--why); }
  section.sec-better   { border-color: var(--better); }  section.sec-better h3  { color: var(--better); }
  section.sec-questions{ border-color: var(--questions);} section.sec-questions h3 { color: var(--questions); }
  code, pre { font-family: "SF Mono", Menlo, Consolas, monospace; }
  code { background: var(--code-bg); padding: .1rem .35rem; border-radius: 4px; font-size: .85em; }
  pre { background: var(--code-bg); padding: 1rem; border-radius: 8px; overflow-x: auto; }
  ul, ol { padding-left: 1.25rem; }
  .mermaid { background: var(--code-bg); border-radius: 8px; padding: 1rem; }
  a { color: var(--what); }
</style>
</head>
<body>
<header class="page-header">
  <h1>Interview Quiz Log</h1>
  <p>FIFA World Cup '26 project — accumulated deep-dives from <code>/interview-quiz</code>, newest first.</p>
</header>
<main>
  <nav class="toc">
    <h2>Entries</h2>
    <ol id="toc-list">
      <!-- new <li> entries inserted here, newest first -->
    </ol>
  </nav>
  <div id="entries">
    <!-- new <article> entries inserted here, newest first -->
  </div>
</main>
<script>
  mermaid.initialize({
    startOnLoad: true,
    theme: 'dark',
    themeVariables: {
      background: '#0b1222', primaryColor: '#1e293b', primaryTextColor: '#e2e8f0',
      primaryBorderColor: '#334155', lineColor: '#64748b',
      secondaryColor: '#334155', tertiaryColor: '#0f172a'
    }
  });
</script>
</body>
</html>
```

Entry template (fill in `{file path}`, `{date}`, `{id}`, and the section bodies from
step 4):

```html
<article class="entry" id="{id}">
  <header>
    <h2>{file path}</h2>
    <div class="meta">{date}</div>
  </header>
  <section class="block sec-what">
    <h3>What it is</h3>
    <p>...</p>
  </section>
  <section class="block sec-how">
    <h3>How it's implemented</h3>
    <p>...</p>
  </section>
  <section class="block sec-arch">
    <h3>Architecture visualization</h3>
    <div class="mermaid">
flowchart LR
  ...
    </div>
  </section>
  <section class="block sec-concept">
    <h3>Concept(s) it demonstrates</h3>
    <p>...</p>
  </section>
  <section class="block sec-why">
    <h3>Why this approach, and what else was considered</h3>
    <p>...</p>
  </section>
  <section class="block sec-better">
    <h3>What could be better next time</h3>
    <p>...</p>
  </section>
  <section class="block sec-questions">
    <h3>Likely interview questions</h3>
    <ol>
      <li>...</li>
    </ol>
  </section>
</article>
```

## 6. Close out

End with one line naming the file covered, confirm the entry was added to
`docs/interview_quiz_log.html` (open it in a browser to view — the Mermaid diagrams
render client-side via the CDN script), and invite the user to run the command again
for a different random pick.
