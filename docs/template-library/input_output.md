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
| `inputs` | list[string] | ✗ | Lines sent to stdin exactly; each is followed by `\n`. `[]` (the default) is empty stdin and `[""]` is one empty line. |
| `expected_output` | string | ✓ | Exact string the program should print to stdout |
| `program_command` | string | ✗ | Command to execute. Can be a plain string (e.g., `"python main.py"`), a dict for multi-language support, or `"CMD"` for auto-resolution based on submission language. |

**Scoring:** 100 if output matches exactly (after trimming whitespace), 0 otherwise.

**Process handling** ([process contract](../contracts/PROCESSES.md)). The command
is an argument vector with no implicit shell; use `sh -c '...'` for shell syntax.
Malformed quoting is rejected when the definition is compiled
(`INVALID_COMMAND`). Each run has a 30 s deadline.

- Any nonzero exit, including one with empty stderr, or a timeout scores 0. The
  report shows stderr, or the exit code when stderr is empty. A timed-out
  program, and any process it started, is killed before the next criterion runs.
- Compile in `preparation` setup commands; a failed setup command stops grading
  with `PREPARATION_FAILED`.
- A program that cannot be started (`PROCESS_START_FAILED`) and infrastructure
  failures (`SANDBOX_ERROR`) fail the execution without a score.

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

### `dont_fail`

Executes a program with a specific input and verifies it completes **without crashing**. The program's stdout is ignored — this test only validates that execution succeeds. Useful for testing error handling (e.g., sending invalid input).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_input` | string | ✗ | One line sent to stdin (followed by `\n`); empty (the default) sends nothing |
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

## Multi-Language Command Resolution

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

