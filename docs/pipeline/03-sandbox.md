# Step 3: Sandbox

## Purpose

The Sandbox step is responsible for preparing a secure, isolated environment where the student's code can be executed. This separates the autograder's internal logic from the potentially unsafe student code.

This step performs two main functions:
1. **Acquiring a sandbox**: Getting a container from the pool.
2. **Mounting files**: Copying the submission files into the sandbox's working directory.

## How It Works

The step execution follows these logic gates:

1. **Check Template Requirements**: The step first checks the loaded `Template`. If `template.requires_sandbox` is `False` (e.g., for a static HTML validation assignment), the step immediately succeeds with `data=None` and does nothing.

2. **Sandbox Creation**: If required, a sandbox container is requested from the `SandboxManager` (via `SandboxService`) for the specific submission language.

3. **Workspace Preparation**: All submission files are streamed into the sandbox's working directory.

The resulting `SandboxContainer` object is stored in the step result's `data` field and also attached to the `PipelineExecution` object for use by subsequent steps.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Load Template** | Reads `template.requires_sandbox` to determine if action is needed |

## Input

| Source | Data |
|--------|------|
| Pipeline | `StepName.LOAD_TEMPLATE` → `Template` |
| Pipeline | `pipeline_exec.submission` → submission files and language |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `SandboxContainer | None` | Reference to the prepared sandbox, or `None` if not required |
| `status` | `StepStatus.SUCCESS` | Sandbox was successfully created and files were mounted |

## Failure Scenarios

- **Sandbox Pool Exhausted** → `StepStatus.FAIL` with infrastructure error details.
- **Submission Language Missing** → `StepStatus.FAIL` if the submission didn't specify a language required for the sandbox.
- **File Transfer Error** → `StepStatus.FAIL`.

## Sandbox Lifecycle

The sandbox created in this step is **persisted** throughout the remaining pipeline.
- It is used by **[Step 4: Pre-Flight](04-pre-flight.md)** to run setup commands.
- It is used by **[Step 5: Grade](05-grade.md)** to run tests.
- It is **automatically released** back to the pool by the `AutograderPipeline` orchestrator once the `run()` method finishes, regardless of the outcome.

## Next Step

After environment preparation, the pipeline proceeds to **[Step 4: Pre-Flight](04-pre-flight.md)** to validate the submission structure and compile the code.

---

## Source

`autograder/steps/sandbox_step.py` → `SandboxStep`

`autograder/services/sandbox_service.py` → `SandboxService`
