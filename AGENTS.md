# Autograder — contributor reference

Read this reference before changing the repository. Phase-2 integration decisions
are recorded in [docs/contracts/DECISIONS.md](docs/contracts/DECISIONS.md), following
#363. Reduce the concepts a developer must understand; remove obsolete paths
before adding abstractions. Breaking contract changes require migration evidence.

## Boundaries

`autograder/` implements grading semantics. `web/` and `github_action/` are hosts:
they collect files, authenticate, select configuration identity, accept work,
persist/publish results and retry delivery. `sandbox_manager/` supplies execution
infrastructure. Core must never import adapters or interpret platform identities,
repository changes, database IDs, or workflow job names.

The current sandbox/AI implementations still use concrete services. A future
host-capability/provisioning redesign (#376/#377) should remove that coupling;
this document does not pretend those boundaries have already been implemented.

## Public Python and JSON contracts

```python
from autograder import compile_definition, build_pipeline
compiled = compile_definition(definition_json)
pipeline = build_pipeline(definition=compiled)
execution = pipeline.run(submission)
terminal_json = execution.outcome.model_dump(mode="json")
```

`GradingDefinition` v1 is one object: `schema_version`, `templates`, `languages`,
`criteria`, optional `preparation`, `feedback`, and `metadata`. Every test has
stable `id`, evaluator `type`, display `name`, object-valued `parameters`, and
relative `weight`. Unknown structural fields and runtime-parameter collisions
are rejected. There are no live list-parameter/name-fallback/test_library paths.

`compile_definition` resolves the registry, validates and normalizes evaluator
parameters, and builds the criteria tree without Docker/network/provider calls.
The normalized values are the ones executed. Built-in evaluator discovery exposes
JSON Schema derived from these same contracts. Trusted Python templates can be
supplied with `templates={identifier: TemplateInstance}`; uploaded code is not
supported. Preserve injected templates when passing a compiled definition.

See [DEFINITIONS.md](docs/contracts/DEFINITIONS.md) and the checked-in v1 JSON
Schemas and valid/invalid examples. The offline converter is an explicit migration
tool, never a fallback inside the public parser.

## Submission and execution

`Submission` contains files (`SubmissionFile` filename/content), opaque submitter
and assignment identifiers, optional language, locale, and optional evaluation
scope. Adapters decide which files to collect. Domain-specific file context goes
in metadata; core owns only typed values it must actually interpret.

Language is inferred for a single-language definition. Multiple allowed languages
require explicit selection. Disallowed language and unavailable execution
capability are different failures. Runtime context cannot be assignment-authored.

The recursive tree retains base/bonus/penalty, nested subjects, tests and the
explicit mixed-group `subjects_weight` split. Sibling weights are ratios; all-zero
siblings share equal weight. Base weight is 100. Bonus adds `score/100 * cap`;
penalty subtracts `(100-score)/100 * cap`; final score clamps to 0–100.

`TestNode` embeds an evaluator implementation, normalized parameters, file target,
weight and criterion ID. Display names may repeat or contain slashes: they never
identify AI batch outputs, result leaves, score vectors, or comparison deltas.

The pipeline uses typed accessors on its internal mutable `PipelineExecution`:

```
LOAD_TEMPLATE → BUILD_TREE → SANDBOX? → PRE_FLIGHT? → AI_BATCH?
              → STRUCTURAL_ANALYSIS → GRADE → FOCUS → FEEDBACK?
```

Optional resource steps depend on selected tests/preparation, not merely other
unused evaluators in a template. Batch AI results must exactly cover criterion
IDs. There is no provider retry fallback or silent zero for missing assessments.

Required failures produce null score/tree. Student compilation/runtime/timeout
reported during evaluator assessment can produce a valid zero. Preparation
failures stop before assessment. Optional focus/feedback/comparison failures
preserve the completed grade with a separate enrichment status.

`execution.outcome` is the immutable versioned terminal integration artifact.
`execution.result` and step diagnostics are internal. Cleanup runs on all execution
paths before returning to the adapter. Never publish mutable `PipelineExecution`.
See [OUTCOMES.md](docs/contracts/OUTCOMES.md) for the failure matrix and invariants.

## Adding an evaluator

1. Implement `TestFunction` (or `AiTestFunction`) locally.
2. Provide a parameter contract. Annotated `execute` keyword signatures derive a
   strict contract; implementations reading `**kwargs` supply `config_schema`.
3. Register the instance under its explicit `name` in a trusted `Template`.
4. Reference the registry key as criterion `type`, with a distinct instance `id`.

Do not add adapter vocabulary or a new pipeline framework for one evaluator.
Provider/system failure raises `EvaluationError` with a fixed safe public message;
ordinary assessment returns a finite `TestResult` in 0–100.

## Adapter contracts and publication

HTTP config resources have canonical IDs, assignment aliases, semantic revisions
and conditional PATCH. Each accepted execution binds a definition snapshot/hash
and revision. Activation gates new acceptance, not already bound jobs. Legacy
history is explicitly unverified, never attributed to today's definition.

HTTP polling is compact, authenticated details contain the full artifact/files,
and history is bounded and deterministically ordered. External results are
validated authenticated host attestations with the exact snapshot and provenance;
they are not proof that this server executed the grader.

The engine finalizes/cleans up before adapter publication. No exporter step, sink
interface, Upstash, Classroom check mutation, or automatic feedback commit remains.
Actions saves a canonical artifact before explicit optional cloud publication;
HTTP saves a private publication receipt before database delivery. Delivery retry
reuses the finalized outcome without grading again. Never report a completed
grade as failed because a sink failed. Scheduling/idempotent submission acceptance
remain separate work items; receipt replay is not a durable job queue.

## Verification

Run meaningful tests for changed behavior. Contract tests cover compile purity,
actual execution of normalized values, invalid paths, outcome invariants, snapshots,
optimistic concurrency, migrations, adapter wire parity and publication retry.
Docker integration tests exercise real grading isolation. Preserve unrelated work;
use a clean worktree for delivery. Do not add co-author commit trailers.
