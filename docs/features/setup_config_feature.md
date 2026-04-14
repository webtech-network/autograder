# Setup Config Feature

## Overview

The autograder supports a `setup_config` field in grading configurations that allows **language-specific** preflight checks before grading begins. Each supported language gets its own `required_files` and `setup_commands` block, and the pipeline resolves the correct block at runtime based on the submission's language.

This feature:
- Separates compilation from test execution
- Detects compilation errors early (before running tests)
- Provides clearer error messages for compilation failures
- Supports different file requirements per language

## Setup Config Structure

The `setup_config` uses a **language-keyed dictionary** format, with an optional root-level `assets` list for global static assets:

```json
{
  "setup_config": {
    "assets": [
      {
        "source": "datasets/tp2/RESTAURANTES.CSV",
        "target": "/tmp/RESTAURANTES.CSV",
        "read_only": true
      }
    ],
    "python": {
      "required_files": ["calculator.py"],
      "setup_commands": []
    },
    "java": {
      "required_files": ["Calculator.java"],
      "setup_commands": ["javac Calculator.java"]
    },
    "node": {
      "required_files": ["calculator.js"],
      "setup_commands": ["npm install"]
    },
    "cpp": {
      "required_files": ["calculator.cpp"],
      "setup_commands": ["g++ calculator.cpp -o calculator"]
    }
  }
}
```

### Static Assets (Global)

The root-level `assets` field allows injecting grader-owned files (e.g., datasets, test fixtures) from a trusted S3 provider into the sandbox environment before setup commands and grading execution.

- **`assets`** (optional): List of assets to inject
  - **`source`**: Required. Relative path to the file in the configured S3 bucket (e.g., `datasets/RESTAURANTES.CSV`).
  - **`target`**: Required. Absolute path in the container where the file will be placed. Use a path under `/tmp/` (for example, `/tmp/RESTAURANTES.CSV`). Do not rely on non-`/tmp/` paths being automatically remapped.
  - **`read_only`**: Optional (default: `true`). If true, the file will be injected with `0444` permissions.

### Secure Injection Method

Assets are resolved and injected **before** language-specific setup commands run. The autograder uses a secure **Base64-encoded `exec_run`** method to inject files, which provides several benefits:
- **gVisor Compatibility**: Works seamlessly with high-isolation runtimes like gVisor (`runsc`).
- **Security**: Allows maintaining the `noexec` flag on `/tmp` while still supporting dynamic file injection.
- **Root-to-Sandbox Handover**: Files are created as `root` to ensure correct placement, then `chmod`ed to be readable by the non-privileged `sandbox` user.

### S3 Infrastructure Requirements

For asset injection to work, the autograder API must be configured with S3 credentials. In a development environment using the provided `docker-compose.yml`, this is handled by the `ministack` service.

Required environment variables:
- `CRITERIA_ASSETS_BUCKET_NAME`: The name of the S3 bucket.
- `S3_ENDPOINT_URL`: The URL of the S3 service (e.g., `http://ministack:4566`).
- `AWS_ACCESS_ID` & `AWS_SECRET_ACCESS_KEY`: Credentials for the S3 provider.

If an asset fails to resolve (e.g., file not found in S3) or inject, the preflight step fails.

### How Resolution Works

When a submission arrives, `PreFlightService` resolves the submission's language in the `setup_config` dictionary. For example, a Python submission uses the `"python"` block; a Java submission uses the `"java"` block. If the submission's language is not present in the config, an empty config is used (no checks, no commands). The `PreFlightService` then orchestrates the execution, calling `SandboxService` for each individual setup command.

### Fields (Per Language)

- **`required_files`** (optional): List of files that must be present in the submission
  - Type: `Array<string>`
  - If any required file is missing, the submission fails immediately

- **`setup_commands`** (optional): List of shell commands to execute during preflight
  - Type: `Array<string | object>`
  - Commands are executed **one by one** in the sandbox environment.
  - **Stop on Failure**: If any command fails (non-zero exit code or system error), execution **stops immediately** and the entire submission is marked as FAILED. Subsequent commands are not attempted.
  - Supports both string format (`"javac Calculator.java"`) and named object format (`{"name": "Compile", "command": "javac Calculator.java"}`)

## Language-Specific Examples

### Java
```json
{
  "java": {
    "required_files": ["Calculator.java"],
    "setup_commands": ["javac Calculator.java"]
  }
}
```

Then your test commands can simply use:
```json
{
  "program_command": {"java": "java Calculator"}
}
```

### C++
```json
{
  "cpp": {
    "required_files": ["calculator.cpp"],
    "setup_commands": [
      {
        "name": "Compile calculator.cpp",
        "command": "g++ calculator.cpp -o calculator"
      }
    ]
  }
}
```

### Python
Python doesn't need compilation, but you can validate files:
```json
{
  "python": {
    "required_files": ["calculator.py"],
    "setup_commands": ["python3 -m py_compile calculator.py"]
  }
}
```

### JavaScript/Node.js
```json
{
  "node": {
    "required_files": ["calculator.js", "package.json"],
    "setup_commands": ["npm install"]
  }
}
```

