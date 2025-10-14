# Core Concepts

This guide explains the fundamental principles and inner workings of the autograder, including how it evaluates student submissions and how the grading criteria are structured. Understanding these concepts is essential for effectively creating and managing assignments.

---

## The Criteria Tree: The Heart of the Autograder

The entire grading process is centered around the **Criteria Tree**, a hierarchical data structure that completely represents a grading package. This tree encapsulates:

- **Score preferences** (weights and point distributions)
- **Test organization** (subjects and categories)
- **Test configurations** (which tests to run and with what parameters)

The Criteria Tree is built from the `criteria.json` configuration file and serves as the blueprint for the entire grading process.

### Why a Tree Structure?

The tree structure provides several key advantages:

1. **Hierarchical Organization**: Tests are naturally grouped into logical categories and subjects
2. **Weight Propagation**: Scores can be weighted at any level and automatically cascade down
3. **Flexible Composition**: Subjects can be nested to any depth
4. **Clear Separation**: Base, bonus, and penalty tests are distinctly separated
5. **Efficient Traversal**: Recursive algorithms can easily process the entire structure

---

## Tree Structure Overview

The Criteria Tree has a fixed structure with four levels:

```
                           Root (Criteria)
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
        Base (100)           Bonus (0-100)      Penalty (0-100)
      (Category)             (Category)         (Category)
            │                    │                    │
    ┌───────┴───────┐    ┌───────┴───────┐    ┌───────┴───────┐
    ▼               ▼    ▼               ▼    ▼               ▼
 Subject A      Subject B Subject C    Subject D Subject E    Subject F
 (weight: 60)   (weight: 40) (weight: 50) (weight: 50) (weight: 100)
    │               │        │               │        │
    ▼               ▼        ▼               ▼        ▼
  Tests          Tests      Tests           Tests    Tests
 (Leaves)       (Leaves)   (Leaves)        (Leaves) (Leaves)
```

### Level 1: Root Node (Criteria)

- Represents the entire grading configuration
- Has exactly three children: `base`, `bonus`, and `penalty` categories
- Defines the overall scoring strategy

### Level 2: Category Nodes

The three main categories, each with a specific purpose:

#### **Base Category** (100 points)
- Contains **mandatory requirements** for the assignment
- Tests here check for essential, core functionality
- A student must pass these to meet minimum criteria
- The base score forms the foundation of the final grade
- **Always worth 100 points** (represents 100% of base requirements)

#### **Bonus Category** (0-100 points, configurable)
- Contains **optional features or extra credit** tests
- Tests here check for advanced features beyond basic requirements
- Bonus points are **only added if base score < 100**
- Rewards students for going above and beyond
- Weight is configurable (e.g., 20, 40, 50 bonus points available)

#### **Penalty Category** (0-100 points, configurable)
- Contains tests for **explicitly forbidden** elements
- Tests here check for bad practices, deprecated features, or prohibited tools
- Points are **subtracted from final score** when violations are found
- Enforces best practices and assignment constraints
- Weight is configurable (e.g., 25, 50 penalty points possible)

### Level 3: Subject Nodes (Branches)

