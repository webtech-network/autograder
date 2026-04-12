# Educational Criteria Design with the Criteria Tree

This guide explains how to design rubrics that are technically precise and pedagogically useful.

## 1. Start from learning outcomes, not test tools

Write outcomes first, then map them to subjects/tests.

Good outcome labels:

- "Correctly handles malformed input"
- "Implements REST semantics for status codes"
- "Uses semantic HTML structure"

Weak outcome labels:

- "Passes regex test 3"
- "No warning in command X"

## 2. Use category intent clearly

- **Base**: required competencies
- **Bonus**: enrichment, not compensation for missing fundamentals
- **Penalty**: explicit deductions (late policy, disallowed behavior)

Avoid putting mandatory requirements in `bonus`.

## 3. Keep subject granularity meaningful

Each subject should represent a coherent skill block. If a subject has one tiny test only, consider merging it. If a subject has too many unrelated tests, split it.

## 4. Weight by instructional importance

A suggested calibration process:

1. Rank outcomes by instructional importance.
2. Convert ranking into percentages.
3. Verify total category and sibling weights make sense to humans.
4. Validate the rubric with 3-5 representative submissions.

## 5. Build explainable feedback paths

For each high-priority test, define:

- clear failure wording
- likely root cause hints
- one remediation resource (URL, section, or exercise)

This keeps feedback actionable without becoming overwhelming.

## 6. Keep rubrics stable across attempts

Frequent rubric changes reduce fairness and comparability between attempts. Version rubric changes intentionally and communicate major shifts.

## Quality checklist

Use this before publishing an assignment rubric:

- Does every weighted node map to a real learning outcome?
- Can a student explain score loss from the generated report?
- Do penalties reflect explicit policy and not hidden expectations?
- Are resources linked to likely failure points?
- Is the rubric understandable by another instructor without extra context?

## Related docs

- [Criteria Tree](../core/criteria-tree.md)
- [Feedback Generation](../core/feedback-generation.md)
- [Criteria Configuration Examples](criteria_configuration_examples.md)
