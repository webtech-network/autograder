# Grading pipeline

`build_pipeline(definition=...)` compiles and normalizes the versioned definition
before execution. Compilation resolves evaluator implementations and validates
all structural/parameter/language requirements without requesting infrastructure
or providers. The host can pass exact definition provenance and trusted template
implementations. Invalid definitions never reach evaluation.

```text
LOAD_TEMPLATE -> BUILD_TREE -> SANDBOX? -> PRE_FLIGHT? -> AI_BATCH?
              -> STRUCTURAL_ANALYSIS -> GRADE -> FOCUS -> FEEDBACK?
```

`AutograderPipeline.run(submission)` selects the definition's language, creates
an internal `PipelineExecution`, and executes the configured steps. Typed
accessors expose intermediate resources to later steps. AI batches bind outputs
to criterion IDs, including repeated uses of the same evaluator.

A required step/evaluator failure stops assessment and produces a failed outcome
with null score/tree. Student compilation/runtime/timeouts reported by an I/O
evaluator are assessed criterion failures. Focus and feedback are optional
enrichment: their failure preserves any completed grade and records an
independent feedback failure.

Resource cleanup runs in `finally`, then finalization builds the immutable
versioned `execution.outcome`. The pipeline returns after cleanup, even when
steps or finalization fail. `execution.result` contains a completed internal
`GradingResult` or is `None` on failed grading. It is not an integration payload.

The hosting adapter serializes the finalized outcome, persists or publishes it,
and owns delivery retries. There is no exporter step or publisher argument to
the engine. Publishing twice never requires grading twice, and publication
failure cannot turn completed grading into a failed student grade.

Read the [definition decisions](../contracts/DECISIONS.md),
[terminal outcome/failure matrix](../contracts/OUTCOMES.md), and
[internal diagnostics](../architecture/pipeline_execution_tracking.md).
