# Criteria Tree

## What it is

The **Criteria Tree** is the rubric model used by the grader. It defines *what is evaluated* and *how much each part contributes*.

Top-level categories:

- `base` (required)
- `bonus` (optional)
- `penalty` (optional)

Each category can contain nested subjects and tests.

## Why it matters

The criteria tree is where educational policy becomes executable logic:

- Transparency: students see what was expected.
- Fairness: every submission is graded with the same rubric structure.
- Maintainability: rubric changes are config updates, not code rewrites.

## How scoring works

1. Tests produce scores in the 0-100 range.
2. Subjects aggregate child tests/subjects by weight.
3. Categories aggregate their children by weight.
4. Final score is computed at the root of the assessed `ResultOutcomeTree`
   (`autograder/models/contracts/scoring.py` holds the one arithmetic definition):

```text
final = base + bonus_contribution - penalty_contribution
```

The root score is capped to `[0, 100]`.

## Key concepts you should model explicitly

### 1. Weight hierarchy

Weights are local to sibling groups. A test's final impact depends on all ancestor weights.

### 2. `subjects_weight`

When a node has both direct tests and child subjects, `subjects_weight` splits influence between the two groups.

### 3. Educational intent

Use subject names that represent real learning objectives ("Input validation", "API contracts", "Accessibility"), not implementation jargon.

## Concrete configuration example

```json
{
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "Correctness",
        "weight": 70,
        "tests": [
          {"id": "answer", "type": "expect_output", "name": "Prints the answer", "weight": 70,
           "parameters": {"program_command": "python3 main.py", "inputs": ["10"], "expected_output": "42"}},
          {"id": "no-crash", "type": "dont_fail", "name": "Does not crash", "weight": 30,
           "parameters": {"program_command": "python3 main.py", "user_input": "10"}}
        ]
      },
      {
        "subject_name": "Code Quality",
        "weight": 30,
        "tests": [
          {"id": "no-os", "type": "forbidden_import", "name": "Avoids os", "weight": 100,
           "parameters": {"forbidden_imports": ["os"]}}
        ]
      }
    ]
  }
}
```

## Common mistakes

- Setting arbitrary weights without tying them to learning objectives
- Overusing deeply nested subjects that are hard for students to interpret
- Mixing "must-have" and "nice-to-have" requirements in the same weighted group

## Continue reading

- [Educational Criteria Design](../guides/criteria-tree-educational-standards.md)
- [Grading Engine Deep Dive](../features/grading_engine.md)
- [Configuration Examples](../guides/criteria_configuration_examples.md)
