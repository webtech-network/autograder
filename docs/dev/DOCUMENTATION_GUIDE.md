# Code Documentation Enhancement Guide

This document provides guidelines and examples for documenting code in the Autograder project. Following these standards ensures consistency and helps contributors understand the codebase.

---

## 📚 Documentation Standards

### Python Docstring Style

We use **Google-style docstrings** for all Python code.

#### Module Documentation

Every Python module should start with a module-level docstring:

```python
"""
Module Name

Brief description of what this module does (1-2 sentences).

Longer description explaining:
- Purpose and responsibility
- Key classes/functions
- Design patterns used
- Dependencies and relationships

Typical Usage:
    from module import Class
    instance = Class()
    instance.method()
"""
```

#### Class Documentation

```python
class ClassName:
    """
    Brief one-line description of the class.

    Longer description explaining:
    - What problem this class solves
    - How it fits into the larger system
    - Key responsibilities
    - Design patterns (if applicable)

    Attributes:
        attr1 (type): Description of attribute1
        attr2 (type): Description of attribute2

    Example:
        >>> instance = ClassName(param1, param2)
        >>> result = instance.method()
        >>> print(result)

    Note:
        Any important notes or warnings.
    """

    def __init__(self, param1: str, param2: int):
        """
        Initialize ClassName.

        Args:
            param1 (str): Description of param1
            param2 (int): Description of param2

        Raises:
            ValueError: If param2 is negative
        """
        pass
```

#### Function/Method Documentation

```python
def function_name(param1: str, param2: int = 0) -> bool:
    """
    Brief one-line description of what function does.

    Longer description if needed, explaining:
    - Algorithm or approach
    - Side effects
    - Performance considerations

    Args:
        param1 (str): Description of param1
            Can span multiple lines if needed
        param2 (int, optional): Description of param2
            Defaults to 0.

    Returns:
        bool: Description of return value
            True if success, False otherwise

    Raises:
        ValueError: When param1 is empty
        TypeError: When param2 is not an integer

    Example:
        >>> result = function_name("test", 5)
        >>> print(result)
        True

    Note:
        Any important notes about usage or behavior.
    """
    pass
```

---

## 🎯 What to Document

### Always Document

1. **Public APIs** - Any class, function, or method meant to be used by others
2. **Complex Logic** - Non-obvious algorithms or business rules
3. **Design Decisions** - Why something is done a certain way
4. **Parameters & Returns** - What goes in, what comes out
5. **Exceptions** - What errors can be raised and why
6. **Examples** - Show how to use the code

### Optional Documentation

1. **Private Methods** - Brief docstring if complex
2. **Simple Getters/Setters** - Only if non-obvious
3. **Override Methods** - Can reference parent documentation

### Don't Document

1. **Obvious Code** - Don't repeat what code already says
2. **Implementation Details** - Focus on "what" and "why", not "how"

---

## 💡 Inline Comments

Use inline comments to explain **why**, not **what**:

### ❌ Bad Comments (Stating the Obvious)

```python
# Increment counter
counter += 1

# Check if list is empty
if len(items) == 0:
    pass
```

### ✅ Good Comments (Explaining Why)

```python
# Use weighted average to prevent outliers from skewing scores
weighted_score = sum(s * w for s, w in zip(scores, weights))

# Pre-execute tests for AI analysis (must happen before tree finalization)
if template.requires_pre_executed_tree:
    criteria_tree = CriteriaTree.build_pre_executed_tree(template)
```

### Comment Sections

Use comment blocks to separate logical sections:

```python
# ========== STEP 1: PRE-FLIGHT SETUP ==========
# Run setup commands (e.g., npm install) if defined
if autograder_request.assignment_config.setup:
    impediments = PreFlight.run()

# ========== STEP 2: LOAD TEST TEMPLATE ==========
# Templates define how to run tests for specific assignment types
template_name = autograder_request.assignment_config.template
```

---

## 📝 Key Files Documentation Status

