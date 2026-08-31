# Changelog — QA Agent Pipeline

All notable changes to this pipeline (not to any project it's used on) are logged here.

## [Unreleased]
### Removed
- OpenCode support. The pipeline now generates and targets Claude Code only — `.opencode/` is
  gone, `scripts/generate_agents.py` no longer writes OpenCode agent/command files, and
  OpenCode references have been removed from the docs.

### Added
- **Coverage matrix.** `test-case-writer` now also writes `output/coverage-matrix.md` every run
  — a Scope Area × Category grid tallied from the test cases it just wrote, with a "Coverage
  Gaps" section flagging any scope-area/category combination the test plan called for in-scope
  that ended up with zero test cases. New `templates/coverage-matrix.template.md` and
  `paths.coverage_matrix` config entry.
- **Dashboard output location.** The dashboard now writes QA artifacts to a sibling
  `<project-name>-qa-pipeline` directory next to `--project-dir`, created once and reused on
  every later run, instead of nesting an `output/` folder inside the project's own repo. A
  project's own `config/pipeline.config.yaml` (if it sets `output_dir` explicitly) still wins.
  Chat/CLI usage outside the dashboard is unchanged.
- **Dashboard UI redesign** — new typography (Sora/Inter/JetBrains Mono), status badges, agent
  icons, plain-language tool-call descriptions instead of raw JSON, a bottom-docked live log
  console, and a much larger Output Browser panel as the dashboard's dominant view.
- **`dashboard/`** — an optional local web UI (FastAPI + vanilla JS, `python3
  dashboard/server.py --project-dir <path>`) with a button per agent, a full-pipeline runner, a
  live streamed log, and a browser for `output/` artifacts (markdown rendered, CSV as a table).
  Every action shells out to `claude`, built from this repo's own `prompts/` +
  `config/agents.yaml` via `claude`'s `--agents` inline-JSON flag — the target project needs
  nothing installed in it (no `.claude/agents/`, no config) to be pointed at with
  `--project-dir`. No new agent behavior. Includes a UI-side Approve step surfaced after
  `test-planner` runs, mirroring the existing human review gate before `test-case-writer` is
  unlocked.
- **QA-friendly, real-user-behavior language required throughout.** `code-scanner`'s discovered
  business rules, `requirements-analyzer`'s mismatch findings, and every `test-case-writer`
  step/expected-result must be phrased in terms of what a real user does and sees — never code
  identifiers or internal implementation details — so QA engineers can act on them without
  reading the underlying code.
- `code-scanner` now also extracts business rules, validation logic, feature flags, and
  integration points from the changed code it already reviews (`## Business Rules & Behavior
  Discovered` in `code-scan.md`), each with a `file:line` citation, in plain user-facing language.
- `requirements-analyzer` now cross-references requirements against `code-scan.md`'s discovered
  business rules (if that stage has run this cycle), surfacing an `## Implementation vs.
  Documentation Mismatches` section: documented-but-unconfirmed, implemented-but-undocumented,
  and directly conflicting behavior.
- **Requirement Traceability Matrix (RTM).** `requirements-analyzer` seeds `output/rtm.md` +
  `rtm.csv` (Requirement ID → Source Ref → Implementation Ref → Test Case ID(s) → Test Status →
  Defect ID(s)) whenever a requirements document exists this cycle; `test-case-writer` and
  `bug-reporter` fill in the remaining columns as the cycle progresses. No RTM is produced when
  there's no requirements document, same as `requirements.md` itself.
- Test cases now carry explicit **Origin** (Requirement-based / Implementation-based),
  **Category** (Functional / Regression / Boundary / Negative / Security / Accessibility), and
  **Automation Candidate** (Yes/No + reason) fields, replacing the old free-text
  Positive/Negative/Edge type — grouped so a reviewer can scan by origin, by risk category, or by
  automation candidates. `test-cases.csv` gains matching columns.
- **Structured clarification questions.** `test-plan.md`'s Open Questions section is now a table
  (Question / Context / Source / Related Scope Area), aggregated by `test-planner` from its own
  uncertain impact areas, `requirements.md` mismatches, and vague code behavior noted in
  `code-scan.md` — every question cites a concrete source. These are for the user to review with
  Product/Dev; the pipeline never answers them itself.
- `test-planner`'s risk classification now explicitly names its four inputs: code complexity,
  business impact, data sensitivity, and module dependencies (wording clarification; the
  High/Medium/Low rating and review gate were already in place).
- `config/pipeline.config.yaml` — configurable output directory/file names, read by every
  agent instead of hardcoding `output/`.
- `qa-pipeline` orchestrator command (`.claude/commands/`, `.opencode/commands/`) that chains
  named stages in sequence, enforcing the test-plan review gate automatically.
- `scripts/generate_agents.py` now also generates commands (`config/commands.yaml` +
  `prompts/commands/`), same pattern as agents.
- **Run-versioned output.** `config/pipeline.config.yaml` gains `runs_subdir` and `run_id`;
  every stage's output now lives under `<output_dir>/<runs_subdir>/<run_id>/`, resolved from
  config, a user-stated run/release identifier, or today's date — except `context.md`, which
  stays unversioned at `<output_dir>/context.md`. Every agent states which `run_id` it used, and
  which run folder it read from when inferring one. All stages in a single `/qa-pipeline`
  invocation share one resolved `run_id`.
- **`requirements-analyzer`** (optional agent) — extracts CR/requirement items from an SRS/CR
  document and cross-references them against `changes.md`, producing `requirements.md`. Says so
  plainly and stops if no requirements document is available; never fabricates requirements from
  the codebase.
- **`code-scanner`** — reviews only the changed code recorded in a run's `changes.md` for logic
  bugs, weak error handling, security concerns, convention violations, and leftover debug code,
  producing `code-scan.md`. Every finding is Blocker/Should-Fix/Note with a file:line reference.
  Advisory only: feeds `test-planner`'s risk rating, never blocks the pipeline.
- `test-planner` now optionally reads `requirements.md` (CR traceability) and `code-scan.md`
  (reweights risk of in-scope areas by Blocker/Should-Fix findings), and adds a defect-prone
  zone heuristic (git churn + historical bug frequency from past runs' `bugs/`) that only
  reweights risk on already-in-scope areas and populates an advisory "Known Fragile Areas - Not
  In Scope This Release" section — never expands test scope to untouched code. Guardrail: signal
  under ~5 historical bugs or a very short churn window is labeled inconclusive, not reweighted.
- `test-planner` and `test-case-writer` now always write a CSV (`test-plan.csv`,
  `test-cases.csv`) alongside their markdown, every run, for manual import into Google Sheets
  (File > Import > Append) — no agent touches Google Sheets or any external tool directly.

## [0.1.0] - Initial release
### Added
- 8 agents covering the full manual QA cycle: context-analyzer, changelog-analyzer,
  test-planner, test-case-writer, log-analyzer, rca-analyst, bug-reporter,
  release-notes-writer.
- Single-source-of-truth prompt files under `prompts/`, generated into both Claude Code
  (`.claude/agents/`) and OpenCode (`.opencode/agent/`) formats via
  `scripts/generate_agents.py`.
- Output templates for every agent under `templates/`.
- Read-only-on-source-code tool permissions for every agent.
