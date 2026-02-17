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

## Grading Result

The complete grading result object returned after pipeline execution.

### Properties

```python
class GradingResult:
    final_score: float           # Overall grade (0-100+)
    feedback: str | None         # Generated feedback (if enabled)
    result_tree: ResultTree      # Detailed score breakdown
    execution_metadata: dict     # Pipeline execution info
```

### Example

```json
{
  "final_score": 91.0,
  "feedback": "Great work! Your program meets most requirements...",
  "result_tree": {
    "final_score": 91.0,
    "root": { ... }
  },
  "execution_metadata": {
    "template_used": "input_output",
    "sandbox_language": "python",
    "execution_time_seconds": 2.3,
    "tests_executed": 12,
    "tests_passed": 10,
    "timestamp": "2026-02-16T10:05:03Z"
  }
}
```

## Pipeline Execution

Internal state object passed between pipeline steps.

### Properties

```python
class PipelineExecution:
    submission: Submission           # Student files and metadata
    template: Template              # Loaded test functions
    criteria_tree: CriteriaTree     # Grading rubric
    result_tree: ResultTree         # Test results (populated during grading)
    sandbox: SandboxContainer       # Execution environment (if needed)
    focus_tests: list[str]          # High-impact failed tests
    feedback: str                   # Generated feedback
    config: PipelineConfig          # Pipeline settings
```

## Test Result

Individual test execution result.

### Properties

```python
class TestResult:
    test_name: str          # Name of the test function
    score: float            # Score achieved (0-100)
    report: str             # Human-readable result message
    passed: bool            # Whether test passed (score >= threshold)
    execution_time: float   # Time taken in seconds
    error: str | None       # Error message (if test crashed)
```

### Example

```json
{
  "test_name": "expect_output",
  "score": 100,
  "report": "Output matched expected value 'Hello, Alice!'",
  "passed": true,
  "execution_time": 0.15,
  "error": null
}
```

## Submission

Student submission data.

### Properties

```python
class Submission:
    files: list[SubmissionFile]    # Uploaded files
    language: str                   # Programming language
    metadata: dict                  # Additional context
    assignment_id: int              # Assignment identifier
    username: str                   # Student identifier
    user_id: int                    # Student ID
```

### Submission File

```python
class SubmissionFile:
    filename: str      # Name of file
    content: str       # File contents (text)
    path: str          # Relative path in submission
```

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

