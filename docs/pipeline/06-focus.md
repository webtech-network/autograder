# Feedback focus

When feedback is requested, `render_feedback` calls `find_focus(tree)`
(`autograder/services/focus_service.py`). It ranks each category's criteria by
the points they cost, `(100 - score) * share`, where `share` comes from the
shared scoring traversal (`iter_test_shares`). Ties keep the canonical criterion
order. The result is a frozen `Focus` holding the tree's own `TestOutcome` values.

Focus is optional enrichment. Failure preserves the validated grade and marks
feedback failed. Disabled feedback does not call focus selection.

See [focus scoring](../features/focus_feature.md).
