# Step 4: Sandbox

## Purpose

The Sandbox step is responsible for preparing a secure, isolated environment where the student's code can be executed. This separates the autograder's internal logic from the potentially unsafe student code.

This step performs three main functions:
1. **Acquiring a sandbox**: Getting a container from the pool.
2. **Mounting files**: Copying the submission files into the sandbox.
3. **Running setup commands**: Executing compilation or initialization scripts.

## How It Works

The step execution follows these logic gates:

1. **Check Template Requirements**: The step first checks the loaded `Template`. If `template.requires_sandbox` is `False` (e.g., for a static HTML validation assignment), the step immediately succeeds with `data=None` and does nothing.

2. **Sandbox Creation**: If required, a sandbox container is requested from the `SandboxManager` for the specific submission language.

3. **Workspace Preparation**: All submission files are streamed into the sandbox's working directory.

4. **Setup Commands Execution**: If the `setup_config` for the submission's language contains `setup_commands`, they are executed sequentially.
    - If any command fails (non-zero exit code), the entire step fails.
    - Common setup commands include `javac Main.java` for Java or `npm install` for Node.js assignments.

The resulting `SandboxContainer` object is stored in the step result's `data` field and also attached to the `PipelineExecution` object for easy access by subsequent grading steps.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Load Template** | Reads `template.requires_sandbox` to determine if action is needed |

## Input

| Source | Data |
|--------|------|
| Constructor | `setup_config: dict` — language-keyed setup configuration (for setup commands) |
| Pipeline | `StepName.LOAD_TEMPLATE` → `Template` |
| Pipeline | `pipeline_exec.submission` → submission files and language |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `SandboxContainer \| None` | Reference to the prepared sandbox, or `None` if not required |
| `status` | `StepStatus.SUCCESS` | Sandbox was successfully created and setup commands passed |

## Failure Scenarios

- **Sandbox Pool Exhausted** → `StepStatus.FAIL` with infrastructure error details.
- **Setup Command Failed** → `StepStatus.FAIL` with the command's exit code, stdout, and stderr.
- **File Transfer Error** → `StepStatus.FAIL`.

## Sandbox Lifecycle

The sandbox created in this step is **persisted** throughout the remaining pipeline.
- It is used by the **[Step 5: Grade](05-grade.md)** step to run tests.
- It is **automatically released** back to the pool by the `AutograderPipeline` orchestrator once the `run()` method finishes, regardless of whether the pipeline succeeded, failed, or was interrupted.

## Next Step

Once the environment is ready and code is compiled, the pipeline proceeds to **[Step 5: Grade](05-grade.md)** to execute the actual test functions.

---

## Source

`autograder/steps/sandbox_step.py` → `SandboxStep`

`autograder/services/pre_flight_service.py` → `PreFlightService`
