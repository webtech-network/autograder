# Step 3: Pre-Flight

## Purpose

The Pre-Flight step runs validation checks on the submission before grading begins. It ensures the student submitted the right files, creates a sandbox environment if the template requires code execution, and runs setup commands (like compilation) inside the sandbox. This step catches problems early — a missing file or compilation error is reported immediately instead of surfacing as a confusing test failure.

## How It Works

The step executes checks in a strict order:

1. **Required files check** — Verifies that all files listed in the language-specific `required_files` config are present in the submission. If any are missing, the step fails immediately without proceeding to sandbox creation or setup commands.

2. **Sandbox creation** — If the loaded template's `requires_sandbox` property is `True`, a sandbox container is acquired from the `SandboxManager` pool for the submission's language. The submission files are copied into the container's working directory.

3. **Setup commands** — If the language-specific config includes `setup_commands`, they are executed sequentially inside the sandbox. Commands can be simple strings (`"javac Calculator.java"`) or named objects (`{"name": "Compile", "command": "javac Calculator.java"}`). If any command returns a non-zero exit code, the step fails with detailed error output (stdout, stderr, exit code).

The sandbox reference (or `None` if no sandbox was needed) is stored in the step result's `data` field for the Grade step to use.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Load Template** | Checks `template.requires_sandbox` to decide whether to create a sandbox |

## Input

| Source | Data |
|--------|------|
| Constructor | `setup_config: dict` — language-keyed setup configuration |
| Pipeline | `StepName.LOAD_TEMPLATE` → `Template` |
| Pipeline | `pipeline_exec.submission` → submission files and language |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `SandboxContainer \| None` | Reference to the created sandbox, or `None` if no sandbox was needed |
| `status` | `StepStatus.SUCCESS` | All checks passed |

## Language-Specific Configuration

The `setup_config` uses a language-keyed dictionary. At runtime, `PreFlightService` resolves the block matching the submission's language:

```json
{
  "python": {
    "required_files": ["calculator.py"],
    "setup_commands": []
  },
  "java": {
    "required_files": ["Calculator.java"],
    "setup_commands": ["javac Calculator.java"]
  }
}
```

A Python submission uses the `"python"` block; a Java submission uses `"java"`. If the language isn't present, an empty config is used (no checks).

For a comprehensive explanation of the setup configuration system, including all formats, API usage, and migration details, see the **[Setup Config Feature](../features/setup_config_feature.md)** documentation.

## Failure Scenarios

- Missing required file → `StepStatus.FAIL` with error listing the missing filename.
- Setup command returns non-zero exit code → `StepStatus.FAIL` with formatted error including command name, exit code, stdout, and stderr.
- Sandbox creation fails (e.g., pool exhausted) → `StepStatus.FAIL` with error details.
- Workdir preparation fails → sandbox is released back to pool, step fails.

## Sandbox Lifecycle

The sandbox created in this step is **not destroyed here**. It is passed forward through the pipeline via the step result and used by the Grade step to execute tests. After the pipeline finishes (success or failure), the `AutograderPipeline.run()` method handles cleanup by releasing the sandbox back to the pool.

## Source

`autograder/steps/pre_flight_step.py` → `PreFlightStep`

`autograder/services/pre_flight_service.py` → `PreFlightService`
