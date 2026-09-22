# QA Agent Pipeline Dashboard

An optional local web UI over the same pipeline documented in the root `README.md` — one button
per agent, one button for the full pipeline, a live log of what's happening, and a browser for
the generated `output/` files. It doesn't change any agent behavior: every button shells out to
the exact same `claude` CLI, built from this repo's own `prompts/` + `config/agents.yaml`.

## No install needed in the target project

Point `--project-dir` at **any** project — it does not need `.claude/agents/`, `config/`, or
anything else from this pipeline copied into it. `dashboard/server.py` always reads agent
definitions from its own parent directory (this repo — `prompts/<id>.md` + `config/agents.yaml`)
and passes them to `claude` inline via its `--agents` JSON flag for each run, so `--project-dir`
is purely "the codebase/working directory to run agents against," nothing more.

If the target project happens to have its own `templates/` (e.g. a real `bug-report.template.md`)
those are honored automatically — agents look for them relative to `--project-dir` first, same as
they always have. If it doesn't, this repo's own `templates/` defaults are used instead.

## Where output goes

This matches direct chat/CLI usage — both keep QA artifacts **out of the project's own tree** by
default: the first time you point either one at a project, it creates a sibling directory named
`<project-name>-qa-pipeline` next to it —
e.g. pointing `--project-dir` at `/hms/projects/m1_rsc/rsc108/rsc-service` creates
`/hms/projects/m1_rsc/rsc108/rsc-service-qa-pipeline/`. Nothing is added to the project's own
repo, so there's no `.gitignore` entry to add and nothing to accidentally commit. If that
directory already exists from a previous cycle, it's reused as-is — nothing is recreated or
wiped.

Inside it, each cycle gets its own run folder under `runs/` (`context.md` stays unversioned at
the top level, same as always), named whatever you put in the **Run folder** field at the top of
the page — defaults to today's date, or type something like `2026-08-24-rc2` to combine a date
with a release name. That value is reused verbatim for every stage in the same cycle (it's never
auto-recomputed from "today"), so a cycle that spans multiple days — e.g. `test-planner` today,
`test-case-writer` after a two-day review — still lands in the same folder.

A project's own `config/pipeline.config.yaml`, if it sets `output_dir` explicitly, always
overrides this default — same "your customization wins" rule as everything else here.

## Install & run

```
pip install -r dashboard/requirements.txt
python3 dashboard/server.py --project-dir /path/to/some/project
```

`--project-dir` defaults to `.` if omitted — useful for running the dashboard against this repo
itself. Then open `http://127.0.0.1:8765` (or whatever `--port` you passed). The server only
binds to `127.0.0.1` — it's a local convenience tool, not meant to be exposed on a network.

## How it works

- **Agent buttons** build `--agents '{"<id>": {"description": ..., "prompt": <prompts/<id>.md
  body>, "tools": [...]}}'` from this repo's own source files, then run `claude -p --agents
  <json> --agent <id> --output-format stream-json --verbose --permission-mode
  bypassPermissions "<default action + your optional context>"` with `cwd` set to
  `--project-dir`. The `tools` list is exactly what `config/agents.yaml` declares for that
  agent — the dashboard doesn't grant anything extra, same guarantee `.claude/agents/<id>.md`
  gives in a normal chat session.
- **Run Pipeline** sends `prompts/commands/qa-pipeline.md`'s body directly as the prompt (with
  `$ARGUMENTS` substituted for the stage list you typed) instead of invoking the `/qa-pipeline`
  slash command — that command file also lives under `.claude/commands/`, so this avoids needing
  it installed in the target project either. The orchestrating session gets every agent
  registered via `--agents` plus the `Task` tool only, so it can delegate to subagents but never
  touch files directly itself. The stage list, defaults, and the test-plan review gate are still
  exactly what `prompts/commands/qa-pipeline.md` says — nothing is reimplemented here, just
  delivered a different way.
- **Run folder** defaults to today's date in the UI. Every invocation also gets an explicit
  `Use <resolved qa-pipeline dir> as output_dir` instruction injected into its prompt (see
  "Where output goes" above) — this is what makes agents write to the sibling directory instead
  of falling back to their own default of a bare `output/` nested in the project.
- **Review gate**: after `test-planner` finishes, the dashboard shows an "Approve" banner. Open
  the test plan in the Output panel, review it, then click Approve — only then does that run
  folder's Test Case Writer button become clickable. This is a UI-side guardrail only;
  `test-case-writer`'s own prompt still independently requires `test-plan.md` to exist.
- **Output browser** reads from the same resolved output directory described above.

## Limitations (v1)

- One job runs at a time — a second click while a job is running is queued, not run in parallel.
- Job history and logs live in memory / `dashboard/logs/` for the life of the server process —
  restarting the server clears run history (the actual `output/` artifacts on disk are
  untouched).
- Requires the `claude` CLI on `PATH` and an authenticated session, same as running agents by
  hand.
