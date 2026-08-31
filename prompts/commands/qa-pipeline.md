Run the QA pipeline stages given in the arguments below, in the order given — invoking each
stage's dedicated subagent and letting it finish before starting the next.

**Arguments (space-separated stage names):** $ARGUMENTS

If no arguments were given, default to: `context changelog test-plan` (the standard "new
release just landed" chain).

## Stage map
| Stage name | Subagent invoked |
|---|---|
| `context` | context-analyzer |
| `changelog` | changelog-analyzer |
| `requirements` | requirements-analyzer |
| `code-scan` | code-scanner |
| `test-plan` | test-planner |
| `test-cases` | test-case-writer |
| `log-analysis` | log-analyzer |
| `rca` | rca-analyst |
| `bug-report` | bug-reporter |
| `release-notes` | release-notes-writer |

## Rules
0. All stages invoked in one `/qa-pipeline` call share the same `run_id` for that invocation —
   resolve it once (config, or a run/release identifier the user states, or today's date) and
   use it consistently across every subagent invoked in this run, rather than letting each stage
   resolve it independently.
1. Invoke exactly the stages given, in the order given. If a name doesn't match the stage map,
   tell the user rather than guessing what they meant, and skip it.
2. Before invoking a stage, check whether it needs input that hasn't been provided yet — e.g.
   `changelog` needs a commit range/changelog source, `log-analysis` needs a log file/path,
   `rca` needs a bug/symptom description, `bug-report` needs to know which bug it's for. If
   something's missing, ask the user for it before invoking that stage.
3. After each stage completes, briefly report what file it wrote before moving to the next one.
4. **Hard gate — do not skip this:** if `test-plan` is in this run and `test-cases` comes
   immediately after it in the same run, STOP after test-planner finishes. Tell the user the
   test plan needs human review and sign-off before test cases get written, and that they
   should re-run this command with just `test-cases` once `output/test-plan.md` (or the
   configured equivalent) is approved. Do not invoke test-case-writer in the same run as
   test-planner even though it was requested — this gate is intentional, not a bug to route
   around.
5. Do not invoke any stage that wasn't explicitly requested (directly, or via the no-argument
   default above). This command chains agents you've already decided on — it doesn't decide
   the plan for you.
