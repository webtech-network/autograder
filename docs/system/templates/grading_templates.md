# Grading Templates

## Overview

**Grading templates** are pre-built collections of test functions designed for specific assignment types. They provide ready-to-use, highly customizable tests that significantly simplify the process of creating grading criteria for common assignment categories.

Instead of writing test logic from scratch, teachers can select a template that matches their assignment type and configure which tests to run with specific parameters.

---

## What is a Template?

A template is a **library of related test functions** for a specific domain. Each template contains:

- **Test Functions**: Individual checks that can be executed
- **Execution Logic**: How tests are run and evaluated
- **Execution Helpers**: Optional specialized components for complex operations (containers, batch processing, etc.)

### Available Templates

| Template Name | Purpose | Example Use Cases |
|--------------|---------|-------------------|
| `web dev` | Web development assignments | HTML structure, CSS styling, JavaScript functionality |
| `api` | API testing | Endpoint validation, request/response checking, authentication |
| `essay` | Essay grading with AI | Thesis statements, grammar, argumentation, coherence |
| `I/O` | Input/Output programs | Command-line programs, script execution, console I/O |
| `custom` | Custom implementation | Any assignment requiring specialized test logic |

---

## How Templates Work

### The Template Selection Process

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Teacher Specifies Template                               │
│    - In AssignmentConfig: template="web dev"                │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Teacher Defines Tests in criteria.json                   │
│    - Selects test names from template                       │
│    - Provides parameters for each test                      │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Autograder Loads Template                                │
│    - TemplateLibrary.get_template("web dev")                │
│    - Initializes execution helpers if needed                │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Criteria Tree Builder Matches Tests                      │
│    - Maps test names in criteria.json to template tests     │
│    - Creates Test objects with parameters                   │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Grader Executes Tests                                    │
│    - Calls template.get_test(name)                          │
│    - Executes test.execute(file_content, *params)           │
│    - Receives TestResult objects                            │
└────────────────┬────────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Cleanup                                                  │
│    - template.stop() cleans up execution helpers            │
└─────────────────────────────────────────────────────────────┘
```

---

## Test Functions: The Building Blocks

### Anatomy of a Test Function

Every test in a template is a **TestFunction** object with the following structure:

```python
class ExampleTest(TestFunction):
    @property
    def name(self) -> str:
        """The unique identifier for this test."""
        return "example_test"
    
    @property
    def description(self) -> str:
        """Human-readable description of what this test checks."""
        return "Checks if the submission contains valid examples"
    
    @property
    def parameter_description(self) -> str:
        """Explains what parameters this test accepts."""
        return "min_count: Minimum number of examples required"
    
    def execute(self, file_content: str, min_count: int) -> TestResult:
        """
        The actual test logic.
        
        Args:
            file_content: The content of the file being tested
            min_count: Custom parameter from criteria.json
            
        Returns:
            TestResult with score (0-100) and feedback
        """
        # Test logic here
        found_examples = count_examples(file_content)
        
        if found_examples >= min_count:
            score = 100
            feedback = f"Found {found_examples} examples (required: {min_count})"
        else:
            score = (found_examples / min_count) * 100
            feedback = f"Only found {found_examples}/{min_count} required examples"
        
        return TestResult(
            name="example_test",
            score=score,
            report=feedback,
            subject_name="content_quality"
        )
```

### Key Components

#### 1. **Name** (Required)
- Unique identifier used in `criteria.json`
- Used to match tests: `template.get_test(name)`
- Convention: lowercase with underscores (e.g., `has_tag`, `check_css_linked`)

#### 2. **Description** (Required)
- Explains what the test checks
- Used for documentation and error messages

#### 3. **Parameter Description** (Required)
- Documents what parameters the test accepts
- Helps teachers understand how to configure the test

#### 4. **Execute Method** (Required)
- Contains the actual test logic
- **Always returns a `TestResult` object**
- Score range: **0 to 100** (represents percentage)
- Parameters:
  - First parameter is typically the file content or submission data
  - Additional parameters come from `criteria.json`

---

## Test Parameterization

One of the most powerful features of templates is **test customization through parameters**.

### Example: The `has_tag` Test

**Test Definition** (in template):
```python
class HasTag(TestFunction):
    def execute(self, html_content: str, tag: str, required_count: int) -> TestResult:
        """Checks if HTML contains a specific tag N times."""
        soup = BeautifulSoup(html_content, 'html.parser')
        found = soup.find_all(tag)
        actual_count = len(found)
        
        if actual_count >= required_count:
            score = 100
            feedback = f"✓ Found {actual_count} <{tag}> tags (required: {required_count})"
        else:
            score = (actual_count / required_count) * 100
            feedback = f"✗ Found only {actual_count}/{required_count} <{tag}> tags"
        
        return TestResult("has_tag", score, feedback, "html_structure")
