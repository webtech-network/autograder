# Step 3: Pre-Flight

## Purpose

The Pre-Flight step runs initial validation checks on the submission before any processing or execution happens. Its primary responsibility is to ensure that the student has submitted all the **required files** defined in the assignment configuration.

This step acts as a "gatekeeper" — if a mandatory file is missing, the pipeline fails immediately, providing clear feedback to the student without attempting to build a test tree or create a sandbox.

## How It Works

The step performs a single, critical check:

1. **Required files check** — It compares the files in the submission against the list of filenames provided in the `required_files` section of the `setup_config` for the submission's language.

If all required files are present, the step succeeds and the pipeline continues to the **Sandbox** step. If any file is missing, the step fails.

## Dependencies

| Step | What It Needs |
|------|---------------|
| — | None |

## Input

| Source | Data |
|--------|------|
| Constructor | `setup_config: dict` — language-keyed setup configuration |
| Pipeline | `pipeline_exec.submission` → submission files and language |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `None` | This step does not produce data for downstream steps |
| `status` | `StepStatus.SUCCESS` | All required files are present |

## Language-Specific Configuration

The `setup_config` defines which files are mandatory for each language:

```json
{
  "python": {
    "required_files": ["main.py"]
  },
  "java": {
    "required_files": ["Calculator.java"]
  }
}
```

For a comprehensive explanation of the setup configuration system, see the **[Setup Config Feature](../features/setup_config_feature.md)** documentation.

## Failure Scenarios

- **Missing required file** → `StepStatus.FAIL` with an error message listing the missing files.
- **Empty submission** → `StepStatus.FAIL` (if any files were required).

## Next Step

After file verification, the pipeline proceeds to **[Step 4: Sandbox](04-sandbox.md)** (if required) to prepare the execution environment.

---

## Source

`autograder/steps/pre_flight_step.py` → `PreFlightStep`

`autograder/services/pre_flight_service.py` → `PreFlightService`

