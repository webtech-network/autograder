# Execution diagnostics

The [terminal outcome](../contracts/OUTCOMES.md) is the only grading artifact.
An optional `observer=callback` argument on `run` and `evaluate_submission`
lets a host collect operational observations separately:

```python
events = []
outcome = evaluate_submission(
    submission, definition=compiled, capabilities=host_capabilities,
    observer=events.append,
)
```

Each frozen `DiagnosticEvent` contains an execution ID, an operation string,
a completed/failed status, and an optional safe structured error. It contains no
submission, criteria tree, session, grade, or back-reference. The coordinator
never reads the observer's records. Callers may collect, discard or add records;
observer exceptions are logged and do not change grading order or results.
Operation strings are internal diagnostics, not an enum or versioned wire contract.
No diagnostic serializer or planned-step reconstruction is required.

Cleanup failures always reach logging and, when supplied, the observer as
`close_session` / `CLEANUP_ERROR`. The original grading outcome is preserved.
Raw exceptions remain in host logs; hosts control access and retention.
The terminal outcome duration includes cleanup and freezes when constructed.

The former execution journal, artifact accessors and
`PipelineExecutionSerializer` have been removed. Consumers of the old debugging
projection migrate to these independent events and terminal outcome fields.