- Represent logical groupings of related tests
- Can be **nested** to any depth (subjects within subjects)
- Each subject has a **weight** (percentage of parent's max score)
- Examples: `html`, `css`, `javascript`, `api-endpoints`, `structure`, `styling`
- You can define as many subjects as needed for your assignment

**Important Rule**: A subject can contain **EITHER** tests **OR** nested subjects, but not both.

### Level 4: Test Nodes (Leaves)

- Represent the actual test functions to be executed
- Each test is associated with a file to test
- Tests can have parameters for customization
- Tests can be called multiple times with different parameters
- Each test execution produces a `TestResult` object

---

## The Grading Algorithm: Tree Traversal and Aggregation

The grading process is implemented as a **recursive tree traversal and score aggregation algorithm** in the `Grader` class. Here's how it works:

### Algorithm Overview

```
1. Start at Root (Criteria)
2. For each Category (Base, Bonus, Penalty):
   a. Recursively traverse subjects (pre-order)
   b. When leaf nodes (tests) are found:
      - Execute all tests in that subject
      - Calculate average score from test results
      - Weight the average by subject's weight
   c. Propagate weighted scores up the tree
   d. Aggregate sibling subject scores
3. Apply final scoring formula:
   final = base + bonus (if base < 100) - penalty
4. Return final score and all test results
```

### Detailed Traversal Process

#### Phase 1: Pre-Order Traversal to Leaves

The grader starts at a category node and recursively descends until it finds leaves (tests):

```python
def _grade_subject_or_category(node, submission_files, depth=0):
    # BASE CASE: Node is a leaf with tests
    if node.has_tests():
        # Execute all tests
        for test in node.tests:
            test_results = test.execute(submission_files)
        
        # Calculate average score
        average_score = sum(result.score for result in test_results) / len(test_results)
        return average_score
    
    # RECURSIVE CASE: Node has child subjects
    else:
        # Recursively grade each child subject
        child_scores = {}
        for child_subject in node.subjects:
            child_scores[child_subject.name] = _grade_subject_or_category(
                child_subject, submission_files, depth + 1
            )
        
        # Weight and aggregate child scores
        weighted_score = calculate_weighted_average(child_scores, weights)
        return weighted_score
```

#### Phase 2: Test Execution at Leaves

When the traversal reaches a leaf node (subject with tests):

1. **Execute each test** in the subject
2. Each test returns a `TestResult` object with:
   - Test name
   - Score (0-100)
   - Feedback report
   - Subject name
3. **Calculate average** of all test scores in the subject
4. **Store results** in category-specific list (base_results, bonus_results, penalty_results)

**Example**:
```
Subject: "html_structure" (weight: 40%)
├─ Test: has_tag("body", 1) → Result: 100/100
├─ Test: has_tag("header", 1) → Result: 100/100
├─ Test: has_tag("article", 4) → Result: 50/100
└─ Average: (100 + 100 + 50) / 3 = 83.33
```

#### Phase 3: Weight Application and Upward Propagation

After calculating the average score for a subject, it's weighted by the subject's weight:

```
Subject Score = Average Test Score × (Subject Weight / Parent's Total Weight)
```

**Example**:
```
HTML Category (60% of Base)
├─ Structure Subject (40% of HTML = 24% of Base)
│  └─ Average Score: 83.33
│  └─ Weighted Score: 83.33 × 0.4 = 33.33
└─ Links Subject (60% of HTML = 36% of Base)
   └─ Average Score: 90.0
   └─ Weighted Score: 90.0 × 0.6 = 54.0

HTML Total: (33.33 × 0.4 + 54.0 × 0.6) = 45.73
```

#### Phase 4: Sibling Aggregation

When multiple subjects exist at the same level, their weighted scores are aggregated:

```
Parent Score = Σ(Child Score × Child Weight / Total Weight)
```

This process continues recursively up the tree until reaching the category level.

#### Phase 5: Final Score Calculation

Once all three categories are scored, the final score is calculated:

```python
def _calculate_final_score(base_score, bonus_score, penalty_points):
    final_score = base_score  # Start with base (0-100)
    
    # Add bonus only if base didn't reach 100
    if final_score < 100:
        bonus_to_add = (bonus_score / 100) × bonus_weight
        final_score += bonus_to_add
    
    # Cap at 100 before penalties
    final_score = min(100, final_score)
    
    # Subtract penalty
    penalty_to_subtract = (penalty_points / 100) × penalty_weight
    final_score -= penalty_to_subtract
    
    # Ensure score stays in valid range
    return max(0, min(100, final_score))
```

**Example Calculation**:
```
Base Score: 82/100
Bonus Score: 90/100 (weight: 40)
Penalty Score: 25/100 (weight: 50)

Step 1: Start with base
  final = 82

Step 2: Add bonus (base < 100)
  bonus_to_add = (90/100) × 40 = 36
  final = 82 + 36 = 118
  
Step 3: Cap at 100
  final = 100

Step 4: Subtract penalty
  penalty_to_subtract = (25/100) × 50 = 12.5
  final = 100 - 12.5 = 87.5

Final Score: 87.5/100
```

---

## Complete Grading Process Example

Let's trace a complete grading session with a concrete example:

### Input: Criteria Tree

```
Root
├── Base (100 points)
│   ├── HTML (60% weight)
│   │   ├── Structure (40% of HTML)
│   │   │   ├── has_tag("body", 1)
│   │   │   ├── has_tag("header", 1)
│   │   │   └── has_tag("article", 4)
│   │   └── Links (60% of HTML)
│   │       └── check_css_linked()
│   └── CSS (40% weight)
│       └── uses_relative_units()
├── Bonus (40 points max)
│   └── Accessibility (100% weight)
│       └── check_all_images_have_alt()
└── Penalty (50 points max)
    └── Forbidden (100% weight)
        └── has_forbidden_tag("script")
```

### Execution: Tree Traversal

#### Step 1: Grade Base Category

**Traverse to HTML → Structure (leaf)**
- Execute `has_tag("body", 1)` → 100/100 ✓
- Execute `has_tag("header", 1)` → 100/100 ✓
- Execute `has_tag("article", 4)` → 50/100 (only 2 found) ✗
- **Structure average**: (100 + 100 + 50) / 3 = 83.33

**Traverse to HTML → Links (leaf)**
- Execute `check_css_linked()` → 100/100 ✓
- **Links average**: 100.0

**Aggregate HTML subject**:
- Structure weighted: 83.33 × 0.4 = 33.33
- Links weighted: 100.0 × 0.6 = 60.0
- **HTML total**: 33.33 + 60.0 = 93.33

**Traverse to CSS (leaf)**
- Execute `uses_relative_units()` → 80/100 ⚠
- **CSS average**: 80.0

**Aggregate Base category**:
- HTML weighted: 93.33 × 0.6 = 56.0
- CSS weighted: 80.0 × 0.4 = 32.0
- **Base score**: 56.0 + 32.0 = 88.0

#### Step 2: Grade Bonus Category

**Traverse to Accessibility (leaf)**
- Execute `check_all_images_have_alt()` → 100/100 ✓
- **Accessibility average**: 100.0

**Aggregate Bonus category**:
- **Bonus score**: 100.0

#### Step 3: Grade Penalty Category

**Traverse to Forbidden (leaf)**
- Execute `has_forbidden_tag("script")` → 0/100 (script found!) ✗
- **Forbidden average**: 0.0 (penalty incurred: 100)

**Aggregate Penalty category**:
- **Penalty score**: 100.0 (full penalty)

#### Step 4: Calculate Final Score

```
final_score = 88.0 (base)

Since 88.0 < 100:
  bonus_to_add = (100.0 / 100) × 40 = 40
  final_score = 88.0 + 40 = 128

Cap at 100:
  final_score = 100

Subtract penalty:
  penalty_to_subtract = (100.0 / 100) × 50 = 50
  final_score = 100 - 50 = 50.0

FINAL SCORE: 50/100
```

### Output: Test Results

The grading process produces three lists of `TestResult` objects:

```python
base_results = [
    TestResult("has_tag", 100, "✓ Found 1 <body> tag", "html_structure"),
    TestResult("has_tag", 100, "✓ Found 1 <header> tag", "html_structure"),
    TestResult("has_tag", 50, "✗ Found only 2/4 <article> tags", "html_structure"),
    TestResult("check_css_linked", 100, "✓ CSS file is linked", "html_links"),
    TestResult("uses_relative_units", 80, "⚠ Using some fixed units", "css"),
]

bonus_results = [
    TestResult("check_all_images_have_alt", 100, "✓ All images have alt", "accessibility"),
]

penalty_results = [
    TestResult("has_forbidden_tag", 0, "✗ Forbidden <script> tag found", "forbidden"),
]
```

These results are then passed to the **Reporter** component to generate human-readable feedback.

---

## Visualizing the Tree Structure

Here is a diagram illustrating the grading tree:

![Grading Artifacts Tree](/docs/imgs/tree_structure.png)

---

## Key Advantages of This Approach

### 1. **Flexibility**
The tree structure allows arbitrary nesting of subjects, making it easy to represent complex grading schemes.

### 2. **Weighted Scoring**
Weights can be assigned at any level, and scores automatically cascade up through the tree.

### 3. **Clear Organization**
Tests are logically grouped into subjects and categories, making configurations easy to understand and maintain.

### 4. **Reusability**
The same tree structure works for any assignment type, from web development to essays to APIs.

### 5. **Transparency**
The hierarchical structure makes it clear how the final score is calculated and which tests contribute how much.

### 6. **Extensibility**
New subjects and tests can be added without changing the core algorithm.

---

## From Tree to Feedback

After the grading process completes, the lists of `TestResult` objects are passed to the **Reporter** component, which:

1. **Analyzes** the results (passed/failed, scores, messages)
2. **Organizes** them by category and subject
3. **Formats** them according to feedback preferences
4. **Generates** human-readable feedback text

The reporter uses the same tree structure to organize the feedback, ensuring that students see their results in a logical, hierarchical format that mirrors the grading criteria.

---

## Summary

The Criteria Tree is the cornerstone of the autograder:

✅ **Represents** the complete grading configuration  
✅ **Organizes** tests into logical hierarchies  
✅ **Enables** weighted scoring at any level  
✅ **Drives** the recursive grading algorithm  
✅ **Produces** structured test results for feedback  

Understanding how the tree is built, traversed, and aggregated is essential for creating effective and fair autograded assignments.

---

## Related Documentation

- **[Criteria Configuration](./configuration/criteria_config.md)** - Learn how to define criteria.json
- **[System Architecture](./system_architecture.md)** - Understand the complete system design
- **[Templates Guide](./templates/grading_templates.md)** - Use pre-built test collections
- **[Getting Started](./getting_started.md)** - Complete workflow overview
