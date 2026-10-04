# Internal pipeline diagnostics

The public integration contract is the finalized
[terminal outcome v1](../contracts/OUTCOMES.md). Consumers use its completed/failed
status, nullable score, definition provenance, safe error, language, timestamps,
and enrichment status. They do not depend on pipeline class names or step counts.

`PipelineExecutionSerializer.serialize(execution)` is an optional internal
operator/debugging projection. It includes executed step names/statuses,
`failed_at_step`, planned step count, successfully completed step count, and
execution duration. `FAIL` and `INTERRUPTED` are both unsuccessful. Bootstrap is
an internal initialization record and is omitted from displayed steps. Planned
steps come from the configured pipeline, not the number executed before failure.
Completed count includes only successful step results. Duration freezes at
terminal finalization; polling/serializing later cannot make execution slower.

Structured preparation diagnostics may contain required-file names, setup
commands, stdout, stderr, and implementation details. Hosts must protect these
operator diagnostics separately from student-facing responses and public error
messages. The HTTP outcome does not include them by default.

The hosting adapter owns persistence and delivery. It may store internal
execution diagnostics separately from the immutable public outcome. A failed
publication is not an unsuccessful grading step, and optional feedback failure
can coexist with a completed grade.
