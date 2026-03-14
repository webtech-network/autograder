# Step 2: Build Tree

## Purpose

The Build Tree step transforms the raw JSON grading criteria into a structured `CriteriaTree` — the hierarchical rubric that drives the entire grading process. It also validates the configuration and links each test entry to its actual `TestFunction` from the loaded template.

## How It Works

1. **Parse configuration** — The raw JSON dictionary is validated and parsed into a `CriteriaConfig` Pydantic model, which enforces structural rules (e.g., a category must have either tests or subjects, subjects with both must declare `subjects_weight`).
2. **Build tree nodes** — The `CriteriaTreeService` recursively walks the config and creates `CategoryNode`, `SubjectNode`, and `TestNode` objects.
3. **Match test functions** — For each test entry in the config, the service looks up the corresponding `TestFunction` from the template loaded in the previous step. If a test name doesn't match any function in the template, the step fails with a `ValueError`.
4. **Balance weights** — Sibling subject weights are normalized to sum to 100 if they don't already.

The resulting `CriteriaTree` is stored in the step result and used by the Grade step to execute tests.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Load Template** | The `Template` object to look up test functions by name |

## Input

| Source | Data |
|--------|------|
| Constructor | `criteria_json: dict` — raw criteria configuration dictionary |
| Pipeline | `StepName.LOAD_TEMPLATE` → `Template` |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `CriteriaTree` | The fully built criteria tree with embedded test functions |
| `status` | `StepStatus.SUCCESS` | On successful build |

## CriteriaTree Structure

```
CriteriaTree
├── base: CategoryNode (required)
│   ├── subjects: [SubjectNode, ...]
│   │   ├── tests: [TestNode, ...]
│   │   └── subjects: [SubjectNode, ...]  (nested)
│   └── tests: [TestNode, ...]
├── bonus: CategoryNode (optional)
└── penalty: CategoryNode (optional)
```

Each `TestNode` holds:
- `name` — Test identifier
- `test_function` — Reference to the actual `TestFunction` instance from the template
- `parameters` — Keyword arguments to pass to the test function at execution time
- `file_target` — Which submission files this test operates on (optional)

## Weight Balancing

If sibling subjects don't sum to 100, the service scales them proportionally:

```
Subject A: weight=30, Subject B: weight=70 → kept as-is (sum=100)
Subject A: weight=3, Subject B: weight=7   → scaled to 30 and 70
```

When a category or subject contains both `subjects` and `tests`, the `subjects_weight` field determines how the total weight is split between the two groups. For example, `subjects_weight=70` means 70% of the score comes from subjects and 30% from direct tests.

## Failure Scenarios

- Invalid criteria JSON structure (missing required fields, wrong types) → Pydantic validation error.
- Test name not found in the template → `ValueError: Couldn't find test {name}`.
- Category has neither tests nor subjects → validation error.

## Source

`autograder/steps/build_tree_step.py` → `BuildTreeStep`

`autograder/services/criteria_tree_service.py` → `CriteriaTreeService`

`autograder/models/config/` → `CriteriaConfig`, `CategoryConfig`, `SubjectConfig`
