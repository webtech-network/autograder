# Data Structures

This document describes the core data structures used throughout the Autograder system.

## Criteria Tree

The criteria tree represents the grading rubric structure. It mirrors how educators think about grading with hierarchical organization.

### Structure

```
CriteriaTree
├── Base (weight: 100)
│   ├── Subject: Functionality (weight: 60)
│   │   ├── Test: Correct Output (weight: 100)
│   │   └── Test: Edge Cases (weight: 100)
│   └── Subject: Code Quality (weight: 40)
│       ├── Test: Proper Syntax (weight: 50)
│       └── Test: Good Practices (weight: 50)
├── Bonus (weight: 10)
│   └── Test: Extra Features
└── Penalty (weight: -20)
    └── Test: Late Submission
```

### Categories

#### Base Category
- **Purpose**: Core grading criteria
- **Weight**: Typically 100 (represents 100% of base grade)
- **Contains**: Subjects and/or tests
- **Required**: Yes

#### Bonus Category
- **Purpose**: Extra credit opportunities
- **Weight**: Additional percentage (e.g., 10 = up to 10% extra)
- **Contains**: Tests only (no subject grouping)
- **Required**: No

#### Penalty Category
- **Purpose**: Deductions from total score
- **Weight**: Negative percentage (e.g., -20 = up to 20% deduction)
- **Contains**: Tests only (no subject grouping)
- **Required**: No

### Subjects

Subjects group related tests together with weighted importance.

**Properties:**
- `subject_name`: Human-readable name
- `weight`: Relative importance (0-100)
- `tests`: List of test configurations
- `subjects`: Nested subjects (for hierarchical organization)

**Example:**
```json
{
  "subject_name": "HTML Structure",
  "weight": 40,
  "tests": [
    {
      "name": "has_tag",
      "parameters": {"tag": "header"},
      "weight": 50
    }
  ]
}
```

### Tests

Individual grading checks within subjects or categories.

**Properties:**
- `name`: Test function name from template library
- `parameters`: Test-specific configuration
- `weight`: Relative importance within parent (0-100)

**Example:**
```json
{
  "name": "expect_output",
  "parameters": {
    "inputs": ["Alice"],
    "expected_output": "Hello, Alice!",
    "program_command": "python3 greeting.py"
  },
  "weight": 100
}
```

## Result Tree

The result tree is the output structure after grading. It mirrors the criteria tree but includes actual scores and reports.

### Structure

```json
{
  "final_score": 85.5,
  "root": {
    "base": {
      "name": "base",
      "score": 85.5,
      "weight": 100,
      "max_score": 100,
      "subjects": [
        {
          "name": "Functionality",
          "score": 90,
          "weight": 60,
          "max_score": 60,
          "tests": [
            {
              "name": "expect_output",
              "score": 100,
              "weight": 100,
              "max_score": 100,
              "report": "Test passed successfully!",
              "passed": true
            }
          ]
        },
        {
          "name": "Code Quality",
          "score": 80,
          "weight": 40,
          "max_score": 40,
          "tests": [
            {
              "name": "check_syntax",
              "score": 80,
              "weight": 100,
              "max_score": 100,
              "report": "Minor style issues detected",
              "passed": false
            }
          ]
        }
      ]
    },
    "bonus": {
      "name": "bonus",
      "score": 5,
      "weight": 10,
      "max_score": 10,
      "tests": [
        {
          "name": "extra_features",
          "score": 50,
          "weight": 100,
          "max_score": 100,
          "report": "Some extra features implemented",
          "passed": false
        }
      ]
    },
    "penalty": {
      "name": "penalty",
      "score": 0,
      "weight": -20,
      "max_score": 0,
      "tests": []
    }
  }
}
```

### Score Calculation

Scores are calculated hierarchically:

1. **Test Level**: Raw score (0-100) based on test execution
2. **Subject Level**: Weighted average of all tests within subject
3. **Category Level**: Weighted average of all subjects (or direct tests)
4. **Final Score**: `base_score + bonus_score - penalty_score`

**Example Calculation:**

