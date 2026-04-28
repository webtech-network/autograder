# Command Resolver and Multi-Language Support

## Overview

The Autograder's **Command Resolver** is an internal service that provides **dynamic command resolution** based on the submission's programming language. This architecture allows a single grading configuration (assignment) to seamlessly accept submissions in multiple languages (e.g., Python, Java, Node.js, C, C++) without requiring redundant setup or duplicate assignments for each language.

This document outlines what the Command Resolver is, how to structure multi-language configurations, and how the entire pipeline processes a multi-language submission.

---

## Supported Languages

The Command Resolver currently supports the following languages:

| Key | Language |
|-----|----------|
| `python` | Python 3 |
| `java` | Java |
| `node` | Node.js |
| `cpp` | C++ |
| `c` | C *(newly supported)* |

---

## What is the Command Resolver?

The `CommandResolver` (`autograder/services/command_resolver.py`) is responsible for taking an abstract or multi-language execution instruction from a grading criteria configuration and translating it into an exact, executable shell string based on the language of the current submission.

The Command Resolver processes two formats:

1. **Multi-Language Dict Format:** A mapping of specific environments to their explicit commands.
2. **`CMD` Placeholder:** A wildcard string that automatically falls back to default commands.

---

## Multi-Language Configuration Examples

When configuring tests in the Autograder, instead of providing a plain string command, you provide either a dictionary or a `"CMD"` placeholder.

### 1. Multi-Language Dict (Recommended)

This format provides explicitly defined commands mapped to their specific languages.

```json
{
  "name": "program_command",
  "value": {
    "python": "python3 calculator.py",
    "java": "java Calculator",
    "node": "node calculator.js",
    "cpp": "./calculator",
    "c": "./calculator"
  }
}
```

**Advantages:**
- Fully explicit and configurable.
- Allows appending custom flags (e.g., specific `-cp` classpath for Java, `--no-warnings` for Node).
- Only supports defined languages, making constraints explicit.

### 2. CMD Placeholder (Auto-Resolution)

For standard executions where the entry point is typical or explicitly clear from the files submitted, use the magic `"CMD"` string.

```json
{
  "name": "program_command",
  "value": "CMD"
}
```

**How it works:** Automatically identifies the main execution file based on conventions and resolves to a default command:
- **Python:** `python3 main.py` or uses the first `.py` fallback it spots.
- **Java:** `java Main` or the corresponding class name inferred from proper `.java` filenames.
- **Node:** `node index.js`
- **C/C++:** `./a.out` (or uses the binary named after the main source file).

**Use case:** Simple projects with a single source point where you don't need custom compilation parameters.

---

## How Configurations are Processed

When a student submits code, it enters an execution pipeline managed by the Autograder's `GraderService`, supported by the `CommandResolver`:

1. **Language Association:** The API or Web layer identifies the submitted language and sets it in the overarching `PipelineExecution`.
2. **Configuration Load:** The pipeline loads the standard criteria (e.g., weight, number of tests, configurations like `setup_config` to compile `.java` or `.cpp`).
3. **Execution Routing in `SubmissionGrader`:** When evaluating an individual test node, `SubmissionGrader` discovers that `program_command` isn't an exact literal. It hands over the raw value (Dict or `"CMD"`) alongside the current `SubmissionLanguage` to the `CommandResolver`.
4. **Processing by `CommandResolver`:**
   - If the value is a dictionary, it looks up the specific key (e.g., `java`) and returns its explicit command string (`java Calculator`).
   - If the value is `"CMD"`, it assesses the submitted files or fallback defaults to return the right execution instruction.
5. **Sandbox Hand-off:** After finding the appropriate string, the `SubmissionGrader` forwards it into the configured Docker container (the sandbox). Since the sandbox matches the submission language context, it spins up and correctly evaluates `java Calculator`, oblivious to the fact that the assignment originally supported Python or Node submissions.

---

## How It Works Internally

### Architecture

```
┌──────────────────────────────────────┐
│ Submission with Language             │
│ (Python/Java/Node/C/C++)             │
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
   - Handles the resolution mapping internally using `CommandResolver`
   - Passes the resolved command to `test_function.execute()`

3. **Command Resolver** (`command_resolver.py`):
   - Checks `program_command` format (`dict` or `"CMD"`)
   - Returns appropriate command string strictly matching the language mapped context.

4. **Sandbox Execution**:
   - Runs the resolved command

---

## CommandResolver API

### `resolve_command(program_command, language, fallback_filename=None)`

- **`program_command`**: The execution configuration from the test. Can be:
  - `dict`: Explicit command overrides per language.
  - `"CMD"`: Auto-resolve to default conventions for the language.
- **`language`**: Processed `Language` Enum type indicating current sandbox.
- **`fallback_filename`**: Optionally informs the auto-resolver of default expected standard entry points.

Returns a formatted executable string or `None` if invalid mappings are caught.

---

## Complete Multi-Language Assignment Example

A complete multi-language assignment contains both standard `setup_config` directives (for compilation when required) and multi-language `program_command` definitions in its tests.

**Step 1: Create Configuration**

```sh
curl -X POST "http://localhost:8000/api/v1/configs" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "template_name": "input_output",
    "languages": ["python", "java", "node", "cpp", "c"],
    "criteria_config": {
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
                  "cpp": "./calculator",
                  "c": "./calculator"
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
      "node": {
        "required_files": ["calculator.js"],
        "setup_commands": []
      },
      "cpp": {
        "required_files": ["calculator.cpp"],
        "setup_commands": ["g++ calculator.cpp -o calculator"]
      },
      "c": {
        "required_files": ["calculator.c"],
        "setup_commands": ["gcc calculator.c -o calculator"]
      }
    }
  }'