### ✅ Already Enhanced

- `autograder/autograder_facade.py` - Main grading pipeline
- `connectors/port.py` - Adapter interface
- `connectors/models/autograder_request.py` - Request model
- `autograder/builder/tree_builder.py` - Criteria tree construction
- `autograder/context.py` - Request context singleton

### 🔄 Needs Enhancement

#### High Priority

1. **`autograder/core/grading/grader.py`**
   - Add module docstring
   - Document recursive grading algorithm
   - Explain weight balancing
   - Add examples for weighted scoring

2. **`autograder/builder/models/criteria_tree.py`**
   - Document tree node classes
   - Explain parent-child relationships
   - Document weight propagation

3. **`autograder/builder/models/template.py`**
   - Explain template lifecycle
   - Document abstract methods
   - Provide template creation guide

4. **`autograder/core/report/reporter_factory.py`**
   - Document reporter types
   - Explain factory pattern usage
   - Show how to add new reporters

5. **`connectors/adapters/api/api_adapter.py`**
   - Document API request handling
   - Explain file upload processing
   - Add endpoint examples

6. **`connectors/adapters/github_action_adapter/github_adapter.py`**
   - Document GitHub integration
   - Explain event handling
   - Show how to configure

#### Medium Priority

7. **Template Library** (`autograder/builder/template_library/templates/`)
   - Document each template's purpose
   - Explain when to use each template
   - Provide configuration examples

8. **Execution Helpers** (`autograder/builder/execution_helpers/`)
   - Document executor types
   - Explain sandbox security
   - Document AI executor prompts

9. **Models** (`autograder/core/models/`)
   - Document data structures
   - Explain field purposes
   - Show serialization examples

10. **Utils** (`autograder/core/utils/`)
    - Document utility functions
    - Explain caching strategy
    - Show usage patterns

---

## 🎨 Examples by Component

### Grader Documentation Example

```python
class Grader:
    """
    Traverses criteria tree, executes tests, and calculates weighted scores.

    The grader implements a recursive tree traversal algorithm that:
    1. Visits each node in the criteria tree
    2. Executes tests at leaf nodes
    3. Aggregates scores using weighted averages
    4. Handles empty categories gracefully

    Scoring Algorithm:
        - Base category: Required tests, max 100 points
        - Bonus category: Optional extra credit
        - Penalty category: Deductions from final score
        - Final score = base + bonus - penalty (clamped to [0, 100])

    Weight Balancing:
        Weights at each level are normalized to sum to 100, ensuring
        proper proportional scoring regardless of user-specified weights.

    Attributes:
        criteria (Criteria): Root node of the criteria tree
        test_library (Template): Template defining test execution
        base_results (List[TestResult]): Test results from base category
        bonus_results (List[TestResult]): Test results from bonus category
        penalty_results (List[TestResult]): Test results from penalty category

    Example:
        >>> criteria_tree = CriteriaTree.build_non_executed_tree()
        >>> template = TemplateLibrary.get_template("web_dev")
        >>> grader = Grader(criteria_tree, template)
        >>> result = grader.run()
        >>> print(f"Score: {result.final_score}")
        Score: 85.5
    """

    def _grade_subject_or_category(
        self,
        current_node: Union['Subject', 'TestCategory'],
        submission_files: Dict,
        results_list: List['TestResult'],
        depth: int = 0
    ) -> Optional[float]:
        """
        Recursively grade a subject or category using depth-first traversal.

        This method implements the core recursive grading algorithm:
        - Leaf nodes (tests): Execute tests and return average score
        - Branch nodes (subjects): Recursively grade children and compute weighted average
        - Empty nodes: Return None to indicate no tests exist

        Args:
            current_node: Subject or TestCategory to grade
            submission_files: Student's submitted files
            results_list: Accumulator for test results
            depth: Current recursion depth (for logging indentation)

        Returns:
            Average score for this node (0-100), or None if no tests exist

        Algorithm:
            1. Base case: Node has tests
               - Execute each test
               - Calculate average score
               - Store results in results_list
               - Return average

            2. Recursive case: Node has children
               - Recursively grade each child
               - Filter out children with no tests (None)
               - Calculate weighted average of valid children
               - Return weighted score

            3. Empty case: No tests and no children
               - Return None

        Example:
            ```
            Subject: HTML Validation (weight: 40)
            ├── Test: Valid DOCTYPE
            │   Score: 100
            ├── Test: Proper Tags
            │   Score: 80
            └── Average: 90
            ```
        """
        pass
```

