# Regression / Sanity Inventory

Last updated: <!-- date, and one line on what changed since last update -->

Sources: `<inputs.regression_suite_manual path, or "none configured">`,
`<inputs.regression_suite_automated path, or "none configured">`

Scope areas below reuse `output/context.md`'s module/area vocabulary exactly, so
`test-planner` can match on it directly.

## Inventory

| Case ID | Title | Source | Scope Area | Location | Last Known Status |
|---|---|---|---|---|---|
<!-- One row per existing regression/sanity case.
Case ID: the source's own ID, or the case's title/description if the source has none.
Source: Manual / Automated.
Scope Area: must match an area name from context.md's module map exactly, or "Uncategorized".
Location: sheet row reference for Manual, file path (+ describe()/test name if useful) for Automated.
Last Known Status: from the spreadsheet's own status column, if it has one. Omit the column
content (leave blank) if the source doesn't track this — never invent a status. -->

## Uncategorized

<!-- Automated-suite entries whose scope area couldn't be determined from file path/directory
convention or describe() names. One line per entry: file path, and a one-line note on why it
couldn't be mapped. These need manual scope tagging (edit the spreadsheet, or move/rename the
spec file to a convention-following path) before test-planner can match them to an impacted area. -->

## Not Confirmed
<!-- Anything you could not verify confidently — e.g. a spreadsheet row with no discernible
scope information, or a spec file that doesn't match any recognized automation-framework
pattern. -->
