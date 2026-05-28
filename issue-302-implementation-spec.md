# Issue 302 Implementation Spec: Split PreFlight into granular setup steps

## Goal

Replace the current `PreFlightStep` "god step" with three single-purpose setup steps while keeping the rest of the grading pipeline behavior stable:

1. `FileCheckStep` for required file validation
2. `AssetInjectionStep` for sandbox asset copy-in
3. `SetupCommandsStep` for setup/compilation command execution

Also add step categorization, allow templates to contribute setup requirements, and update every consumer that still assumes one monolithic `PreFlightStep`.

## Current state

The current flow is:

`LOAD_TEMPLATE -> BUILD_TREE -> SANDBOX -> PRE_FLIGHT -> AI_BATCH -> STRUCTURAL_ANALYSIS -> GRADE -> FOCUS -> FEEDBACK -> EXPORTER`

Relevant code paths:

- `autograder/autograder.py` builds the pipeline order.
- `autograder/steps/step_registry.py` decides which steps are included.
- `autograder/steps/pre_flight_step.py` currently handles:
  - required file validation
  - asset injection
  - setup commands
- `autograder/services/pre_flight_service.py` resolves language-specific setup config and executes setup commands.
- `autograder/serializers/pipeline_execution_serializer.py` still special-cases `PRE_FLIGHT`.
- `autograder/utils/feedback_generator.py` and `web/service/grading_service.py` still look for `PreFlightStep`.

## Target behavior

### Final pipeline order

`LOAD_TEMPLATE -> BUILD_TREE -> FILE_CHECK -> SANDBOX -> ASSET_INJECTION -> SETUP_COMMANDS -> AI_BATCH -> STRUCTURAL_ANALYSIS -> GRADE -> FOCUS -> FEEDBACK -> EXPORTER`

Step inclusion rules:

| Step | Include when | Notes |
|------|--------------|-------|
| `FileCheckStep` | merged required files are non-empty | Must run before sandbox allocation |
| `SandboxStep` | any template requires sandbox OR any merged setup assets/commands exist | Sandbox is needed for asset injection and setup commands |
| `AssetInjectionStep` | merged assets are non-empty | Runs only after sandbox exists |
| `SetupCommandsStep` | merged setup commands are non-empty | Runs only after sandbox exists |

### Step categories

Add a `category`/`step_type` attribute to `Step` and expose a shared enum:

| Category | Intended steps |
|----------|----------------|
| `SETUP` | bootstrap, load template, build tree, file check, sandbox, asset injection, setup commands |
| `GRADING` | AI batch, structural analysis, grade, focus |
| `REPORTING` | feedback, exporter |

The category is primarily metadata, but it should be available on every step and registered centrally so later pipeline tooling can filter by phase.

### Template-level setup requirements

Templates should be able to contribute setup requirements in addition to assignment-level `setup_config`.

The merged setup payload should:

- keep assignment `setup_config` as the base
- merge template-provided `required_files`
- merge template-provided `setup_commands`
- preserve assignment-level `assets`
- keep language-specific resolution behavior unchanged

Important: merge raw config before step construction, but keep language resolution inside the existing `SetupConfig` / `PreFlightService` flow so the runtime still picks the correct language block from the submission.

## Design by component

### 1) Step model and registry

Files:

- `autograder/models/dataclass/step_result.py`
- `autograder/models/abstract/step.py`
- `autograder/steps/step_registry.py`

Required changes:

- Add `StepCategory` enum with `SETUP`, `GRADING`, `REPORTING`.
- Add a `category` property to `Step`.
- Update every existing step class to return a category.
- Teach `StepRegistry` to build the new setup steps and to stop registering `PRE_FLIGHT`.

### 2) New step classes

Files to add:

- `autograder/steps/file_check_step.py`
- `autograder/steps/asset_injection_step.py`
- `autograder/steps/setup_commands_step.py`

Behavior:

#### `FileCheckStep`

- Reads the merged required files for the current submission language.
- Fails fast before sandbox creation.
- Emits structured error data for missing files.
- Should reuse the existing file-check logic from `PreFlightService` rather than duplicating resolution rules.

#### `AssetInjectionStep`