### Adapter Documentation Example

```python
class ApiAdapter(Port):
    """
    REST API adapter for the autograder system.

    This adapter implements the Port interface to enable HTTP-based
    access to the autograder. It handles:
    - Multipart file uploads
    - JSON configuration parsing
    - Error handling and HTTP status codes
    - Response formatting

    Workflow:
        1. Receive HTTP POST request with files and config
        2. Parse request into AutograderRequest
        3. Call core autograder
        4. Format response as JSON
        5. Return HTTP response

    Endpoints:
        POST /grade_submission/ - Grade a student submission
        GET /template/{name} - Get template information

    Request Format:
        multipart/form-data:
            - submission_files: List of files
            - template_preset: Template name
            - student_name: Student identifier
            - criteria_json: Grading criteria (if custom)
            - feedback_json: Feedback config (optional)

    Response Format:
        {
            "status": "pass" | "fail",
            "final_score": 85.5,
            "feedback": "Detailed feedback..."
        }

    Example:
        >>> import httpx
        >>> files = {"index.html": open("index.html", "rb")}
        >>> data = {
        ...     "template_preset": "web_dev",
        ...     "student_name": "alice@example.com"
        ... }
        >>> response = httpx.post(
        ...     "http://localhost:8000/grade_submission/",
        ...     files=files,
        ...     data=data
        ... )
        >>> print(response.json())
    """
```

---

## 🚀 Documentation TODOs

### Immediate (This Week)

- [ ] Add module docstrings to all Python files
- [ ] Document all public classes with examples
- [ ] Add inline comments for complex algorithms
- [ ] Update README with API documentation

### Short-term (This Month)

- [ ] Create template creation guide
- [ ] Document criteria configuration schema
- [ ] Add architecture diagrams to docs
- [ ] Create video tutorials for common tasks

### Long-term (This Quarter)

- [ ] Set up Sphinx documentation site
- [ ] Auto-generate API reference from docstrings
- [ ] Create contributor's guide with examples
- [ ] Add interactive examples/playground

---

## 🔧 Tools for Documentation

### Docstring Generation

```bash
# Generate documentation from docstrings
pip install sphinx sphinx-autodoc-typehints

# Build HTML docs
cd docs
make html
```

### Docstring Linting

```bash
# Check docstring quality
flake8 --select=D autograder/

# Or use pydocstyle
pydocstyle autograder/
```

### Type Hints

Always include type hints - they're documentation!

```python
def process_score(
    score: float,
    weights: List[float],
    category: str
) -> Tuple[float, str]:
    """Process weighted score for a category."""
    pass
```

---

## 📋 Documentation Checklist

Before submitting PR, ensure:

- [ ] Module has docstring explaining purpose
- [ ] All public classes have docstrings
- [ ] All public methods have docstrings with Args/Returns
- [ ] Complex algorithms have explanatory comments
- [ ] At least one usage example provided
- [ ] Type hints included for all parameters
- [ ] Exceptions documented if raised
- [ ] Links to related documentation included

---

## 📚 Additional Resources

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [PEP 257 - Docstring Conventions](https://www.python.org/dev/peps/pep-0257/)
- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [Type Hints (PEP 484)](https://www.python.org/dev/peps/pep-0484/)

---

**Remember**: Good documentation is as important as good code. Document with empathy for future contributors (including future you)!