```

**Test Usage** (in `criteria.json`):
```json
{
  "file": "index.html",
  "name": "has_tag",
  "calls": [
    ["body", 1],
    ["header", 1],
    ["article", 4],
    ["img", 5]
  ]
}
```

**What Happens**:
1. The test is called **4 times** (once per call)
2. Each call checks for a different tag/count combination
3. Four `TestResult` objects are generated
4. Scores are averaged for the subject

This allows **one test function** to validate **multiple requirements** with different parameters!

---

## The TestResult Object

Every test execution produces a `TestResult` object:

```python
class TestResult:
    def __init__(self, name: str, score: float, report: str, subject_name: str):
        self.name = name              # Test function name
        self.score = score            # 0-100 percentage score
        self.report = report          # Feedback message
        self.subject_name = subject_name  # Parent subject in criteria tree
        self.passed = score >= 70     # Typically 70% threshold
```

**Example Results**:
```python
# Passing test
TestResult(
    name="has_tag",
    score=100,
    report="✓ Found 5 <img> tags (required: 5)",
    subject_name="html_structure"
)

# Failing test
TestResult(
    name="has_tag",
    score=50,
    report="✗ Found only 2/4 <article> tags",
    subject_name="html_structure"
)
```

---

## Execution Helpers

For templates that require complex operations (containers, API batching, databases), **Execution Helpers** handle the heavy lifting.

### What are Execution Helpers?

Execution Helpers are specialized components that:
- Provide infrastructure for test execution (e.g., Docker containers)
- Handle complex patterns (e.g., batch API requests)
- Manage lifecycle (start/stop operations)

### Helper Lifecycle

```python
# At grading start
template.start()  # Initializes helpers (starts containers, opens connections)

# During testing
test.execute()    # Tests use helpers via self.executor

# At grading end
template.stop()   # Cleanup (removes containers, closes connections)
```

### Example 1: Sandbox Executor

**Purpose**: Isolates and executes untrusted student code in Docker containers

**Used by**: `I/O` template, `api` template

**How it Works**:

```python
class InputOutputTemplate(Template):
    def __init__(self):
        self.executor = None  # Will hold SandboxExecutor
    
    def start(self):
        """Initialize the container before grading."""
        self.executor = SandboxExecutor.start()
    
    def stop(self):
        """Clean up the container after grading."""
        if self.executor:
            self.executor.stop()

class RunScript(TestFunction):
    def execute(self, script_content: str, test_input: str) -> TestResult:
        """Run student's script with input in isolated container."""
        # Use the executor from the template
        exit_code, stdout, stderr = self.executor.run_command(
            f"python script.py <<< '{test_input}'"
        )
        
        # Evaluate output
        if exit_code == 0 and stdout == expected_output:
            return TestResult("run_script", 100, "✓ Correct output", "execution")
        else:
            return TestResult("run_script", 0, f"✗ Got: {stdout}", "execution")
```

**Lifecycle**:
1. `start()`: Creates Docker container, copies student files
2. `execute()`: Runs commands inside container
3. `stop()`: Removes container

---

### Example 2: AI Executor

**Purpose**: Batch AI-powered tests to minimize API latency

**Used by**: `essay` template

**The Problem**:
- Traditional execution: Each test makes one API call (~5 seconds each)
- With 10 tests: 50 seconds of sequential waiting ❌

**The Solution**:
- Collect all tests first (no execution)
- Send one batch request with all tests (~5 seconds total) ✅

**How it Works**:

```python
class EssayGraderTemplate(Template):
    def __init__(self):
        self.ai_executor = AiExecutor()
    
    def stop(self):
        """Trigger batch execution and map results."""
        self.ai_executor.execute_batch()  # Sends one API request
        self.ai_executor.mapback()        # Maps results to TestResults

