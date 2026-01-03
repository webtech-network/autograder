# Pipeline Logic for Criteria Tree and Tree Building

## Overview

The pipeline implements conditional logic to optimize grading based on the number of submissions. This design eliminates unnecessary tree construction overhead when grading single submissions while maintaining efficient batch processing for multiple submissions.

## Key Concepts

### Why Two Paths?

**Single Submission Path**: When grading only one submission, building a criteria tree and then traversing it is redundant. We can directly process the criteria configuration and build the result tree in one pass.

**Multiple Submissions Path**: When grading multiple submissions, the criteria tree becomes valuable because:
- The tree structure is built once and reused for all submissions
- Reduces redundant parsing and validation
- Improves overall performance through tree reuse

## Pipeline Flow Diagram

### Single Submission Path (Optimized)
```
┌─────────────────────┐
│  Criteria Config    │
│  (JSON/Dict)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    GradeStep        │
│ grade_from_config() │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   ResultTree        │
│  (Final Score)      │
└─────────────────────┘
```

### Multiple Submissions Path (Tree-Based)
```
┌─────────────────────┐
│  Criteria Config    │
│  (JSON/Dict)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  BuildTreeStep      │
│  (Build Once)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  CriteriaTree       │
│  (Reusable)         │
└──────────┬──────────┘
           │
           ▼
    ┌──────┴──────┐
    │  For Each   │
    │ Submission  │
    └──────┬──────┘
           │
           ▼
┌─────────────────────┐
│    GradeStep        │
│  grade_from_tree()  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   ResultTree        │
│  (Per Submission)   │
└─────────────────────┘
```

## Step Implementations

### BuildTreeStep

**Responsibility**: Construct hierarchical criteria tree from configuration

**Input**: 
- Criteria configuration (dict)
- Template instance
- Submission files (for validation)

**Output**: 
- `CriteriaTree` object (fully built with test functions resolved)

**When Executed**: 
- Only when `len(submissions) > 1`

**Key Features**:
- Validates JSON schema using Pydantic models
- Resolves test functions from template library
- Stores test parameters and file references
- Builds complete tree structure with weights

### GradeStep

**Responsibility**: Execute grading and produce result tree

**Input Detection Logic**:
```python
if isinstance(input_data, CriteriaTree):
    # Use tree-based grading
    result = grader_service.grade_from_tree(criteria_tree, submission)
else:
    # Use config-based grading
    result = grader_service.grade_from_config(criteria_config, template, submission)
```

**Two Grading Methods**:

1. **`grade_from_config()`** - Single submission optimization
   - Directly processes criteria configuration
   - Builds result tree while executing tests
   - Single-pass algorithm (no tree pre-construction)

2. **`grade_from_tree()`** - Multiple submission efficiency
   - Traverses pre-built criteria tree
   - Executes tests from tree nodes
   - Builds result tree from criteria tree structure

**Output**: 
- `ResultTree` object with scores and feedback

## Pipeline Configuration Logic

### Automatic Path Selection

```python
def configure_pipeline(submissions: List[Submission], criteria_config: dict):
    """
    Automatically configures pipeline based on submission count.
    """
    if len(submissions) == 1:
        # Single submission: Skip tree building
        return [
            PreFlightStep(),
            LoadTemplateStep(),
            GradeStep(),  # Uses grade_from_config
            FeedbackStep(),
            ExportStep()
        ]
    else:
        # Multiple submissions: Build tree once, reuse
        return [
            PreFlightStep(),
            LoadTemplateStep(),
            BuildTreeStep(),  # Build criteria tree
            GradeStep(),  # Uses grade_from_tree
            FeedbackStep(),
            ExportStep()
        ]
```

## Data Flow Example

### Single Submission Example

**Input**:
```json
{
  "criteria": {
    "name": "HTML Assignment",
    "tests": [
      {"name": "check_title", "weight": 50},
      {"name": "check_header", "weight": 50}
    ]
  },
  "submissions": [
    {"files": ["index.html"]}
  ]
}
```

