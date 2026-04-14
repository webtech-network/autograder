# Input/Output Template (`input_output`)

The Input/Output template tests command-line programs by providing stdin inputs and validating stdout output. It requires a sandbox for code execution.

> **Template name for configs:** `input_output`  
> **Requires sandbox:** Yes  
> **Supported languages:** Python, Java, Node.js, C++

---

## Test Functions

### `expect_output`

Executes a program with a series of stdin inputs and compares the program's stdout against an expected output string.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `inputs` | list[string] | ✓ | List of strings sent to stdin, each on a new line |
| `expected_output` | string | ✓ | Exact string the program should print to stdout |
| `program_command` | string | ✗ | Command to execute. Can be a plain string (e.g., `"python main.py"`), a dict for multi-language support, or `"CMD"` for auto-resolution based on submission language. |

**Scoring:** 100 if output matches exactly (after trimming whitespace), 0 otherwise.

**Error handling:** Automatically detects and reports:
- Timeouts (infinite loops)
- Compilation errors (Java/C++)
- Runtime errors (crashes)
- System errors (infrastructure failures)

**Example:**
```json
{
  "name": "expect_output",
  "parameters": {
    "inputs": ["Alice"],
    "expected_output": "Hello, Alice!",
    "program_command": "python3 main.py"
  },
  "weight": 100
}
```

**Multi-language example** (auto-resolves command based on submission language):
```json
{
  "name": "expect_output",
  "parameters": {
    "inputs": ["5", "3"],
    "expected_output": "8",
    "program_command": "CMD"
  },
  "weight": 100
}
```

---

### `expect_file_artifact`

Executes a program and then extracts a generated file from the sandbox container, comparing its content against an expected value. Useful for assignments where students must produce output files (e.g., reports, sorted data, metrics).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `artifact_path` | string | ✓ | Relative path under `/app` of the file the program must generate (e.g., `output.txt`) |
| `expected_content` | string | ✓ | Expected file content or pattern to match against |
| `program_command` | string | ✗ | Command to execute (same format as `expect_output`) |
| `match_mode` | string | ✗ | `exact` (default), `contains`, or `regex` |
| `inputs` | list[string] | ✗ | List of strings sent to stdin before extraction |
| `normalization` | boolean | ✗ | Normalize line endings and trim trailing whitespace (default: `true`) |

**Scoring:** 100 if file content matches, 0 otherwise.

**Error handling:** Inherits all execution error detection from `expect_output` (timeouts, compilation errors, runtime errors), plus:
- Missing artifact file
- Artifact extraction failure
- Invalid regex pattern
- Invalid artifact path (absolute or traversal paths are rejected)

**Artifact path conventions:**
- Paths are relative to `/app` (the sandbox working directory)
- Absolute paths (`/etc/passwd`) and traversal paths (`../secret`) are rejected
- The file must be a regular file (not a directory or symlink)
- Maximum extracted file size: 1 MB

**Exact match example:**
```json
{
  "name": "expect_file_artifact",
  "parameters": {
    "inputs": ["1000"],
    "program_command": {
      "python": "python3 main.py",
      "java": "java Main",
      "node": "node main.js",
      "cpp": "./main"
    },
    "artifact_path": "matricula_selecao.txt",
    "match_mode": "exact",
    "expected_content": "comparacoes: 10\nmovimentacoes: 4\ntempo: 0.001s"
  },
  "weight": 100
}
```

**Regex match example** (for variable values like execution time):
```json
{
  "name": "expect_file_artifact",
  "parameters": {
    "inputs": ["1000"],
    "program_command": "CMD",
    "artifact_path": "matricula_insercao.txt",
    "match_mode": "regex",
    "expected_content": "comparacoes:\\s*\\d+\\s+movimentacoes:\\s*\\d+\\s+tempo:\\s*[0-9.]+s"
  },
  "weight": 100
}
```

**Contains match example:**
```json
{
  "name": "expect_file_artifact",
  "parameters": {
    "program_command": "python3 main.py",
    "artifact_path": "report.txt",
    "match_mode": "contains",
    "expected_content": "PASSED"
  },
  "weight": 50
}
```

---

### `dont_fail`

Executes a program with a specific input and verifies it completes **without crashing**. The program's stdout is ignored — this test only validates that execution succeeds. Useful for testing error handling (e.g., sending invalid input).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_input` | string | ✗ | A string to send via stdin |
| `program_command` | string | ✗ | Command to execute (same format as `expect_output`) |

**Scoring:** 100 if program completes without error, 0 if it crashes/times out.

**Example:**
```json
{
  "name": "dont_fail",
  "parameters": {
    "user_input": "not_a_number",
    "program_command": "python3 calculator.py"
  },
  "weight": 50
}
```

---

## Usage Example

```json
{
  "external_assignment_id": "calculator-assignment",
  "template_name": "input_output",
  "languages": ["python", "java"],
  "setup_config": {
    "required_files": ["calculator.py"],
    "setup_commands": []
  },
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "Basic Operations",
          "weight": 60,
          "tests": [
            {
              "name": "expect_output",
              "parameters": { "inputs": ["add", "5", "3"], "expected_output": "8", "program_command": "CMD" },
              "weight": 50
            },
            {
              "name": "expect_output",
              "parameters": { "inputs": ["subtract", "10", "4"], "expected_output": "6", "program_command": "CMD" },
              "weight": 50
            }
          ]
        },
        {
          "subject_name": "Error Handling",
          "weight": 40,
          "tests": [
            {
              "name": "dont_fail",
              "parameters": { "user_input": "invalid", "program_command": "CMD" },
              "weight": 100
            }
          ]
        }
      ]
    }
  }
}
```

## Multi-Language Command Resolution

When `program_command` is set to `"CMD"`, the autograder automatically resolves the execution command based on the submission's language:

| Language | Resolved Command |
|----------|-----------------|
| Python | `python3 <main_file>` |
| Java | `java <MainClass>` |
| Node.js | `node <main_file>` |
| C++ | `./<compiled_binary>` |

This allows the same grading configuration to work across multiple languages without specifying language-specific commands.