class GrammarCheck(TestFunction):
    def execute(self, essay_content: str) -> TestResult:
        """Doesn't actually execute - just registers with AI executor."""
        # Create empty TestResult as placeholder
        placeholder = self.ai_executor.add_test(
            test_name="grammar_check",
            test_prompt=f"Evaluate grammar in this essay:\n{essay_content}"
        )
        return placeholder  # Will be filled later by mapback()
```

**Execution Flow**:

```
1. Tree Building Phase:
   ├─ Test 1: execute() → registers with AI executor → returns placeholder
   ├─ Test 2: execute() → registers with AI executor → returns placeholder
   ├─ Test 3: execute() → registers with AI executor → returns placeholder
   └─ ... (all tests registered)

2. Batch Execution (template.stop()):
   ├─ AI executor sends ONE request with all test prompts
   ├─ OpenAI returns all results in one response
   └─ mapback() updates all placeholder TestResults with real scores

3. Result Processing:
   └─ All TestResults now have real scores and feedback
```

**Efficiency Gain**:
- Before: 10 tests × 5 seconds = **50 seconds**
- After: 1 batch request = **~7 seconds**
- **7x faster!** 🚀

---

## Using Templates in Practice

### Step 1: Choose Your Template

In `AssignmentConfig`:
```python
assignment_config = AssignmentConfig(
    template="web dev",  # Select template
    criteria=criteria_json,
    setup=setup_json,
    feedback=feedback_json
)
```

### Step 2: Reference Tests in criteria.json

Browse the template's available tests and add them to your criteria:

```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "html_structure": {
        "weight": 50,
        "tests": [
          {
            "file": "index.html",
            "name": "has_tag",
            "calls": [
              ["body", 1],
              ["header", 1]
            ]
          },
          {
            "file": "index.html",
            "name": "check_css_linked"
          }
        ]
      }
    }
  }
}
```

### Step 3: Let the Autograder Handle the Rest

The autograder will:
1. Load the `web dev` template
2. Match test names (`has_tag`, `check_css_linked`)
3. Execute tests with parameters
4. Collect `TestResult` objects
5. Calculate weighted scores
6. Generate feedback

---

## Template Comparison

### Web Dev Template

**Best for**: HTML, CSS, JavaScript assignments

**Key Tests**:
- `has_tag`: Check for HTML tags
- `has_attribute`: Verify attributes
- `check_css_linked`: Ensure CSS is linked
- `uses_relative_units`: Check responsive design
- `js_uses_dom_manipulation`: Verify JavaScript DOM usage

**Execution Helper**: None (static file analysis)

**Example Assignment**: Build a portfolio website

---

### API Template

**Best for**: RESTful API implementations

**Key Tests**:
- `endpoint_exists`: Check if route exists
- `check_status_code`: Verify HTTP responses
- `validate_json_schema`: Ensure proper data structure
- `check_authentication`: Test auth mechanisms

**Execution Helper**: `SandboxExecutor` (runs server in container)

**Example Assignment**: Build a task management API

---

### Essay Template

**Best for**: Written assignments requiring AI analysis

**Key Tests**:
- `thesis_statement`: Check for clear thesis
- `grammar_and_spelling`: Detect errors
- `clarity_and_cohesion`: Evaluate flow
- `counterargument_handling`: Check argumentation
- `logical_fallacy_check`: Detect reasoning errors

**Execution Helper**: `AiExecutor` (batch OpenAI requests)

**Example Assignment**: Argumentative essay on technology

---

### I/O Template

**Best for**: Command-line programs, scripts

**Key Tests**:
- `run_with_input`: Execute with test input
- `check_output`: Verify console output
- `check_exit_code`: Ensure proper termination
- `test_error_handling`: Validate error cases

**Execution Helper**: `SandboxExecutor` (executes in container)

**Example Assignment**: Python calculator program

---

### Custom Template

**Best for**: Specialized assignments not covered by other templates

**How it works**:
- Teacher provides custom Python code
- Code must define a class inheriting from `Template`
- Can include any test logic needed

**Example**:
```python
from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction

class DatabaseTest(TestFunction):
    @property
    def name(self):
        return "check_sql_query"
    
    def execute(self, query: str) -> TestResult:
        # Custom test logic
        pass

