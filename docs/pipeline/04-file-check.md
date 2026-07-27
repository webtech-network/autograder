# Step 4: File Check

## Purpose

The File Check step validates that all required files exist in the student's submission before proceeding with sandbox execution. This provides a fast-fail mechanism that gives students immediate feedback about missing files without consuming sandbox resources.

## How It Works

The step execution follows these logic gates:

1. **Load Configuration**: The step reads the `setup_config` for the submission's language and extracts the `required_files` list. If no required files are configured, the step immediately succeeds.

2. **Check Submission Files**: The `PreFlightService` compares the list of required files against the actual files present in the submission.

3. **Report Results**: If any required files are missing, the step fails with a descriptive error listing all missing files. Otherwise, it succeeds.

## Dependencies

| Step | What It Needs |
|------|---------------|
| None | This step only needs the submission files from the pipeline context |

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

The `required_files` list is defined per language in the `setup_config`:

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

Templates can also contribute required files via `template.required_files`, which are merged with the assignment-level configuration during pipeline assembly.

## Failure Scenarios

- **Missing required file** → `StepStatus.FAIL` with an error message listing all missing files.

## Next Step

After file validation, the pipeline proceeds to **[Step 3: Sandbox](03-sandbox.md)** to prepare the execution environment (if the submission requires it).

---

## Source

`autograder/steps/file_check_step.py` → `FileCheckStep`

`autograder/services/pre_flight_service.py` → `PreFlightService`
