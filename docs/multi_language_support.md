**# Multi-Language Program Command Resolution

## Overview

The autograder now supports **dynamic command resolution** based on the submission's programming language. This allows a single grading configuration to accept submissions in multiple languages (Python, Java, Node.js, C++) without requiring separate configurations for each language.

## The Problem

Previously, grading criteria had to hardcode a single program command:

```json
{
  "name": "expect_output",
  "parameters": [
    {"name": "inputs", "value": ["5", "3"]},
    {"name": "expected_output", "value": "8"},
    {"name": "program_command", "value": "python3 calculator.py"}
  ]
}
```

**Issue:** If a student submitted Java code, the test would fail because it would try to run `python3 calculator.py` on Java files.

## The Solution

### Multi-Language Command Format

Define commands for all supported languages in a single test:

```json
{
  "name": "expect_output",
  "parameters": [
    {"name": "inputs", "value": ["5", "3"]},
    {"name": "expected_output", "value": "8"},
    {
      "name": "program_command",
      "value": {
        "python": "python3 calculator.py",
        "java": "java Calculator",
        "node": "node calculator.js",
        "cpp": "./calculator"
      }
    }
  ]
}
```

**How it works:** The pipeline automatically selects the correct command based on the submission's language.

## Command Resolution Formats

### 1. Multi-Language Dict (Recommended)

```json
{
  "name": "program_command",
  "value": {
    "python": "python3 calculator.py",
    "java": "java Calculator",
    "node": "node calculator.js",
    "cpp": "./calculator"
  }
}
```

**Advantages:**
- Supports multiple languages in one configuration
- Explicit and clear
- Flexible (can define only the languages you want to support)

### 2. CMD Placeholder (Auto-Resolution)

```json
{
  "name": "program_command",
  "value": "CMD"
}
```

**How it works:** Automatically resolves to a default command based on language:
- Python: `python3 main.py`
- Java: `java Main`
- Node: `node index.js`
- C++: `./a.out`

**Use case:** When you don't need custom filenames or compilation options.

### 3. Legacy Single Command (Backward Compatible)

```json
{
  "name": "program_command",
  "value": "python3 calculator.py"
}
```

**Behavior:** Used as-is, regardless of submission language. Only works for the specified language.

**Use case:** Backward compatibility with existing configurations.

## Complete Example

### Creating a Multi-Language Assignment

**Step 1: Create Configuration**

```bash
curl -X POST "http://localhost:8000/api/v1/configs" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "template_name": "input_output",
    "language": "python",
    "criteria_config": {
      "test_library": "input_output",
      "base": {
        "weight": 100,
        "tests": [
          {
            "name": "expect_output",
            "parameters": [
              {"name": "inputs", "value": ["5", "3"]},
              {"name": "expected_output", "value": "8"},
              {
                "name": "program_command",
                "value": {
                  "python": "python3 calculator.py",
                  "java": "java Calculator",
                  "node": "node calculator.js",
                  "cpp": "./calculator"
                }
              }
            ]
          },
          {
            "name": "expect_output",
            "parameters": [
              {"name": "inputs", "value": ["10", "7"]},
              {"name": "expected_output", "value": "17"},
              {
                "name": "program_command",
                "value": {
                  "python": "python3 calculator.py",
                  "java": "java Calculator",
                  "node": "node calculator.js",
                  "cpp": "./calculator"
                }
              }
            ]
          }
        ]
      }
    },
    "setup_config": {
      "required_files": [],
      "setup_commands": []
    }
  }'
```

**Step 2: Submit Python Solution**

```bash
curl -X POST "http://localhost:8000/api/v1/submissions" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "external_user_id": "student-001",
    "username": "alice",
    "files": [
      {
        "filename": "calculator.py",
        "content": "a = int(input())\nb = int(input())\nprint(a + b)"
      }
    ],
    "language": "python"
  }'
```

**Pipeline will execute:** `python3 calculator.py`

**Step 3: Submit Java Solution**

