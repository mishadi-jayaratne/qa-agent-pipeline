# Test Plan — <release/version identifier>

Based on: `output/changes.md`, `output/context.md` (and `output/requirements.md`,
`output/code-scan.md`, `output/regression-inventory.md` where available)
Status: DRAFT — requires human review and sign-off before test case writing begins

## Scope Summary
<!-- One paragraph: what this release changes and the overall testing approach. -->

## Impacted Areas

### <Scope area name>
- **Traces to change(s):** <ref from changes.md>
- **Impact type:** Direct / Ripple
- **Risk:** High / Medium / Low — <reasoning. Note if reweighted by code-scan findings and/or
  the churn/historical-bug heuristic, and by how much.>
- **Test scope:** <functional / integration / regression / negative / performance / security — whichever apply>
- **Notes:** <anything uncertain, marked "possible impact, needs verification" where relevant>

<!-- repeat per impacted area -->

## CR Traceability
<!-- From output/requirements.md for this run, if it exists: which impacted areas trace to a
CR/requirement ID. If requirements.md doesn't exist this cycle, state plainly:
"CR traceability not performed this cycle." -->

## Existing Regression/Sanity Coverage
<!-- From output/regression-inventory.md for this run, if it exists: for each impacted area
above that has matching existing case(s), list them here as mandatory scope for this cycle —
these are cases to execute, not just references. Format: "<Scope Area>: TC <Case ID>, TC
<Case ID>, ...". If regression-inventory.md doesn't exist this cycle, state plainly:
"Regression inventory cross-reference not performed this cycle." -->

## Regression Coverage Gaps
<!-- Impacted areas above that have zero matching existing case(s) in regression-inventory.md
(when that file exists) — i.e. this area needs regression coverage but none exists yet. One
line per area. Omit this section entirely if regression-inventory.md wasn't available, or if
every impacted area had at least one match. -->

## Known Fragile Areas - Not In Scope This Release
<!-- High-churn / high-defect modules (from git history and past output/runs/*/bugs/) with zero
impact from this release's changes. One line per area: module, reason (churn/defect signal),
explicitly labeled "not tested this cycle." Advisory only — requires a separate human decision
to act on; never expands scope. Omit or label "inconclusive" per-entry if the underlying signal
is too thin (see test-planner's guardrail: <5 historical bugs or a very short churn window). -->

## Out of Scope
<!-- Areas explicitly not tested this cycle, with reasoning. -->

## Test Environment & Data Needs
<!-- Environment, test data, mocks/stubs, third-party dependencies required. -->

## Entry Criteria
-

## Exit Criteria
-

## Open Questions
<!-- Structured, sourced clarification questions for the user to review with Product/Dev before
sign-off. This pipeline generates these — it never answers them. -->

| Question | Context | Source | Related Scope Area |
|---|---|---|---|
| | | <!-- Vague Requirement / Undocumented Code Behavior / Conflicting Info --> | |
