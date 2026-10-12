# Grading flow

The complete runtime order lives in `AutograderPipeline.run` in
`autograder/autograder.py`. It uses ordinary calls and local values:

1. Select the submission language and derive requirements from selected criteria.
2. Validate required files and evaluator file selection before checking providers.
3. Acquire a host-owned session only when execution is required, stage files,
   fixtures and setup commands, and start an assessed server when needed.
4. Evaluate selected AI criteria once, returning assessments keyed by criterion ID.
5. Pass the compiled criteria, submission, session and assessments directly to
   `GraderService.grade_from_tree`; calculate and validate the result tree.
6. If feedback is enabled, pass that result to focus selection and reporting.
7. Close the owned session in `finally`, then construct the terminal outcome.

Compilation supplies trusted templates, normalized parameters and the criteria
tree. Runtime does not load templates or rebuild/attach that tree. Structural
parsing is lazy and local to the grader's selected static assessments. Static
evaluation opens no execution session.

Required failures return a failed outcome with null score/tree. A valid student
assessment of zero completes normally. Focus/reporting have an explicit optional
failure boundary: a failure preserves the validated grade and sets feedback to
failed. Disabled feedback calls neither service.

The session belongs to the run as soon as acquisition returns. Staging,
preparation, assessment and enrichment failures all reach cleanup. A close
failure is logged with the execution ID and emitted to an optional diagnostic
observer; it does not replace an existing assessment or trigger a second close.

`evaluate_submission(...)` returns the immutable terminal outcome.
`build_pipeline(...).run(...).outcome` remains supported through a frozen
return envelope. No evaluation data is stored in diagnostics or recovered from
operation names. The host publishes the finalized outcome and owns delivery retries.

## Internal Python migration (ARC-01)

The v1 definition/outcome schemas and supported facade are unchanged.
Internal step constructors, `add_step`, `StepRegistry`, `StepName`,
`StepResult`, artifact accessors, `execution.result`, mutable execution status,
and `finish_execution` are removed. Call the facade and read `outcome.status`,
`outcome.score`, `outcome.tree` and `outcome.feedback`.
Tests of evaluators/services pass explicit inputs; tests of orchestration use the
compiled definition and fake host capabilities. Adding an evaluator requires only
its parameter contract and trusted template registration.

Hosts needing operational observations may pass `observer=callback` to
`run` or `evaluate_submission`. See [diagnostics](../architecture/pipeline_execution_tracking.md),
[host capabilities](../contracts/CAPABILITIES.md), and
[terminal outcomes](../contracts/OUTCOMES.md).

## Migration verification

The regression coverage uses the replacement interfaces directly:

| Behavior | Coverage |
| --- | --- |
| Diagnostics disabled, discarded, extended or failing | `tests/unit/pipeline/test_explicit_flow.py` |
| Close before terminal construction on success and failures; visible cleanup errors | `test_explicit_flow.py` and `test_host_capabilities.py` |
| Invalid assessment, completed zero, optional feedback failure | `test_terminal_outcome.py` and `test_explicit_flow.py` |
| Trusted compiled evaluators and repeated runs | `test_compiled_execution.py` and `test_explicit_flow.py` |
| AI coverage and direct assessment propagation | `test_ai_batch.py` and `tests/integration/test_result_comparator_integration.py` |
| Static parsing, scoped files and normalized commands | `tests/unit/test_evaluator_file_selection.py` and contribution/command integration tests |
| Host wire contracts and publication retries | `tests/web/` and `tests/unit/github_action/` |

The Docker pipeline integration tests now consume terminal outcomes. They still
require a running Docker host; fake-session tests do not establish real container
isolation or live provider availability.
