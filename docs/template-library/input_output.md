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

### `forbidden_keyword`

Tests that a submission does **not** use specific forbidden keywords or language constructs. This test performs structural analysis using `ast-grep`, which is more reliable than regex because it correctly ignores matches inside comments or string literals.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `forbidden_keywords` | list[string] | ✗ | List of high-level keywords to forbid (e.g., `"for_loop"`, `"while_loop"`) |
| `custom_ast_grep_rules` | list[dict] | ✗ | Custom `ast-grep` rules for advanced structural matching |

**Supported Keywords for Predefined Rules:**

| Language | Supported Keywords |
|----------|--------------------|
| **Python** | `for_loop`, `while_loop`, `eval_call`, `exec_call` |
| **Java** | `for_loop`, `while_loop` |
| **Node.js** | `for_loop`, `while_loop`, `eval_call` |
| **C++ / C** | `for_loop`, `while_loop`, `do_while_loop` |

**Scoring:** 100 if no forbidden constructs are found, 0 otherwise.

**Example:**
```json
{
  "name": "forbidden_keyword",
  "parameters": {
    "forbidden_keywords": ["for_loop", "eval_call"]
  },
  "weight": 100
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