```bash
curl -X POST "http://localhost:8000/api/v1/submissions" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "external_user_id": "student-002",
    "username": "bob",
    "files": [
      {
        "filename": "Calculator.java",
        "content": "import java.util.Scanner;\npublic class Calculator {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        System.out.println(sc.nextInt() + sc.nextInt());\n    }\n}"
      }
    ],
    "language": "java"
  }'
```

**Pipeline will execute:** `java Calculator`

**Step 4: Submit Node.js Solution**

```bash
curl -X POST "http://localhost:8000/api/v1/submissions" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "external_user_id": "student-003",
    "username": "charlie",
    "files": [
      {
        "filename": "calculator.js",
        "content": "const readline = require('\''readline'\'');\nconst rl = readline.createInterface({ input: process.stdin });\nconst lines = [];\nrl.on('\''line'\'', l => {\n  lines.push(l);\n  if (lines.length === 2) {\n    console.log(parseInt(lines[0]) + parseInt(lines[1]));\n    rl.close();\n  }\n});"
      }
    ],
    "language": "node"
  }'
```

**Pipeline will execute:** `node calculator.js`

**Step 5: Submit C++ Solution**

```bash
curl -X POST "http://localhost:8000/api/v1/submissions" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "external_user_id": "student-004",
    "username": "diana",
    "files": [
      {
        "filename": "calculator.cpp",
        "content": "#include <iostream>\nint main() {\n  int a, b;\n  std::cin >> a >> b;\n  std::cout << a + b << std::endl;\n  return 0;\n}"
      }
    ],
    "language": "cpp"
  }'
```

**Pipeline will execute:** `./calculator`

## How It Works Internally

### Architecture

```
┌──────────────────────────────────────┐
│ Submission with Language             │
│ (Python/Java/Node/C++)               │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│ GraderService                        │
│ - Sets submission language           │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│ Test Execution                       │
│ - Receives multi-lang command config │
│ - Receives submission language       │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│ CommandResolver                      │
│ - Resolves actual command            │
│ - Based on language                  │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│ Sandbox Execution                    │
│ - Runs the resolved command          │
└──────────────────────────────────────┘
```

### Code Flow

1. **Grade Step** (`grade_step.py`):
   - Sets submission language in `GraderService`

2. **Grader Service** (`grader_service.py`):
   - Passes language to each test as `__submission_language__` parameter

3. **Test Function** (`input_output.py` - `ExpectOutputTest`):
   - Receives `program_command` and `__submission_language__`
   - Creates `CommandResolver` instance
   - Calls `resolver.resolve_command(program_command, language)`

4. **Command Resolver** (`command_resolver.py`):
   - Checks command format (dict/string/CMD)
   - Returns appropriate command for the language

5. **Sandbox Execution**:
   - Runs the resolved command

## CommandResolver API

### `resolve_command(program_command, language, fallback_filename=None)`

Resolves a command based on the submission language.

**Parameters:**
- `program_command`: Command configuration (dict, string, or "CMD")
- `language`: `Language` enum value (PYTHON, JAVA, NODE, CPP)
- `fallback_filename`: Optional filename for auto-resolution

**Returns:** Resolved command string or None

**Examples:**

```python
from autograder.services.command_resolver import CommandResolver
from sandbox_manager.models.sandbox_models import Language

resolver = CommandResolver()

# Multi-language dict
commands = {
    "python": "python3 calc.py",
    "java": "java Calc",
    "node": "node calc.js",
    "cpp": "./calc"
}
resolver.resolve_command(commands, Language.JAVA)
# Returns: "java Calc"

# CMD placeholder
resolver.resolve_command("CMD", Language.PYTHON)
# Returns: "python3 main.py"

# Legacy string
resolver.resolve_command("python3 calc.py", Language.PYTHON)
# Returns: "python3 calc.py"
```

## Migrating Existing Configurations

### From Single-Language to Multi-Language

**Before:**
```json
{
  "name": "program_command",
  "value": "python3 calculator.py"
}
```

**After:**
```json
{
  "name": "program_command",
  "value": {
    "python": "python3 calculator.py",
    "java": "java Calculator",
    "node": "node calculator.js",
    "cpp": "./calculator"
  }
}
```

### Migration Script

We provide a script to automatically update criteria files:

