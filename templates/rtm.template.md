# Requirement Traceability Matrix — <release/version identifier>

Built by: requirements-analyzer (cross-reference mode), from the current `output/requirements.md`
(refreshed in place across runs). This RTM is per-run and safe to rebuild.
Last cross-referenced: <!-- date -->
Cross-referenced against: <!-- changes.md for this run, or "not available — changes not matched" -->
Code-scan: <!-- code-scan.md for this run, or "not available — mismatch detection not performed;
re-run requirements-analyzer after code-scanner" -->

Test Case ID(s) / Test Status are updated in place by test-case-writer, Defect ID(s) by
bug-reporter. A re-run of requirements-analyzer preserves those values.

| Requirement ID | Source Ref | Matched Change Ref | Implementation Ref | Test Case ID(s) | Test Status | Defect ID(s) |
|---|---|---|---|---|---|---|
| <!-- CR-### or "untagged" --> | <!-- location in the source doc --> | <!-- ref from changes.md, or "no matching change found" --> | <!-- file:line, or "pending — no code-scan match" --> | <!-- pending until test-case-writer runs --> | <!-- pending / written, not yet executed / pass / fail --> | <!-- none yet --> |

<!-- one row per current (not superseded/removed) requirement in requirements.md -->

## Undocumented Changes
<!-- Entries from changes.md with no matching requirement/CR item. Omit if none, or if
changes.md wasn't available. -->

## Implementation vs. Documentation Mismatches
<!-- From code-scan.md's "Business Rules & Behavior Discovered", if it exists for this run.
Otherwise state plainly "not performed — code-scan.md not found". One row per mismatch, in
plain user-facing language: -->

| Requirement | Discovered Behavior | Mismatch Type | Notes |
|---|---|---|---|
| <!-- CR-### or "untagged", or "—" if code-only --> | <!-- file:line + plain description, or "—" if requirement-only --> | <!-- documented-not-confirmed / implemented-undocumented / conflicting --> | |