```

**Step 2: Submitting a Python Solution**

```sh
curl -X POST "http://localhost:8000/api/v1/submissions" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "external_user_id": "student-001",
    "username": "alice",
    "language": "python",
    "files": [
      {
        "filename": "calculator.py",
        "content": "a = int(input())\nb = int(input())\nprint(a + b)"
      }
    ]
  }'
```

**Step 3: Submitting a Java Solution**

```sh
curl -X POST "http://localhost:8000/api/v1/submissions" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "external_user_id": "student-002",
    "username": "bob",
    "language": "java",
    "files": [
      {
        "filename": "Calculator.java",
        "content": "import java.util.Scanner;\npublic class Calculator {\n    public static void main(String[] args) {\n        Scanner s = new Scanner(System.in);\n        System.out.println(s.nextInt() + s.nextInt());\n    }\n}"
      }
    ]
  }'
```

---

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
    "cpp": "./calculator",
    "c": "./calculator"
  }
}
```

### Migration Script

To automatically update existing criteria files, run:

```bash
python update_criteria_examples.py
```

This script:
- Finds all `program_command` entries with single Python commands
- Converts them to multi-language dict format
- Generates appropriate commands for all supported languages

---

## Limitations

### 1. No Per-Language Test Variations

All languages run the same tests with the same inputs and expected outputs. The following is **not supported**:

```json
// NOT SUPPORTED
{
  "inputs": {
    "python": ["5", "3"],
    "java": ["10", "20"]
  }
}
```

### 2. File Requirements Are Language-Specific

`required_files` is defined per language inside `setup_config`. Each language can require different files and compilation steps.

### 3. CMD Uses Default Filenames

Auto-resolution via `"CMD"` relies on naming conventions (`main.py`, `Main.java`, `index.js`, `a.out`). If the submitted file uses a non-standard name, use the explicit multi-language dict format instead.

---

## API Changes

### Breaking Changes

None. This feature is fully backward compatible with existing configurations.

### New Features

1. Multi-language command dict format
2. `CMD` placeholder for auto-resolution
3. `CommandResolver` service
4. C language support (`"c"` key)

### Modified Components

- `GraderService`: Tracks and passes submission language to tests
- `GradeStep`: Sets submission language in grader service

---

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

---

## Troubleshooting

### Issue: Test fails with "command not found"

**Cause:** Missing language in multi-language dict.

**Solution:** Add the language to your command config:
```json
{
  "python": "...",
  "java": "...",
  "node": "...",
  "cpp": "...",
  "c": "..."
}
```

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

---

## Best Practices

### 1. Always Use Multi-Language Format

Unless you have a specific reason to restrict languages, use the multi-language dict format:

```json
{
  "python": "python3 myfile.py",
  "java": "java MyClass",
  "node": "node myfile.js",
  "cpp": "./myfile",
  "c": "./myfile"
}
```

### 2. Use CMD for Simple Cases

If you don't care about specific filenames and the project has a single standard entry point.

### 3. Handle Compilation in setup_config

For compiled languages, define setup commands per language. The pipeline resolves the correct language block at runtime based on the submission's language:

```json
{
  "setup_config": {
    "java": {
      "required_files": ["Calculator.java"],
      "setup_commands": ["javac Calculator.java"]
    },
    "cpp": {
      "required_files": ["calculator.cpp"],
      "setup_commands": ["g++ calculator.cpp -o calculator"]
    },
    "c": {
      "required_files": ["calculator.c"],
      "setup_commands": ["gcc calculator.c -o calculator"]
    },
    "python": {
      "required_files": ["calculator.py"],
      "setup_commands": []
    },
    "node": {
      "required_files": ["calculator.js"],
      "setup_commands": []
    }
  }
}
```

---

## Future Enhancements

Potential improvements:

- **Language-specific test parameters** — allow different test configurations per language
- **Per-language input/output variations** — support distinct inputs and expected outputs for each language
- **Conditional setup commands based on language** — run setup steps conditionally depending on the submission language
- **Auto-detection of required files per language** — infer `required_files` automatically from submitted files without manual configuration

---

## Future Enhancements

Potential improvements:
- Language-specific test parameters
- Per-language input/output variations
- Conditional setup commands based on language
- Auto-detection of required files per language
