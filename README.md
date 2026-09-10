# QA Agent Pipeline

A project-agnostic set of QA agents for [Claude Code](https://docs.claude.com/en/docs/claude-code),
covering the workflow from "new codebase" through "release closed and notes shipped." Clone it
into any project and use it as-is — no project-specific setup beyond dropping in your bug report
template.

This README is written for someone using Claude Code and this pipeline for the first time. If
you already know Claude Code well, skip to [Getting started](#getting-started).

## What this actually is

It's a folder of **prompts** (plain instructions, one per QA task — "analyze this codebase",
"write test cases from this plan", etc.) plus a small script that turns those prompts into
Claude Code subagents. You open Claude Code in your project, and instead of typing a long
explanation every time you want QA work done, you just say "use the test-planner agent" and it
follows the pre-written instructions, reading and writing files in an `output/` folder as it
goes. Nothing here edits your source code — every agent only reads your code and writes
Markdown/CSV reports.

## Why this exists

Manual QA on real releases follows a repeatable shape: understand the codebase, understand
what changed, work out what's at risk, write test cases, run them, investigate failures, file
bugs, close the cycle. This repo turns each of those steps into a small, focused AI agent —
not one giant agent trying to do everything.

**Design principles:**
- **One agent, one job.** Each agent does one stage and writes one kind of output file.
- **Explicit invocation, human gates between stages.** Nothing auto-chains. You review each
  output file before moving to the next stage — especially the test plan, which should be
  reviewed and approved before test cases are written from it.
- **Read-only on source code.** No agent here edits your codebase. They read, analyze, and
  write reports/docs under `output/`.
- **Single source of truth.** Each agent's real instructions live in one file under `prompts/`.
  The Claude Code agent/command files are generated from that one file, so you only ever edit a
  prompt in one place.
- **General-purpose.** Nothing here is hardcoded to a specific project, domain, or language.
  `context-analyzer` builds project-specific knowledge at runtime; every other agent reads that
  instead of assuming anything.

## Requirements

- **[Claude Code](https://docs.claude.com/en/docs/claude-code)** installed and logged in. If you
  can run `claude` in a terminal and it opens a chat, you're set. If not, follow the install
  instructions at that link first — this README assumes Claude Code already works.
- **git**, to clone this repo.
- Nothing else, for day-to-day use. `pyyaml` is only needed if you edit `prompts/` or
  `config/agents.yaml` and want to regenerate the agent files (`pip install pyyaml`).

## Quick start (absolute beginner path)

These are the exact commands to go from nothing to running your first agent. Run them in a
terminal.

```bash
# 1. Go to (or next to) the project you want to QA, and clone this repo there.
#    Easiest option: clone it *inside* your project as a subfolder called qa-pipeline.
cd /path/to/your-project
git clone <this-repo-url> qa-pipeline
cd qa-pipeline

# 2. Replace the bug report template with your team's real one (Jira fields, internal
#    tracker format, whatever you actually file bugs against). It ships with a generic
#    placeholder in templates/bug-report.template.md — edit that file directly.

# 3. Start Claude Code in this folder.
claude

# 4. Inside the Claude Code chat, confirm the agents are available:
/agents

# 5. Run your first agent — this one builds a knowledge file about the codebase you're
#    testing and only needs to be run once (re-run later only after major structural changes).
Use the context-analyzer agent to analyze this codebase.
```

That's it — step 5 writes `output/context.md`. From here, follow the
[Typical workflow](#typical-workflow) below for a full release cycle. Everything past this point
in the README explains what each agent does and how to configure things, but the five commands
above are all you need to get moving.

**If your target project is a separate repo from this pipeline** (you don't want to clone
`qa-pipeline` inside it), open Claude Code in your project directory instead, and copy
`.claude/`, `templates/`, and `output/` from this repo into it — or just reference this repo's
`prompts/` and `templates/` via a relative path when you invoke agents. Simplest is still to
clone this repo as a sibling directory and `cd` into your project when starting `claude`.

## Optional — GitLab push setup

Skip this whole section if you only want local Markdown drafts of bugs/release notes — nothing
else in this pipeline needs GitLab access. Come back to it later if you decide you want
`gitlab-publisher` to file things directly to GitLab.

```bash
# 1. Install the GitLab MCP server globally (this repo's .mcp.json points at the globally
#    installed binary rather than `npx ...@latest`, since npx's own console noise —
#    update-notifier banners, first-run download progress — can print to stdout and corrupt
#    the JSON-RPC stream the MCP protocol expects there, causing a "Connection closed" error).
npm install -g @zereight/mcp-gitlab

# 2. Copy the env template and fill in your own values.
cp .env.example .env
```

Then edit `.env` and set:
- `GITLAB_PERSONAL_ACCESS_TOKEN` — a **personal** token (Settings > Access Tokens on GitLab),
  scope `api`. Bugs/releases get filed as *you*, not a shared bot — each teammate sets their
  own. Grant it only Wiki and Work Item/Issue create+read abilities, nothing under Repository.
- `GITLAB_API_URL` — e.g. `https://gitlab.com/api/v4` (GitLab SaaS) or
  `https://gitlab.your-company.com/api/v4` (self-managed).

```bash
# 3. Point the pipeline at your GitLab project — edit config/pipeline.config.yaml and set
#    gitlab.project to your project path, e.g. "group/subgroup/project".
```

```bash
# 4. Start (or restart) Claude Code in this folder, then inside the chat run:
/mcp
```
The first time Claude Code sees `gitlab` in this project's `.mcp.json`, it shows a one-time
trust-approval prompt — accept it, or the server won't load and `/mcp` will show it as
unavailable with no other error. Confirm `/mcp` shows `gitlab` as connected before relying on
`gitlab-publisher`.

## Configuration

`config/pipeline.config.yaml` controls where agents write their output: `output_dir` (default
`output`), `runs_subdir` (default `runs`), an optional `run_id`, plus the file/folder names
under each run. Every agent reads this file before writing anything and falls back to the same
defaults if it's missing, so deleting it is safe. Change `output_dir` if you want artifacts to
land somewhere other than `./output`, e.g. inside an existing `docs/` or `qa/` folder.

**Run-versioned output.** Every stage's output lives under
`<output_dir>/<runs_subdir>/<run_id>/`, except `context.md`, which always lives directly at
`<output_dir>/context.md` — it's refreshed in place across cycles, not per-run, since it
describes the codebase rather than a specific release. `run_id` is resolved per invocation: the
value set in `config/pipeline.config.yaml`, or a run/release identifier you state in
conversation (e.g. a release tag or CR number), or — if neither is given — today's date
(`YYYY-MM-DD`). Every agent states which `run_id` it used at the top of its response, and if it
has to read a prior stage's file with no `run_id` given, it uses the most recently modified run
folder and tells you which one. Setting `run_id` explicitly is useful when you have concurrent
test cycles in flight (e.g. two release branches) and want their output kept cleanly separate.

`config/pipeline.config.yaml` also has an `inputs:` block for optional input locations
(`requirements_docs`, `logs_dir`, `bug_template`) — leave these `null` and just point agents at
the right file in conversation if you'd rather not configure them.

## Running the agents

Open Claude Code in your project directory (`claude`), then either:
- **Ask directly:** `Use the context-analyzer subagent to analyze this codebase.`
- **@-mention it** (guarantees delegation instead of Claude deciding): `@context-analyzer analyze this codebase and update context.md`
- **List what's available:** `/agents`

Agent names: `context-analyzer`, `regression-inventory-analyzer`, `changelog-analyzer`,
`requirements-analyzer`, `code-scanner`, `test-planner`, `test-case-writer`, `log-analyzer`,
`rca-analyst`, `bug-reporter`, `release-notes-writer`, `gitlab-publisher`.

## Running a pipeline (orchestrator)

For running several stages back-to-back instead of one at a time, Claude Code gets a
`/qa-pipeline` slash command that chains the named stages in order:

```
/qa-pipeline context changelog test-plan
/qa-pipeline regression-inventory
/qa-pipeline requirements code-scan
/qa-pipeline test-cases
/qa-pipeline log-analysis
/qa-pipeline rca bug-report
/qa-pipeline release-notes
/qa-pipeline                          # no args = defaults to: context changelog test-plan
```

All stages invoked in one `/qa-pipeline` call share the same `run_id` (see Configuration below)
— it's resolved once per invocation, not independently per stage.

It still respects the human review gate: if you chain `test-plan` and `test-cases` together in
the same call, it deliberately stops after `test-plan` and asks you to review/approve before
you re-run it with just `test-cases`. It's a convenience for chaining stages you've already
decided on — it doesn't decide the plan for you, and it won't run a stage you didn't ask for.

This is a command, not a 9th agent — it lives at `.claude/commands/qa-pipeline.md`, generated
from the source file at `prompts/commands/qa-pipeline.md`.

## The agents

| Order | Agent | Reads | Writes |
|---|---|---|---|
| 1 | `context-analyzer` | codebase | `output/context.md` |
| — | `regression-inventory-analyzer` *(optional, standing asset)* | manual suite CSV\*, automated specs\*, `context.md` | `output/regression-inventory.md`, `output/regression-inventory.csv` |
| 2 | `changelog-analyzer` | changelog/commits/diff | `output/changes.md` |
| 3 | `requirements-analyzer` *(optional)* | SRS/CR doc, `changes.md`, `code-scan.md`\* | `output/requirements.md`, `output/rtm.md`, `output/rtm.csv` |
| 4 | `code-scanner` *(optional)* | changed code from `changes.md`, `context.md` | `output/code-scan.md` |
| 5 | `test-planner` | `changes.md`, `context.md`, `requirements.md`\*, `code-scan.md`\*, `regression-inventory.md`\* | `output/test-plan.md`, `output/test-plan.csv` |
| — | *(human review & sign-off on the test plan)* | | |
| 6 | `test-case-writer` | `test-plan.md`, `regression-inventory.md`\* | `output/test-cases/*.md`, `output/test-cases.csv`, `output/coverage-matrix.md`, updates `output/rtm.md`\* |
| 7 | `log-analyzer` | logs (ad hoc, during execution) | `output/log-analysis.md` |
| 8 | `rca-analyst` | bug symptom, code, logs, `changes.md` | `output/rca/*.md` |
| 9 | `bug-reporter` | RCA, test case, your template | `output/bugs/*.md`, updates `output/rtm.md`\* |
| 10 | `release-notes-writer` | everything above | `output/test-closure-report.md`, `output/release-notes.md` |
| — | `gitlab-publisher` *(optional, on demand)* | one drafted bug or release notes doc | GitLab issue or wiki page; updates that same local draft with the resulting URL |

\* read/updated only if present for the run — these are optional stages/artifacts and later
agents degrade gracefully (stating so explicitly) when they weren't run.

**Pushing to GitLab.** `bug-reporter` and `release-notes-writer` only ever write local
Markdown — neither has GitLab access. To actually file something, review the draft, then run
`/push-bug <slug>` or `/push-release-notes <version>` (e.g. `/push-release-notes 3.0.68-DA`).
Each is a single, explicit push of one item, handled by `gitlab-publisher` — the only agent with
GitLab access, and it's scoped to issues and wiki pages only (`GITLAB_TOOLSETS=wiki,issues` in
`.mcp.json`, via the [zereight/gitlab-mcp](https://github.com/zereight/gitlab-mcp) server — used
instead of GitLab's official MCP server since that requires a GitLab Duo license). It never
reads source code or repository files, and never pushes anything you didn't name explicitly.
A successful push writes the resulting GitLab URL back into the local draft, so re-running the
same push is recognized as already-done instead of filing a duplicate. See
[Optional — GitLab push setup](#optional--gitlab-push-setup) above for one-time setup (`.env`,
`config/pipeline.config.yaml`'s `gitlab:` block).

`requirements-analyzer` is genuinely optional: it only does anything useful when an SRS/CR
document actually exists for the release. Point it at one, or skip the stage entirely — it will
say so plainly and stop rather than fabricate requirements if none is available.

**Existing regression/sanity coverage.** `regression-inventory-analyzer` is the same kind of
standing asset as `context-analyzer` — refreshed in place at `output/regression-inventory.md`,
not versioned per run, and re-run only when your existing suite meaningfully changes (not every
release cycle). Point it at a manual suite (`inputs.regression_suite_manual`, a CSV export of
your spreadsheet/TestRail/Xray/Zephyr suite), an automated suite (`inputs.regression_suite_automated`,
a path/glob to Cypress/Playwright/Selenium/pytest-style specs, in-repo or a local directory), or
both — either can be left unset, in which case the agent skips itself plainly. When the inventory
exists, `test-planner` cross-references it and pulls matching existing cases into a mandatory
"Existing Regression/Sanity Coverage" section of the test plan (so they get executed, not just
referenced), and flags impacted areas with none as "Regression Coverage Gaps." `test-case-writer`
then references those existing Case IDs (`Origin: Existing-Suite`) instead of re-authoring
equivalent regression cases from scratch.

**Requirement Traceability Matrix (RTM).** `requirements-analyzer` seeds `output/rtm.md` +
`rtm.csv` (Requirement ID → Source Ref → Implementation Ref → Test Case ID(s) → Test Status →
Defect ID(s)) whenever it has a requirements document to extract from. `Implementation Ref` is
filled in from `code-scan.md`'s discovered business rules if that stage has already run this
cycle — run `code-scan` before `requirements` for a fuller RTM, though running `requirements`
first still works (that column just stays "pending"). `test-case-writer` and `bug-reporter` fill
in the remaining columns as the cycle progresses. If no requirements document exists, no RTM is
produced — same "say so plainly, don't fabricate" rule as `requirements.md` itself.

`log-analyzer` and `rca-analyst` aren't strictly linear — use them whenever you're investigating
something, not only at a fixed point in the sequence.

### CSV output

`test-planner` and `test-case-writer` always write a CSV alongside their markdown
(`test-plan.csv`, `test-cases.csv`, paths configurable in `config/pipeline.config.yaml`) — no
setup required, this happens every run. `regression-inventory-analyzer` does the same
(`regression-inventory.csv`) whenever it actually runs. They're meant for manual import into
Google Sheets (**File > Import > Append to current sheet**) whenever you want the data there; no
agent in this pipeline touches Google Sheets or any external tool itself.

### Coverage matrix

`test-case-writer` also writes `output/coverage-matrix.md` every run — a Scope Area × Category
grid (Functional/Regression/Boundary/Negative/Security/Accessibility) tallied straight from the
test cases it just wrote, with a "Coverage Gaps" section for any scope-area/category combination
the test plan called for that ended up with zero test cases. It's a fast answer to "did we
actually get security/accessibility coverage for module X" without reading `test-cases.csv` by
hand.

## Typical workflow

```
# 1. Once per project (re-run after major structural changes)
Use the context-analyzer agent to analyze this codebase and produce context.md.
   -> writes directly to output/context.md, not run-versioned

# 2. Every release — pick a run_id (or let it default to today's date)
Use the changelog-analyzer agent on the diff between <last-tag> and HEAD.
   -> writes output/runs/<run_id>/changes.md

# 3. Optional, every release, after step 2
Use the requirements-analyzer agent against <SRS/CR doc> for this release.
Use the code-scanner agent to review the changed code from this run.
   -> writes output/runs/<run_id>/requirements.md and code-scan.md; skip either if not useful
      this cycle

# 4. Every release, after step 2 (and step 3 if run)
Use the test-planner agent to produce a test plan for these changes.
   -> review output/runs/<run_id>/test-plan.md yourself, edit/approve it
   -> also writes test-plan.csv unconditionally (see CSV output note below)

# 5. After the plan is approved
Use the test-case-writer agent to write test cases from the approved test plan.
   -> also writes test-cases.csv unconditionally

# 6. During execution, as needed
Use the log-analyzer agent on <log file/path>.
Use the rca-analyst agent to investigate <symptom description>.
Use the bug-reporter agent to file a bug based on the RCA for <symptom>.

# 7. At the end of the cycle
Use the release-notes-writer agent to prepare the closure report and release notes.

# 8. Optional, once a draft is reviewed — pushes to GitLab, never automatic
/push-bug <slug>
/push-release-notes <version>
```

Use the same `run_id` across a cycle (state it explicitly, e.g. "for run 2026-07-rc2") so every
stage's output lands in the same run folder — or just let every stage default to today's date if
you're not running concurrent cycles.

Subagents are typically invoked by name (`@agent-name` or by asking Claude to "use the X agent").

## Repo layout

```
qa-agent-pipeline/
├── prompts/                 SOURCE OF TRUTH — one file per agent, plain instructions
│   └── commands/            SOURCE OF TRUTH for slash commands (qa-pipeline, push-bug, ...)
├── config/
│   ├── agents.yaml           agent metadata (description, tool permissions)
│   ├── commands.yaml         command metadata (description, argument hint)
│   └── pipeline.config.yaml  where agents write output (output_dir + file names), plus the
│                             gitlab: block (project, wiki dir, severity label map)
├── scripts/generate_agents.py   regenerates .claude/ from prompts/ + config/
├── .claude/agents/          generated — Claude Code subagent files (committed)
├── .claude/commands/        generated — Claude Code slash commands (committed)
├── .mcp.json                GitLab MCP server config (issues+wiki only) for gitlab-publisher
├── .env.example              template for your own GITLAB_PERSONAL_ACCESS_TOKEN / API URL
├── templates/               required output structure for each agent
│   └── bug-report.template.md   <- replace this with your team's real template
├── output/                  where agents write results (gitignored per-project data,
│                             structure kept via .gitkeep; path configurable, see above)
├── dashboard/               optional local web UI — see dashboard/README.md
└── CHANGELOG.md             version history of this pipeline itself
```

## Extending this

To add a new agent (say, a performance-test analyzer):
1. Write `prompts/perf-analyzer.md` — the actual instructions, no frontmatter.
2. Add an entry to `config/agents.yaml` (id, description, tools).
3. Add an output template under `templates/` if it produces a new file type.
4. Run `python3 scripts/generate_agents.py`.
5. Commit everything, including the two generated agent files.

To change an existing agent's behavior, edit its file under `prompts/` and re-run the generator
— never hand-edit files under `.claude/agents/` directly, they'll be overwritten next time
someone regenerates.

Same pattern for commands: edit `prompts/commands/qa-pipeline.md` or `config/commands.yaml` to
change the orchestrator, or add a new `id` to `config/commands.yaml` plus a matching
`prompts/commands/<id>.md` for a new one, then re-run the generator.

## Dashboard (optional)

For a click-and-view alternative to typing agent invocations in Claude Code chat, there's a
local web dashboard under `dashboard/`: one button per agent, one button for the full pipeline, a
live log of what's running, and a browser for the generated `output/` files (rendered markdown,
CSV as a table). It's a thin wrapper — every button shells out to the exact same `claude` CLI
invocations documented above, built from this repo's own `prompts/` — so the chat/CLI workflow
keeps working unchanged whether or not you use it. Point it at any project with `--project-dir`;
that project does not need `.claude/` or anything else copied into it first.

```bash
pip install -r dashboard/requirements.txt
python3 dashboard/server.py --project-dir /path/to/some/project
```

Then open `http://127.0.0.1:8765` in a browser (`--project-dir` defaults to `.` if omitted, and
you can pass `--port` to change the port). See `dashboard/README.md` for details, including how
the test-plan review gate is surfaced in the UI.

## Troubleshooting

- **`/agents` doesn't list the pipeline's agents.** Make sure you started `claude` from inside
  this repo (or a project where `.claude/agents/` was copied in) — agent definitions are
  resolved from the current working directory.
- **`/mcp` shows `gitlab` as unavailable / "Connection closed".** Almost always one of: the
  one-time trust prompt wasn't accepted yet, `mcp-gitlab` isn't installed globally (see
  [GitLab push setup](#optional--gitlab-push-setup)), or `.env` is missing/empty. Restart
  `claude` after fixing any of these.
- **An agent says a prior stage's output is missing.** Run the stage it depends on first (see
  the [table above](#the-agents) for what each agent reads), or tell it which `run_id` to look
  in if you're not using today's date.
- **I edited a prompt and nothing changed.** Prompts under `prompts/` aren't used directly —
  run `python3 scripts/generate_agents.py` (needs `pip install pyyaml`) to regenerate
  `.claude/agents/` and `.claude/commands/`, then restart `claude`.

## Versioning

This pipeline is versioned independently of any project it's used in — see `VERSION` and
`CHANGELOG.md`. If you fork/customize this for your team, bump the version and log changes there
so improvements are traceable over time, same as any other codebase.