```bash
python update_criteria_examples.py
```

This script:
- Finds all `program_command` with single Python commands
- Converts them to multi-language dict format
- Generates appropriate commands for all languages

## Best Practices

### 1. Always Use Multi-Language Format

Unless you have a specific reason to restrict languages, use the multi-language dict format:

```json
{
  "python": "python3 myfile.py",
  "java": "java MyClass",
  "node": "node myfile.js",
  "cpp": "./myfile"
}
```

### 2. Use CMD for Simple Cases

If you don't care about specific filenames:

```json
{
  "name": "program_command",
  "value": "CMD"
}
```

### 3. Be Consistent with Naming

If your assignment uses `calculator.py`, also use:
- `Calculator.java` (capitalized for Java conventions)
- `calculator.js`
- `calculator.cpp`

### 4. Handle Compilation in setup_config

For compiled languages, ensure setup_config handles compilation:

```json
{
  "setup_config": {
    "required_files": [],
    "setup_commands": [
      // Java compilation happens automatically
      // C++ needs explicit compilation
      {
        "name": "Compile C++ if needed",
        "command": "g++ calculator.cpp -o calculator || true"
      }
    ]
  }
}
```

**Note:** The pipeline creates language-specific sandboxes, so compilation commands should be conditional or use `|| true` to avoid failing for other languages.

## Limitations

### 1. No Per-Language Test Variations

All languages run the same tests with the same inputs/outputs. You cannot have:
```json
// NOT SUPPORTED
{
  "inputs": {
    "python": ["5", "3"],
    "java": ["10", "20"]
  }
}
```

### 2. Setup Commands Are Not Language-Aware

`setup_config` commands run regardless of submission language. Make them conditional:

```bash
# Good: conditional compilation
"[ -f Calculator.java ] && javac Calculator.java || true"

# Bad: always tries to compile Java
"javac Calculator.java"
```

### 3. File Requirements Don't Change

`required_files` is static. You can't require `calculator.py` for Python and `Calculator.java` for Java in the same config.

**Workaround:** Leave `required_files` empty for multi-language assignments.

## Testing

### Unit Tests

```bash
pytest tests/unit/test_command_resolver.py -v
```

Tests the `CommandResolver` service in isolation.

### Integration Tests

```bash
pytest tests/integration/test_multi_language_command_resolution.py -v
```

Tests the full pipeline with different languages and command formats.

## Troubleshooting

### Issue: Test fails with "command not found"

**Cause:** Missing language in multi-language dict.

**Solution:** Add the language to your command config:
```json
{
  "python": "...",
  "java": "...",
  "node": "...",  // Add this
  "cpp": "..."
}
```

### Issue: All submissions use same command regardless of language

**Cause:** Using legacy single-string format.

**Solution:** Convert to multi-language dict or use "CMD" placeholder.

### Issue: CMD placeholder uses wrong filename

**Cause:** Auto-resolution uses default filenames.

**Solution:** Use explicit multi-language dict instead of CMD.

### Issue: Java submissions fail with "class not found"

**Cause:** Incorrect class name in command.

**Solution:** Ensure Java command matches the actual class name (case-sensitive):
```json
{
  "java": "java Calculator"  // Must match: public class Calculator
}
```

## API Changes

### Breaking Changes

None. This feature is backward compatible with existing single-command configurations.

### New Features

1. **Multi-language command dict format**
2. **CMD placeholder for auto-resolution**
3. **CommandResolver service**

### Modified Components

- `ExpectOutputTest.execute()`: Now accepts `__submission_language__` parameter
- `GraderService`: Tracks and passes submission language to tests
- `GradeStep`: Sets submission language in grader service

## Examples

All example criteria files in `examples/assets/input_output/criteria_examples/` have been updated to use the multi-language format.

See:
- `1_base_only_simple.json`
- `2_base_and_bonus.json`
- `3_base_bonus_penalty.json`
- `4_with_subjects.json`
- `5_nested_subjects.json`

## Future Enhancements

Potential improvements:
- Language-specific test parameters
- Per-language input/output variations
- Conditional setup commands based on language
- Auto-detection of required files per language

