# Test Cases — <Scope Area Name>

Traces to: `output/test-plan.md` § <scope area>

---

## TC-<###>: <Title>
- **Origin:** Requirement-based / Implementation-based
- **Category:** Functional / Regression / Boundary / Negative / Security / Accessibility
- **Automation Candidate:** Yes / No — <one-line reason>
- **Priority:** High / Medium / Low
- **Traces to:** <CR/requirement ID or change ref from changes.md>
- **Preconditions:** <state required before execution>

**Steps:**
1. <step> — **Expected:** <unambiguous expected outcome of this step>
2. <step> — **Expected:** <unambiguous expected outcome of this step>

<!-- Use a per-step Expected on each numbered step whenever steps are independent checkpoints
(e.g. a cache-then-fresh-lookup sequence where step 2 and step 3 each assert something different).
Collapse to a single trailing "**Expected Result:**" line only when every step is pure setup and
one final assertion is genuinely the only outcome that matters. Never mix the two — pick one form
per test case. -->

---

<!-- repeat per test case. Group Functional, then Regression/Boundary, then Negative/Security/
Accessibility, within each scope area. -->