## API Usage

### Creating a Grading Configuration

**Endpoint**: `POST /api/v1/configs`

**Request Body**:
```json
{
  "external_assignment_id": "java-calc-001",
  "template_name": "input_output",
  "languages": ["python", "java", "cpp"],
  "criteria_config": {
    "base": {
      "weight": 100,
      "tests": [
        {
          "name": "expect_output",
          "parameters": [
            {"name": "inputs", "value": ["add", "5", "3"]},
            {"name": "expected_output", "value": "8"},
            {
              "name": "program_command",
              "value": {
                "python": "python3 calculator.py",
                "java": "java Calculator",
                "cpp": "./calculator"
              }
            }
          ]
        }
      ]
    }
  },
  "setup_config": {
    "python": {
      "required_files": ["calculator.py"],
      "setup_commands": []
    },
    "java": {
      "required_files": ["Calculator.java"],
      "setup_commands": ["javac Calculator.java"]
    },
    "cpp": {
      "required_files": ["calculator.cpp"],
      "setup_commands": [
        {
          "name": "Compile calculator.cpp",
          "command": "g++ calculator.cpp -o calculator"
        }
      ]
    }
  }
}
```

### Response Example

```json
{
  "id": 1,
  "external_assignment_id": "java-calc-001",
  "template_name": "input_output",
  "languages": ["python", "java", "cpp"],
  "criteria_config": { "..." : "..." },
  "setup_config": {
    "python": {
      "required_files": ["calculator.py"],
      "setup_commands": []
    },
    "java": {
      "required_files": ["Calculator.java"],
      "setup_commands": ["javac Calculator.java"]
    },
    "cpp": {
      "required_files": ["calculator.cpp"],
      "setup_commands": [
        {
          "name": "Compile calculator.cpp",
          "command": "g++ calculator.cpp -o calculator"
        }
      ]
    }
  },
  "version": 1,
  "created_at": "2026-02-17T10:00:00",
  "updated_at": "2026-02-17T10:00:00",
  "is_active": true
}
```

## Migration

A database migration has been created to add the `setup_config` column:

**File**: `web/migrations/versions/c7d8e9f0g1h2_add_setup_config_to_grading_configurations.py`

To apply the migration:
```bash
cd web
alembic upgrade head
```

## Preflight Error Handling

If any preflight check fails, the submission will be marked as FAILED with detailed error information:

### Missing Required File
```
**Erro:** Arquivo ou diretório obrigatório não encontrado: `'Calculator.java'`
```

### Compilation Error
```
**Error:** Setup command 'Compile Calculator.java' failed with exit code 1

**Command:** `javac Calculator.java`

**Error Output (stderr):**
```
Calculator.java:10: error: ';' expected
    System.out.println("Hello")
                               ^
1 error
```
```

## Benefits

### Before (Old Approach)
```json
{
  "program_command": "javac Calculator.java && java Calculator"
}
```
Problems:
- Compilation happens on **every test**
- Hard to distinguish compilation errors from runtime errors
- Slower execution
- Unclear error messages

### After (New Approach)
```json
{
  "setup_config": {
    "java": {
      "required_files": ["Calculator.java"],
      "setup_commands": [
        {
          "name": "Compile Calculator.java",
          "command": "javac Calculator.java"
        }
      ]
    }
  }
}
```
With test commands using:
```json
{
  "program_command": {"java": "java Calculator"}
}
```
Benefits:
- Compilation happens **once** during preflight
- Clear separation of compilation vs runtime errors
- Faster test execution
- Better error reporting
- Language-specific file requirements

## Backward Compatibility

- Existing configs without `setup_config` continue to work (field is nullable)
- The `setup_config` field is optional in both `GradingConfigCreate` and `GradingConfigUpdate`

## Implementation Details

### Code Changes

1. **Schemas** (`web/schemas/assignment.py`):
   - `setup_config` field on `GradingConfigCreate`, `GradingConfigUpdate`, and `GradingConfigResponse`

2. **Database Model** (`web/database/models/grading_config.py`):
   - `setup_config: Mapped[Optional[dict]]` column

3. **PreFlightService** (`autograder/services/pre_flight_service.py`):
   - Handles resolution and validation of required files.
   - Orchestrates the loop of setup commands, ensuring execution stops at the first failure.

4. **SandboxService** (`autograder/services/sandbox_service.py`):
   - Handles sandbox lifecycle (creation/release).
   - Executes individual setup commands within the sandbox and returns raw execution results.

5. **PreFlightStep** (`autograder/steps/pre_flight_step.py`):
   - The pipeline step that uses `PreFlightService` to perform all pre-grading validations.

6. **SandboxStep** (`autograder/steps/sandbox_step.py`):
   - Uses `SandboxService` to acquire and prepare the environment *before* pre-flight checks occur.

## Related Documentation

- [Command Resolver & Multi-Language Support](command_resolver.md) — How command resolution works across languages
- [Configuration Examples](../guides/criteria_configuration_examples.md) — Full grading configuration examples
- [Pipeline Execution Tracking](../architecture/pipeline_execution_tracking.md) — How preflight results appear in pipeline summaries

