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

### `complexity`

Measures the **algorithmic complexity** of a student's program by running it with increasing input sizes, timing each execution inside the sandbox, and classifying the growth rate via log-log regression. Useful for verifying that a sorting algorithm is O(n log n) rather than O(n²), or that a search runs in O(log n).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `program_command` | string or dict | ✓ | — | Command to execute (same format as `expect_output`, supports `"CMD"`) |
| `expected_complexity` | string | ✓ | `"O(n)"` | Expected class: `O(1)`, `O(log n)`, `O(sqrt(n))`, `O(n)`, `O(n log n)`, `O(n^2)`, `O(n^3)`, `O(exponential)` |
| `input_generator` | string | ✗ | `"random_array"` | Built-in generator name (see table below) |
| `scoring` | string | ✗ | `"graduated"` | Scoring mode: `strict`, `graduated`, or `custom` |
| `score_table` | dict | ✗ | — | Custom score map (only used when `scoring` = `"custom"`) |
| `test_sizes` | list[int] | ✗ | `[500, 2500, 12500, 62500]` | Input sizes to benchmark |
| `inconclusive_policy` | string | ✗ | `"partial"` | What to do when R² is too low: `partial` (50 points) or `fail` (0 points) |
| `repeats` | int | ✗ | `3` | Repetitions per size (minimum time is kept) |
| `timeout` | int | ✗ | `30` | Per-execution timeout in seconds |
| `input_args` | dict | ✗ | — | Extra arguments passed to the input generator (e.g., `min_value`, `max_value`) |

#### Input Generators

| Generator | Format sent to stdin | Use case |
|-----------|---------------------|----------|
| `random_array` | `N\nv1 v2 ... vN` | Sorting, searching algorithms |
| `sorted_array` | `N\nv1 v2 ... vN` (ascending) | Best-case analysis |
| `reverse_sorted_array` | `N\nv1 v2 ... vN` (descending) | Worst-case analysis |
| `random_string` | `abcxyz...` (N chars) | String algorithms |
| `random_pairs` | `N\na1 b1\na2 b2\n...` | Graph/pair-based algorithms |
| `single_number` | `N` | Number theory algorithms |
| `random_matrix` | `R C\nrow1\nrow2\n...` (√N × √N) | Matrix algorithms |

#### Scoring Modes

- **`strict`** — 100 if detected ≤ expected, 0 otherwise.
- **`graduated`** — Partial credit based on how far off: same=100, +1 class=80, +2=60, +3=30, +4+=0.
- **`custom`** — Professor defines a `score_table` mapping each complexity class to a score.

#### How It Works

1. Generates inputs for each size using the chosen generator
2. Injects a benchmark wrapper script into the sandbox
3. Runs the student's program for each input size (with warmup + repeats)
4. Collects minimum execution times per size
5. Fits a power-law model via log-log regression to determine growth rate (α exponent)
6. For α in the O(n)/O(n log n) gray zone, performs dual model fitting to discriminate
7. Computes a score based on detected vs expected complexity

**Example — Strict scoring:**
```json
{
  "name": "complexity",
  "parameters": {
    "program_command": "python3 sort.py",
    "expected_complexity": "O(n log n)",
    "input_generator": "random_array",
    "scoring": "strict"
  },
  "weight": 100
}
```

**Example — Graduated scoring with custom sizes:**
```json
{
  "name": "complexity",
  "parameters": {
    "program_command": "CMD",
    "expected_complexity": "O(n)",
    "input_generator": "random_array",
    "scoring": "graduated",
    "test_sizes": [1000, 5000, 25000, 125000]
  },
  "weight": 50
}
```

**Example — Custom scoring table:**
```json
{
  "name": "complexity",
  "parameters": {
    "program_command": "python3 search.py",
    "expected_complexity": "O(log n)",
    "input_generator": "sorted_array",
    "scoring": "custom",
    "score_table": {
      "O(1)": 100,
      "O(log n)": 100,
      "O(sqrt(n))": 70,
      "O(n)": 40,
      "O(n log n)": 10,
      "O(n^2)": 0
    }
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