class DatabaseTemplate(Template):
    def __init__(self):
        self.tests = [DatabaseTest()]
    
    def get_test(self, name: str) -> TestFunction:
        for test in self.tests:
            if test.name == name:
                return test
        raise ValueError(f"Test '{name}' not found")
```

---

## Best Practices

### 1. **Understand Test Parameters**
Before using a test, review its `parameter_description` to understand what arguments it needs.

### 2. **Use Multiple Calls for Efficiency**
Instead of:
```json
{"file": "index.html", "name": "has_tag", "calls": [["body", 1]]},
{"file": "index.html", "name": "has_tag", "calls": [["header", 1]]}
```

Do this:
```json
{
  "file": "index.html",
  "name": "has_tag",
  "calls": [
    ["body", 1],
    ["header", 1]
  ]
}
```

### 3. **Specify Correct Files**
Ensure the `file` field points to the actual submission file:
```json
{"file": "index.html", "name": "has_tag", "calls": [...]}
{"file": "css/styles.css", "name": "check_media_queries"}
```

### 4. **Use "all" for Project-Wide Tests**
Some tests need access to all files:
```json
{"file": "all", "name": "check_dir_exists", "calls": [["css"], ["imgs"]]}
```

### 5. **Leverage Template Features**
If a template uses an execution helper (AI, sandbox), ensure:
- Setup configuration is correct
- Required API keys are provided
- Container images are specified (for sandbox)

---

## How Grading Uses Templates

### The Complete Flow

```python
# 1. Teacher creates request
request = AutograderRequest(
    submission_files={"index.html": "<html>...</html>"},
    assignment_config=AssignmentConfig(
        template="web dev",
        criteria=criteria_json,
        setup=setup_json,
        feedback=feedback_json
    ),
    student_name="Alice"
)

# 2. Autograder loads template
template = TemplateLibrary.get_template("web dev")

# 3. Criteria tree is built
criteria_tree = CriteriaTree.build_non_executed_tree()

# 4. Grader traverses tree and executes tests
grader = Grader(criteria_tree, template)

# During grading, for each test:
test_function = template.get_test("has_tag")
result = test_function.execute(html_content, "body", 1)

# 5. Results collected and scored
final_score = grader.run()

# 6. Template cleanup
template.stop()
```

---

## Advanced: Creating Custom Tests

If you need a test not provided by existing templates, you can:

### Option 1: Use Custom Template
Provide your own template code in `AssignmentConfig`:

```python
custom_code = """
from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction

class MyCustomTest(TestFunction):
    # ... implement your test
    pass

class MyCustomTemplate(Template):
    # ... implement your template
    pass
"""

assignment_config = AssignmentConfig(
    template="custom",
    custom_template_str=custom_code,
    criteria=criteria_json,
    setup=setup_json,
    feedback=feedback_json
)
```

### Option 2: Extend Existing Template
Inherit from an existing template and add tests:

```python
class ExtendedWebDev(WebDevTemplate):
    def __init__(self):
        super().__init__()
        self.custom_tests = [MyNewTest()]
    
    def get_test(self, name: str):
        # Try custom tests first
        for test in self.custom_tests:
            if test.name == name:
                return test
        # Fall back to parent template
        return super().get_test(name)
```

---

## Summary

Templates provide:
- ✅ **Reusable test collections** for common assignment types
- ✅ **Parameterized tests** for maximum flexibility
- ✅ **Execution helpers** for complex operations (containers, AI batching)
- ✅ **Standardized TestResult objects** for consistent grading
- ✅ **Easy configuration** through `criteria.json`

**Key Concept**: You select a template, reference its tests by name, provide parameters, and the autograder handles execution and scoring automatically.

---

## Related Documentation

- **[Criteria Configuration](../configuration/criteria_config.md)** - How to reference template tests
- **[Setup Configuration](../configuration/setup_config.md)** - Configure execution helpers
- **[Getting Started](../getting_started.md)** - Complete workflow overview

---

## Template Quick Reference

| Template | Execution Helper | Best For | API Keys Required |
|----------|-----------------|----------|-------------------|
| `web dev` | None | HTML/CSS/JS | No |
| `api` | SandboxExecutor | REST APIs | No |
| `essay` | AiExecutor | Written work | Yes (OpenAI) |
| `I/O` | SandboxExecutor | CLI programs | No |
| `custom` | User-defined | Anything | Depends |

Choose your template wisely and unlock powerful, flexible automated grading! 🎓
