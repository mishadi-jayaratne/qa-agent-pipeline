# Requirements Traceability

Last updated: <!-- date of most recent refresh, and which source document drove it, e.g.
"2026-09-08 — CR-042.docx" -->
Source(s) analyzed so far: <!-- running list of every SRS/CR document folded in over time,
e.g. "SRS-v1.pdf (initial, 2026-08-01), CR-042.docx (2026-09-08 update)" -->
Cross-referenced against: <!-- output/changes.md for the run that produced this update, or
"not available this cycle" -->

## Requirements

| ID | Description | Acceptance Criteria | Matched Change Ref | Status |
|---|---|---|---|---|
| <!-- CR-### or "untagged" --> | | | <!-- ref from changes.md, or "no matching change found" --> | <!-- current / superseded / removed -->|

<!-- One row per requirement/acceptance-criteria item ever extracted. On a refresh, update
drifted rows in place, add new rows, and mark rows no longer present in the current source(s)
as "superseded" or "removed" rather than deleting them — keep the history auditable. -->

## Undocumented Changes
<!-- Entries from changes.md with no matching requirement/CR item. Omit section if none, or if
changes.md wasn't available to cross-reference. -->

## Implementation vs. Documentation Mismatches
<!-- From output/code-scan.md's "Business Rules & Behavior Discovered", if that stage ran this
cycle. State plainly "not performed this cycle — code-scanner has not run" if it hasn't. One row
per mismatch, in plain user-facing language: -->

| Requirement | Discovered Behavior | Mismatch Type | Notes |
|---|---|---|---|
| <!-- CR-### or "untagged", or "—" if code-only --> | <!-- file:line + plain description, or "—" if requirement-only --> | <!-- documented-not-confirmed / implemented-undocumented / conflicting --> | |

## Summary
<!-- If this was a refresh: items added, updated, superseded/removed. Either way: requirements
extracted, matched, unmatched, undocumented changes found, and (if code-scan.md was available)
mismatches by type. -->

---
This file is refreshed in place across runs (like `output/context.md`), not versioned per
cycle — see also: `output/runs/<run_id>/rtm.md` — that run's Requirement Traceability Matrix,
seeded from the current rows above.
