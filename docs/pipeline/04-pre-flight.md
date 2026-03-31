# Step 4: Pre-Flight

## Purpose

The Pre-Flight step runs initial validation checks on the submission and prepares the code for grading. It acts as the final "gatekeeper" that ensures both the file structure is correct and the code is in an executable state (e.g., compiled).

This step performs two main functions:
1. **Required files check**: Ensuring all mandatory files defined in the assignment configuration exist.
2. **Setup commands execution**: Running compilation or initialization scripts (e.g., `javac`, `npm install`, `gcc`) inside the sandbox.

## How It Works

The step execution follows these logic gates:

1. **Required Files Check**: It compares the files in the submission against the list provided in the `required_files` section of the `setup_config` for the submission's language.

2. **Setup Commands Execution**: If the `setup_config` contains `setup_commands`, they are executed sequentially within the sandbox created in **Step 3**.
    - **Stop on Failure**: If any command fails (non-zero or invalid response), the step **stops immediately** and fails the entire pre-flight check. Subsequent commands are not executed.
    - Setup commands are orchestrated via the `SandboxService`.

If both checks pass, the step succeeds and the pipeline continues to **Step 5: Grade**.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Sandbox** | Requires the `SandboxContainer` to execute setup commands |

## Input

| Source | Data |
|--------|------|
| Constructor | `setup_config: dict` — language-keyed setup configuration |
| Pipeline | `StepName.SANDBOX` → `SandboxContainer` |
| Pipeline | `pipeline_exec.submission` → submission files and language |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `None` | This step does not produce data for downstream steps |
| `status` | `StepStatus.SUCCESS` | Required files exist and all setup commands passed |

## Language-Specific Configuration

The `setup_config` defines mandatory files and commands for each language:

```json
{
  "python": {
    "required_files": ["main.py"],
    "setup_commands": []
  },
  "java": {
    "required_files": ["Calculator.java"],
    "setup_commands": ["javac Calculator.java"]
  }
}
```

## Failure Scenarios

- **Missing required file** → `StepStatus.FAIL` listing missing files.
- **Setup Command Failed** → `StepStatus.FAIL` with the command's exit code, stdout, and stderr.
- **No Sandbox** → `StepStatus.FAIL` if setup commands exist but no sandbox was provided.

## Next Step

After verification and compilation, the pipeline proceeds to **[Step 5: Grade](05-grade.md)** to execute the actual test functions.

---

## Source

`autograder/steps/pre_flight_step.py` → `PreFlightStep`

`autograder/services/pre_flight_service.py` → `PreFlightService`

`autograder/services/sandbox_service.py` → `SandboxService`