**Flow**:
1. Criteria config loaded as dict
2. GradeStep detects dict input
3. Calls `grade_from_config(criteria, template, submission)`
4. Executes tests and builds result tree simultaneously
5. Returns final result tree

### Multiple Submissions Example

**Input**:
```json
{
  "criteria": { /* same as above */ },
  "submissions": [
    {"files": ["index.html"]},
    {"files": ["index.html"]},
    {"files": ["index.html"]}
  ]
}
```

**Flow**:
1. Criteria config loaded as dict
2. BuildTreeStep creates `CriteriaTree` (once)
3. For each submission:
   - GradeStep detects `CriteriaTree` input
   - Calls `grade_from_tree(tree, submission)`
   - Executes tests from tree
   - Returns result tree for that submission
4. Collects all result trees

## Performance Implications

### Single Submission
- **Avoided Overhead**: No tree construction/traversal
- **Memory**: Lower (no tree object created)
- **Speed**: Faster for single grading
- **Complexity**: O(n) where n = number of tests

### Multiple Submissions
- **Tree Construction**: One-time cost
- **Per-Submission**: Fast traversal (reuse structure)
- **Memory**: Higher (tree persists)
- **Speed**: Faster overall for batch processing
- **Complexity**: O(t + n*m) where t = tree building, n = submissions, m = tests

## Error Handling

### BuildTreeStep Errors
- Missing test functions in template
- Invalid JSON schema
- Malformed criteria structure
- **Result**: Pipeline fails early (before grading)

### GradeStep Errors
- Test execution failures
- File access issues
- Runtime errors in test functions
- **Result**: Captured in ResultTree as test failures

## Type Safety

The GradeStep uses robust type checking to determine the grading method:

```python
from autograder.models.criteria_tree import CriteriaTree

# Type checking
if isinstance(input_data, CriteriaTree):
    # Definitely a tree
    use_grade_from_tree()
elif isinstance(input_data, dict):
    # Configuration dictionary
    use_grade_from_config()
else:
    # Error: unexpected input type
    raise TypeError("Invalid input type for GradeStep")
```

## Benefits of This Architecture

### 1. Performance Optimization
- Single submissions: No unnecessary tree overhead
- Multiple submissions: Efficient tree reuse

### 2. Flexibility
- Same pipeline handles both scenarios
- Automatic path selection based on input

### 3. Maintainability
- Clear separation of concerns
- Each step has single responsibility
- Easy to modify or extend

### 4. Consistency
- Both paths produce identical `ResultTree` output
- Same scoring algorithm regardless of path
- Unified error handling

### 5. Testability
- Each grading method can be tested independently
- Clear input/output contracts
- Easier to debug issues

## Migration from Old Architecture

### Old Approach Problems
- Pre-executed trees (confusing concept)
- AI Executor as lazy-loading proxy (complex)
- Multiple traversals (inefficient)
- Mixed responsibilities

### New Approach Solutions
- ✅ Single clear tree type: `CriteriaTree`
- ✅ Result tree built during grading
- ✅ Optional tree building (conditional)
- ✅ Clear step responsibilities
- ✅ Batch optimization handled separately

## Future Enhancements

### Potential Optimizations
1. **Parallel Execution**: Grade multiple submissions in parallel
2. **Caching**: Cache template loading across requests
3. **Streaming**: Stream results as they complete
4. **Incremental Results**: Return partial results for long-running grades

### AI Executor Integration
For AI-based tests (e.g., essay grading):
- Collect all AI tests during tree traversal
- Batch API calls (single request)
- Map results back to result tree nodes
- Minimize API latency impact

## Conclusion

The pipeline's conditional tree-building logic provides an optimal balance between simplicity and performance. By detecting submission count and automatically choosing the appropriate path, we achieve:

- **Fast single-submission grading** (no tree overhead)
- **Efficient batch processing** (tree reuse)
- **Clean architecture** (clear separation)
- **Type-safe execution** (runtime validation)

This design sets a solid foundation for scaling the autograder system while maintaining code clarity and performance.