```
Test 1: 100 (weight: 50) = 50 points
Test 2: 80 (weight: 50) = 40 points
Subject Score: (50 + 40) / 100 = 90

Subject 1: 90 (weight: 60) = 54 points
Subject 2: 80 (weight: 40) = 32 points
Base Score: (54 + 32) / 100 = 86

Bonus Score: 5 (from 10 max)
Penalty Score: 0

Final Score: 86 + 5 - 0 = 91
```

## Terminal grading outcome

The immutable [outcome v1](../contracts/OUTCOMES.md) contains execution identity,
provenance, language, timestamps, score/tree, optional feedback/comparison status,
and a safe error on required failure. A completed zero is distinct from a failed
execution with null score/tree.

`evaluate_submission` returns this artifact directly.
`build_pipeline(...).run(...)` returns a frozen `PipelineExecution` envelope
containing only `outcome`. Intermediate criteria, sessions, assessments and
result trees are ordinary local values in the coordinator.

Optional [diagnostic events](pipeline_execution_tracking.md) contain observations
without artifact data or references to the execution. They never drive grading.

## Test Result

Individual test execution result.

### Properties

```python
class TestResult:
    test_name: str                            # Name of the test function
    score: float                              # Score achieved (0-100)
    report: str                               # Human-readable result message
    subject_name: str = ""                    # Parent subject name
    parameters: Optional[Dict[str, Any]]      # Test parameters used
```

### Example

```json
{
  "test_name": "expect_output",
  "score": 100,
  "report": "Output matched expected value 'Hello, Alice!'",
  "subject_name": "Functionality",
  "parameters": {
    "inputs": ["Alice"],
    "expected_output": "Hello, Alice!",
    "program_command": "python3 main.py"
  }
}
```

## Submission

Student submission data.

### Properties

```python
class Submission:
    username: str                                   # Student identifier
    user_id: int                                    # Student ID
    assignment_id: int                              # Assignment identifier
    submission_files: Dict[str, SubmissionFile]     # Uploaded files keyed by filename
    language: Optional[Language] = None             # Programming language
    locale: str = "en"                              # Feedback locale
    evaluation_scope: Optional[EvaluationScope] = None
```

### Submission File

```python
class SubmissionFile:
    filename: str                              # Name of file
    content: str                               # Full file contents (text)
    changed_lines: Optional[Set[int]] = None   # One-indexed added/modified lines
    metadata: Optional[Dict[str, Any]] = None  # Opaque per-file context
```

`SubmissionFile.is_contribution_aware` is `True` when `changed_lines` was
provided, including when the caller explicitly provides an empty set.

### Evaluation Scope

```python
class EvaluationScope:
    scoped_files: List[str]  # Files that are the primary evaluation subject
```

When a scope is present, scope-aware pipeline steps restrict their work to the
listed filenames. Currently, structural analysis uses the scope to avoid
parsing unrelated files. Omitting the scope preserves snapshot behavior and
analyzes all eligible submission files.

### Metadata Ownership

Evaluation context is deliberately split by responsibility:

| Field | Pipeline behavior | Intended use |
|-------|-------------------|--------------|
| `EvaluationScope.scoped_files` | Read by scope-aware steps | Select files that analysis should focus on |
| `SubmissionFile.changed_lines` | Read by structural analysis and available to tests | Identify added or modified lines |
| `SubmissionFile.metadata` | Never interpreted; forwarded to test functions | Carry arbitrary per-file context |
| API `metadata` / database `submission_metadata` | Never read by the core pipeline | Preserve submission-level provenance and audit context |

Platform- or domain-specific data belongs in the open-ended metadata fields,
not in new typed core model fields. Test functions receive `evaluation_scope`
and a filename-keyed `file_metadata` mapping through `execute(**kwargs)`. They
also receive the original `SubmissionFile` objects, including `changed_lines`
and `metadata`, through the `files` argument.

## Template

Template provides test functions for a specific assignment type.

### Properties

```python
class Template:
    name: str                           # Template identifier
    tests: dict[str, TestFunction]      # Available test functions
    requires_sandbox: bool              # Whether code execution needed
    supported_languages: list[str]      # Compatible languages
```

### Test Function

```python
class TestFunction:
    name: str                          # Function identifier
    
    def execute(
        self,
        files: dict[str, str],
        sandbox: SandboxContainer | None,
        **kwargs
    ) -> TestResult:
        """Execute the test and return result"""
        pass
```