- Requires an existing sandbox.
- Resolves assets with `AssetSourceResolver`.
- Injects resolved assets with `SandboxContainer.inject_assets(...)`.
- Fails with a distinct structured error type for asset injection failures.

#### `SetupCommandsStep`

- Requires an existing sandbox.
- Runs commands sequentially.
- Stops on the first failing command.
- Reuses the current command execution/error formatting logic from `PreFlightService` and `SandboxService`.

### 3) Setup config merging

Files:

- `autograder/autograder.py`
- `autograder/models/abstract/template.py`
- `autograder/services/template_library_service.py` if template metadata is surfaced

Required changes:

- Add optional template-level setup requirement accessors to `Template`.
- Keep default behavior empty so existing templates do not need changes beyond the interface.
- Merge all template contributions into the assignment `setup_config` before step construction.
- If multiple templates contribute the same file or command, de-duplicate while preserving order.

Recommended merge rules:

1. assignment config wins for shared structure
2. template values are appended
3. duplicates are removed
4. empty values are ignored

### 4) Pipeline execution reporting

Files:

- `autograder/serializers/pipeline_execution_serializer.py`
- `autograder/utils/feedback_generator.py`
- `web/service/grading_service.py`

Required changes:

- Stop special-casing `PreFlightStep` only.
- Treat any of the three setup steps as preflight/setup failures.
- Update `failed_at_step`, step messages, and `error_details` mapping.
- Replace the hard-coded `total_steps_planned = 7` with a value derived from the actual registered steps.
- Add category-aware success messages for:
  - `FILE_CHECK`
  - `ASSET_INJECTION`
  - `SETUP_COMMANDS`

### 5) Compatibility/deprecation

Files:

- `autograder/steps/pre_flight_step.py`
- `autograder/models/dataclass/step_result.py`
- docs under `autograder/docs/`

Required changes:

- `PreFlightStep` should no longer be part of the pipeline.
- `StepName.PRE_FLIGHT` should not be emitted by new runs.
- Keep compatibility shims only if needed for imports or old tests, but new orchestration must use the split steps.

## Error model guidance

Keep the existing structured error approach, but extend it so the new steps are distinguishable.

Suggested mapping:

| Failure source | Structured type |
|----------------|-----------------|
| missing required file | `FILE_CHECK` |
| asset copy failure | `ASSET_INJECTION` |
| setup command failure | `SETUP_COMMAND` |
| missing sandbox for setup work | `SANDBOX_CREATION` or a dedicated setup/sandbox type |

The serializer and feedback generator should read these types instead of parsing step names.

## Docs to update

Update docs that currently describe `PreFlightStep` as a single stage:

- `autograder/docs/pipeline/04-pre-flight.md`
- `autograder/docs/pipeline/README.md`
- `autograder/docs/architecture/pipeline_execution_tracking.md`
- `autograder/docs/architecture/core_structures.md`
- `autograder/docs/features/setup_config_feature.md`
- `autograder/docs/API.md`
- `autograder/web/README.md`

## Tests that should exist after implementation

### Unit

- `tests/unit/test_language_specific_setup_config.py`
- new tests for `FileCheckStep`, `AssetInjectionStep`, `SetupCommandsStep`
- serializer tests for the new setup step names and failure details
- feedback generation tests for all setup failure types
- pipeline builder tests that verify sandbox inclusion when assets/commands exist

### Integration

- full local-sandbox pipeline test covering:
  - assignment creation
  - submission creation
  - file check failure
  - asset injection success
  - setup command success/failure
  - final submission result payload

### Web/API

- grading service tests updated for new setup step names
- submission result serialization tests updated for new pipeline summary shape

## Implementation order

1. Add step category metadata and new step names.
2. Split `PreFlightStep` into the three setup steps.
3. Merge template-level setup requirements into the pipeline config.
4. Update registry and pipeline ordering.
5. Update serializer, feedback, and web service consumers.
6. Refresh tests and docs.

## Validation expectations

After implementation, the code should still satisfy:

- `pytest` passes
- local autograder API runs in local sandbox mode
- assignment creation and submission grading still work end-to-end
- pipeline logs show the new step breakdown
- submission result payloads expose the full execution trail, including step-by-step setup failures and command output

