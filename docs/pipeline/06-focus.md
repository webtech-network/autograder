# Feedback focus

When feedback is requested, `FocusService.find(result_tree)` ranks tests by their
effect on the grade and returns a `Focus` value. The coordinator passes both the
focus and result tree directly to the reporter.

Focus is optional enrichment. Failure preserves the validated grade and marks
feedback failed. Disabled feedback does not call focus selection.

Implementation: `autograder/services/focus_service.py`.
See [focus scoring](../features/focus_feature.md).
