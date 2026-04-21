# Template Configuration Guide

This guide is your complete reference for configuring assignment grading with the autograder. Whether you're setting up a simple input/output exercise or a full web development project, you'll find everything you need here.

## Available Templates

The autograder ships with three built-in templates. Each template provides a set of test functions designed for a specific type of assignment.

| Template | Registry Key | Sandbox Required | Use Case |
|----------|-------------|-----------------|----------|
| [Input/Output](input_output.md) | `input_output` | Yes | Console programs that read input and produce output |
| [API Testing](api_testing.md) | `api` | Yes | REST APIs running inside a container |
| [Web Development](web_dev.md) | `webdev` | No | Static HTML/CSS/JS projects (no server needed) |

!!! tip "Which template should I use?"
    - **Students write programs that print results?** → `input_output`
    - **Students build a REST API?** → `api`
    - **Students create web pages with HTML, CSS, and JS?** → `webdev`

## How Grading Works

### The Criteria Tree

Every grading configuration is a **criteria tree** — a hierarchical rubric that defines what gets tested and how much each part is worth.

```
criteria_config
├── base (required) ─── the core rubric, worth 0-100 points
├── bonus (optional) ── extra credit, adds points on top of base
└── penalty (optional) ─ deductions for violations
```

Each category contains **subjects** (groups of related tests) and/or **tests** (individual checks). Subjects can nest inside other subjects for multi-level rubrics.

### Score Calculation

Scores flow bottom-up through the tree:

1. Each **test** produces a score from 0 to 100
2. Each **subject** aggregates its children using weighted averages
3. Each **category** aggregates its subjects/tests using weighted averages
4. The **final score** combines all categories:

```
final_score = base_score + bonus_contribution - penalty_deduction
```

Where:

- `bonus_contribution = (bonus_score / 100) × bonus_weight` — bonus adds up to `bonus_weight` extra points
- `penalty_deduction = ((100 - penalty_score) / 100) × penalty_weight` — penalty subtracts up to `penalty_weight` points when penalty tests **fail**
- Final score is clamped to **[0, 100]**

!!! example "Score example"
    With `base_score = 80`, `bonus` at weight 20 scoring 50%, and `penalty` at weight 10 scoring 100% (all pass):

    `final = 80 + (50/100 × 20) - ((100-100)/100 × 10) = 80 + 10 - 0 = 90`

### Weight Rules

- Weights are **relative to siblings** — they don't need to sum to 100 (they're normalized automatically)
- When a node has **both** subjects and direct tests, you must set `subjects_weight` to split influence between the two groups
- Default test weight is `100` if not specified

## Configuration Structure

A grading configuration is sent via the API as part of a `GradingConfig`:

```json
{
  "external_assignment_id": "canvas-assignment-123",
  "template_name": "input_output",
  "languages": ["python"],
  "criteria_config": {
    "base": { ... },
    "bonus": { ... },
    "penalty": { ... }
  }
}
```

### Criteria Config Format

```json
{
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "Functionality",
        "weight": 70,
        "tests": [
          {
            "name": "expect_output",
            "file": "main.py",
            "parameters": [
              { "name": "inputs", "value": ["5"] },
              { "name": "expected_output", "value": "120" }
            ],
            "weight": 100
          }
        ]
      }
    ]
  }
}
```

### Test Definition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Test function name from the template registry |
| `file` | string | No | Target file for the test (e.g., `"index.html"`, `"styles.css"`) |
| `parameters` | list | No | List of `{name, value}` pairs passed to the test function |
| `weight` | number | No | Relative weight among siblings (default: `100`) |

### Subject Definition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `subject_name` | string | Yes | Display name for this group |
| `weight` | number | Yes | Relative weight among sibling subjects |
| `tests` | list | No | Direct test definitions |
| `subjects` | list | No | Nested subject groups |
| `subjects_weight` | number | Conditional | Required when **both** `tests` and `subjects` are present. Percentage of score from subjects (rest goes to tests). |

### Category Definition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `weight` | number | Yes | Category weight (for bonus/penalty: max points to add/subtract) |
| `tests` | list | No | Direct test definitions |
| `subjects` | list | No | Subject groups |
| `subjects_weight` | number | Conditional | Required when **both** `tests` and `subjects` are present |

## Supported Languages

For templates that require a sandbox (`input_output`, `api`), you must specify which languages the assignment supports:

| Language | Key | Auto-resolved Command |
|----------|-----|----------------------|
| Python | `python` | `python3 {file}` |
| Java | `java` | `javac {file} && java {class}` |
| Node.js | `node` | `node {file}` |
| C++ | `cpp` | `g++ -o program {file} && ./program` |

## Quick Start Examples

### Minimal: One Test

```json
{
  "base": {
    "tests": [
      {
        "name": "expect_output",
        "parameters": [
          { "name": "inputs", "value": ["Alice"] },
          { "name": "expected_output", "value": "Hello, Alice!" },
          { "name": "program_command", "value": "python3 greeting.py" }
        ]
      }
    ]
  }
}
```

### With Subjects and Bonus

```json
{
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "Correctness",
        "weight": 70,
        "tests": [
          {
            "name": "expect_output",
            "parameters": [
              { "name": "inputs", "value": ["5"] },
              { "name": "expected_output", "value": "120" },
              { "name": "program_command", "value": "python3 factorial.py" }
            ]
          }
        ]
      },
      {
        "subject_name": "Robustness",
        "weight": 30,
        "tests": [
          {
            "name": "dont_fail",
            "parameters": [
              { "name": "user_input", "value": "-1" },
              { "name": "program_command", "value": "python3 factorial.py" }
            ]
          }
        ]
      }
    ]
  },
  "bonus": {
    "weight": 10,
    "tests": [
      {
        "name": "expect_output",
        "parameters": [
          { "name": "inputs", "value": ["0"] },
          { "name": "expected_output", "value": "1" },
          { "name": "program_command", "value": "python3 factorial.py" }
        ]
      }
    ]
  }
}
```

## Next Steps

- **[Input/Output Template](input_output.md)** — All tests for console programs
- **[API Testing Template](api_testing.md)** — All tests for REST APIs
- **[Web Development Template](web_dev.md)** — All tests for HTML/CSS/JS projects
- **[Complete Examples](examples.md)** — Full assignment configurations you can copy and adapt
