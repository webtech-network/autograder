# Data Science Template (`data_science`)

The Data Science template tests Python assignments that involve reading datasets, performing transformations, training models, and producing predictions or analytical outputs. It leverages the sandbox environment with pre-installed scientific packages (e.g., pandas, numpy, scikit-learn).

> **Template name for configs:** `data_science`  
> **Requires sandbox:** Yes  
> **Supported languages:** Python (Data Science variant: `PYTHON_DS`)

---

## Prerequisites

Before using this template, you must build the data science Docker image on the host machine running the autograder:

```bash
docker build -t sandbox-pyds:latest -f sandbox_manager/images/Dockerfile.python-ds .
```

Assignments should specify the language as `PYTHON_DS` to utilize this environment.

---

## Test Functions

### `expect_stdout_value`

Executes a program, extracts a numeric value from stdout using a regular expression (with a named group `value`), and compares it to an expected value with an optional numeric tolerance.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `program_command` | string | ✓ | Command to execute the student program |
| `extraction_pattern` | string | ✓ | Regex pattern with a `(?P<value>...)` named group |
| `expected_value` | number | ✓ | The numeric value expected |
| `tolerance` | number | ✗ | Acceptable absolute difference (default: `0`) |

**Scoring:** 100 if the extracted value is within the tolerance, 0 otherwise.

**Example:**
```json
{
  "name": "expect_stdout_value",
  "parameters": {
    "program_command": "python3 analysis.py",
    "extraction_pattern": "Mean absolute error:\\s*(?P<value>[\\d.]+)",
    "expected_value": 0.5,
    "tolerance": 0.1
  },
  "weight": 100
}
```

---

### `expect_metric`

Executes a program, extracts a metric from stdout via regex, and validates it against a threshold using a comparison operator (`>=`, `<=`, `>`, `<`, `==`).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `program_command` | string | ✓ | Command to execute the student program |
| `metric_pattern` | string | ✓ | Regex pattern with a `(?P<value>...)` named group |
| `condition` | string | ✓ | Comparison operator (`>=`, `<=`, `>`, `<`, `==`) |
| `threshold` | number | ✓ | The threshold value for the metric |

**Scoring:** 100 if the condition is met, 0 otherwise.

**Example:**
```json
{
  "name": "expect_metric",
  "parameters": {
    "program_command": "python3 train.py",
    "metric_pattern": "Accuracy:\\s*(?P<value>[\\d.]+)",
    "condition": ">=",
    "threshold": 0.85
  },
  "weight": 100
}
```

---

### `expect_csv_output`

Validates a generated CSV file by checking column names, shape (rows x cols), and specific cell values (with numeric tolerance). Uses proportional scoring based on how many checks pass.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `program_command` | string | ✓ | Command to execute the student program |
| `artifact_path` | string | ✓ | Relative path to the generated CSV file |
| `expected_columns` | list[string] | ✗ | Expected column names in exact order |
| `expected_shape` | list[number] | ✗ | Expected `[rows, columns]` including header row |
| `expected_values` | list[list] | ✗ | 2D array of expected values |
| `tolerance` | number | ✗ | Tolerance for numeric comparisons |

**Scoring:** Proportional based on successful checks (e.g., matching columns counts as 1 check, correct shape as 1, and the ratio of correctly matched cell values counts as 1).

**Example:**
```json
{
  "name": "expect_csv_output",
  "parameters": {
    "program_command": "python3 script.py",
    "artifact_path": "predictions.csv",
    "expected_columns": ["id", "prediction"],
    "expected_shape": [101, 2]
  },
  "weight": 100
}
```

---

### `expect_json_output`

Validates a generated JSON file by checking for the presence of required keys and expected values. Supports dot-notation for nested keys (e.g., `metrics.accuracy`).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `program_command` | string | ✓ | Command to execute the student program |
| `artifact_path` | string | ✓ | Relative path to the generated JSON file |
| `required_keys` | list[string] | ✗ | Keys that must exist in the JSON |
| `expected_values` | dict | ✗ | Dictionary of key-value pairs that must match |
| `tolerance` | number | ✗ | Tolerance for numeric comparisons |

**Scoring:** Proportional based on successful key findings and value matches.

**Example:**
```json
{
  "name": "expect_json_output",
  "parameters": {
    "program_command": "python3 eval.py",
    "artifact_path": "results.json",
    "required_keys": ["status", "metrics.loss"],
    "expected_values": {
      "status": "success",
      "metrics.accuracy": 0.95
    },
    "tolerance": 0.02
  },
  "weight": 100
}
```

---

### `expect_model_artifact`

Verifies that the student program produced a model file (or any artifact) in the sandbox and that it meets a minimum file size constraint.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `program_command` | string | ✓ | Command to execute the student program |
| `artifact_path` | string | ✓ | Relative path to the generated model file |
| `min_size_bytes` | number | ✗ | Minimum required size of the file in bytes |

**Scoring:** 100 if the file exists and its size >= `min_size_bytes`, 0 otherwise.

**Example:**
```json
{
  "name": "expect_model_artifact",
  "parameters": {
    "program_command": "python3 train_model.py",
    "artifact_path": "model.pkl",
    "min_size_bytes": 10240
  },
  "weight": 100
}
```

---

## Assignment Example

Here is a full assignment configuration that uses the data science template to inject a dataset via assets, train a model, and validate its outputs:

```json
{
  "external_assignment_id": "ds-regression-task",
  "template_name": "data_science",
  "languages": ["PYTHON_DS"],
  "setup_config": {
    "required_files": ["train.py"],
    "setup_commands": [],
    "assets": [
      {
        "source": "url",
        "url": "https://example.com/dataset.csv",
        "destination_path": "/tmp/dataset.csv",
        "extract": false
      }
    ]
  },
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "Model Evaluation",
          "weight": 50,
          "tests": [
            {
              "name": "expect_metric",
              "parameters": {
                "program_command": "python3 train.py --data /tmp/dataset.csv",
                "metric_pattern": "R2 Score:\\s*(?P<value>[\\d.]+)",
                "condition": ">=",
                "threshold": 0.80
              },
              "weight": 100
            }
          ]
        },
        {
          "subject_name": "Artifact Generation",
          "weight": 50,
          "tests": [
            {
              "name": "expect_model_artifact",
              "parameters": {
                "program_command": "python3 train.py --data /tmp/dataset.csv",
                "artifact_path": "model.pkl",
                "min_size_bytes": 5000
              },
              "weight": 50
            },
            {
              "name": "expect_csv_output",
              "parameters": {
                "program_command": "python3 train.py --data /tmp/dataset.csv",
                "artifact_path": "predictions.csv",
                "expected_columns": ["id", "pred_value"]
              },
              "weight": 50
            }
          ]
        }
      ]
    }
  }
}
```
