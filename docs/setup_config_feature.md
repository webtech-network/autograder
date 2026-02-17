# Setup Config Feature - Compilation in Preflight

## Overview

The autograder now supports a `setup_config` field in grading configurations that allows compilation and other setup commands to be executed during the **preflight step** before grading begins.

This feature improves efficiency by:
- Separating compilation from test execution
- Detecting compilation errors early (before running tests)
- Providing clearer error messages for compilation failures
- Avoiding repeated compilation commands in test definitions

## Setup Config Structure

The `setup_config` is an optional JSON object with the following fields:

```json
{
  "required_files": ["Calculator.java", "Helper.java"],
  "setup_commands": ["javac Calculator.java", "javac Helper.java"]
}
```

### Fields

- **`required_files`** (optional): List of files that must be present in the submission
  - Type: `Array<string>`
  - If any required file is missing, the submission fails immediately
  - Example: `["Calculator.java", "Main.java"]`

- **`setup_commands`** (optional): List of shell commands to execute during preflight
  - Type: `Array<string>`
  - Commands are executed in order in the sandbox environment
  - If any command fails (non-zero exit code), the submission fails
  - Typical use: compilation commands
  - Example: `["javac *.java", "g++ -o program main.cpp"]`

## Language-Specific Examples

### Java
```json
{
  "required_files": ["Calculator.java"],
  "setup_commands": ["javac Calculator.java"]
}
```

Then your test commands can simply use:
```json
{
  "program_command": "java Calculator"
}
```

### C++
```json
{
  "required_files": ["calculator.cpp"],
  "setup_commands": [
    {
      "name": "Compile calculator.cpp",
      "command": "g++ calculator.cpp -o calculator"
    }
  ]
}
```

Then your test commands can use:
```json
{
  "program_command": "./calculator"
}
```

### Python
Python doesn't need compilation, but you can still validate files:
```json
{
  "required_files": ["calculator.py"],
  "setup_commands": ["python3 -m py_compile calculator.py"]
}
```

### JavaScript/Node.js
```json
{
  "required_files": ["calculator.js", "package.json"],
  "setup_commands": ["npm install"]
}
```

## API Changes

### Creating a Grading Configuration

**Endpoint**: `POST /api/v1/configs`

**Request Body**:
```json
{
  "external_assignment_id": "java-calc-001",
  "template_name": "input_output",
  "language": "java",
  "criteria_config": {
    "base": {
      "weight": 100,
      "tests": [
        {
          "name": "expect_output",
          "parameters": [
            {"name": "inputs", "value": ["add", "5", "3"]},
            {"name": "expected_output", "value": "8"},
            {"name": "program_command", "value": "java Calculator"}
          ]
        }
      ]
    }
  },
  "setup_config": {
    "required_files": ["Calculator.java"],
    "setup_commands": ["javac Calculator.java"]
  }
}
```

### Response Example

```json
{
  "id": 1,
  "external_assignment_id": "java-calc-001",
  "template_name": "input_output",
  "language": "java",
  "criteria_config": { ... },
  "setup_config": {
    "required_files": ["Calculator.java"],
    "setup_commands": [
      {
        "name": "Compile Calculator.java",
        "command": "javac Calculator.java"
      }
    ]
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
    "setup_commands": [
      {
        "name": "Compile Calculator.java",
        "command": "javac Calculator.java"
      }
    ]
  },
  "criteria_config": {
    "tests": [{
      "program_command": "java Calculator"
    }]
  }
}
```
Benefits:
- Compilation happens **once** during preflight
- Clear separation of compilation vs runtime errors
- Faster test execution
- Better error reporting

## Web UI Updates

The test dashboard (`tests/assets/input_output/`) has been updated to automatically include setup_config:

- Java: Adds `javac Calculator.java` to setup_commands
- C++: Adds `g++ calculator.cpp -o calculator` to setup_commands
- Python/JavaScript: No compilation needed

The updated files have a cache-busting parameter `?v=2` to ensure browsers load the new version.

## Backward Compatibility

**Breaking Change**: This update adds a new column to the database and changes the API contract.

However, since the API is not yet in production use:
- Existing configs without `setup_config` will work (field is nullable)
- Old code using inline compilation (`javac ... && java ...`) will still work
- Migration is straightforward

## Implementation Details

### Code Changes

1. **Schemas** (`web/schemas/assignment.py`):
   - Added `setup_config` to `GradingConfigCreate`
   - Added `setup_config` to `GradingConfigUpdate`
   - Added `setup_config` to `GradingConfigResponse`

2. **Database Model** (`web/database/models/grading_config.py`):
   - Added `setup_config: Mapped[Optional[dict]]` column

3. **API Endpoint** (`web/main.py`):
   - Updated `create_grading_config` to accept `setup_config`
   - Updated `grade_submission` to pass `setup_config` to pipeline

4. **Migration**:
   - Created `c7d8e9f0g1h2_add_setup_config_to_grading_configurations.py`

5. **Web UI** (`tests/assets/input_output/shared.js`):
   - Separated compilation from runtime commands
   - Added `setupConfigs` object with language-specific setup

## Testing

To test the new feature:

1. Run the database migration:
   ```bash
   cd web
   alembic upgrade head
   ```

2. Start the API server:
   ```bash
   cd web
   python main.py
   ```

3. Open the test dashboard:
   ```
   tests/assets/input_output/index.html
   ```

4. Create a configuration with Java language
5. Submit Java code
6. Verify compilation happens in preflight and errors are clear

## Future Enhancements

Potential improvements:
- Add timeout for setup commands
- Support for multi-stage compilation
- Environment variables for setup commands
- Setup command output in submission details
- Cached compilation results for identical code

