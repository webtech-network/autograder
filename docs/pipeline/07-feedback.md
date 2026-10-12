# Requested feedback

The definition's `feedback.enabled` controls focus selection and reporting.
The coordinator calls `ReporterService.generate_feedback` with the explicit
focus, result tree, validated preferences and submission locale. The supported
mode is `default`, which returns Markdown.

Successful reporting becomes completed feedback on the terminal outcome.
A focus/reporting exception or absent report becomes `FEEDBACK_ERROR` while
preserving the completed grade. Disabled feedback performs no enrichment work.

Learning-resource links use criterion IDs. Credentials and provider operations
belong to the host. Publication happens after cleanup and finalization in the
[hosting adapter](08-export.md), outside grading.
