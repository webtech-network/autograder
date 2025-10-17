# Criteria Configuration

## Overview

The **criteria.json** file is the most complex and important configuration file in the autograder. It represents the complete grading guidelines for an assignment and defines how the final score should be calculated.

This file is transformed into a **criteria tree data structure** during the grading process, so it's essential to understand and visualize it as a tree.

---

## The Criteria Tree Structure

### Root Node: Final Score (100)

The root of the tree represents the final score, which starts at 100 points. This root has three main category branches:

#### 1. **Base Category** (Sum: 0-100 points)
- Contains the **standard requirements** for the assignment
- Tests here represent the basic, essential elements
- **Executed first** in the grading process
- Should add up to 100% when all subjects are considered

#### 2. **Bonus Category** (Sum: 0-100 points, configurable)
- Contains **non-essential but positive elements**
- Tests for features that go beyond basic requirements
- Bonus points are **only added if the base score is below 100**
- Rewards students for extra effort or advanced implementations

#### 3. **Penalty Category** (Sum: 0-100 points, configurable)
- Contains **forbidden or discouraged elements**
- Tests for things that should NOT be present
- Points are **subtracted from the final score** if violations are found
- Enforces best practices and assignment constraints

---

## Scoring Algorithm

The final score is calculated using this process:

```
final_score = 0

# Step 1: Add base score
final_score += base_score

# Step 2: Add bonus (only if below 100)
if final_score < 100:
    bonus_to_add = min(bonus_score, 100 - final_score)
    final_score += bonus_to_add

# Step 3: Subtract penalties
final_score -= penalty_score

# Ensure score stays within bounds
final_score = max(0, min(100, final_score))
```

---

## Subjects: Organizing Tests into Groups

Within each category (base, bonus, penalty), you can create **subject groups** to organize and weight your tests.

### What are Subjects?

- **Subject groups** represent score divisions within a category
- Allow you to assign different importance levels to different test groups
- Can be **nested** to create hierarchical structures
- Each subject must have a **weight** assigned (percentage of parent's max score)

### Subject Weights

All subject weights represent **percentages** of their parent level's maximum score.

**Example:**
```
Base Category (100 points)
├── Subject X (weight: 50%) = 50 points max
│   └── Subject Y (weight: 50%) = 25 points max (50% of 50)
│       └── Test Z = 25 points max
```

If Subject Y contains only one test, that test would be worth:
- 50% (Subject Y) of 50% (Subject X) of 100 (Base) = **25 points**

---

## The Golden Rule: Tests vs. Subjects

**Important Constraint:**

> **You can only have subjects within a subject if that parent subject has NO tests directly assigned to it.**

### Why?

Tests represent **leaf nodes** (the end of a branch). Once you reach a test, no further branching is allowed.

```
✅ VALID:
Subject A (no tests)
├── Subject B (no tests)
│   └── Test 1
│   └── Test 2
└── Subject C (no tests)
    └── Test 3

❌ INVALID:
Subject A
├── Test 1  ← Has a test
└── Subject B  ← Cannot have sub-subject after test
    └── Test 2
```

---

## Leaf Nodes: The Tests

Tests are the **most important part** of the criteria tree. They represent the actual checks to be executed.

### Test Structure

Each test leaf contains:

1. **Test Name**: The function to be called
2. **Test File**: Where the test implementation exists (inferred from template)
3. **Test Parameters**: Arguments passed to each test call
4. **Expected Count**: How many occurrences should be found (for certain tests)

### Test Definition Formats

Tests can be defined in two ways:

#### Simple Format (No Parameters)
```json
"tests": [
  "test_function_name"
]
```

#### Parameterized Format
```json
"tests": [
  {
    "test_function_name": [
      ["param1", count1],
      ["param2", count2]
    ]
  }
]
```

---

## Complete Example

Here's a real-world example for a web development assignment:

```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "html": {
        "weight": 60,
        "subjects": {
          "structure": {
            "weight": 40,
            "tests": [
              {
                "has_tag": [
                  ["body", 1],
                  ["header", 1],
                  ["nav", 1],
                  ["main", 1],
                  ["article", 4],
                  ["img", 5],
                  ["footer", 1],
                  ["div", 1],
                  ["form", 1],
                  ["input", 1],
                  ["button", 1]
                ]
              },
              {
                "has_attribute": [
                  ["class", 2]
                ]
              }
            ]
          },
          "link": {
            "weight": 20,
            "tests": [
              "check_css_linked",
              {
                "check_internal_links_to_articles": [[4]]
              }
            ]
          }
        }
      },
      "css": {
        "weight": 40,
        "subjects": {
          "responsivity": {
            "weight": 50,
            "tests": [
              "uses_relative_units",
              "check_media_queries",
              "check_flexbox_usage"
            ]
          },
          "style": {
            "weight": 50,
            "tests": [
              {
                "has_style": [
                  ["font-size", 1],
                  ["font-family", 1],
                  ["text-align", 1],
                  ["display", 1],
                  ["position", 1],
                  ["margin", 1],
                  ["padding", 1]
                ]
              }
            ]
          }
        }
      }
    }
  },
  "bonus": {
    "weight": 40,
    "subjects": {
      "accessibility": {
        "weight": 20,
        "tests": [
          "check_all_images_have_alt"
        ]
      },
      "head_detail": {
        "weight": 80,
        "tests": [
          {
            "check_head_details": [
              ["title"],
              ["meta"]
            ]
          },
          {
            "check_attribute_and_value": [
              ["meta", "charset", "UTF-8"],
              ["meta", "name", "viewport"],
              ["meta", "name", "description"],
              ["meta", "name", "author"],
              ["meta", "name", "keywords"]
            ]
          }
        ]
      }
    }
  },
  "penalty": {
    "weight": 50,
    "subjects": {
      "html": {
        "weight": 50,
        "tests": [
          "check_bootstrap_usage",
          {
            "check_id_selector_over_usage": [[2]]
          },
          {
            "has_forbidden_tag": [["script"]]
          },
          "check_html_direct_children",
          {
            "check_tag_not_inside": [
              ["header", "main"],
              ["footer", "main"]
            ]
          }
        ]
      },
      "project_structure": {
        "weight": 50,
        "tests": [
          {
            "check_dir_exists": [
              ["css"],
              ["imgs"]
            ]
          },
          {
            "check_project_structure": [
              ["css/styles.css"]
            ]
          }
        ]
      }
    }
  }
}
```

---

## Tree Visualization

For the example above, here's how the tree structure looks:

```
Root (100 points)
├── Base (100 points)
│   ├── HTML (60 points)
│   │   ├── Structure (24 points = 40% of 60)
│   │   │   ├── has_tag tests
│   │   │   └── has_attribute tests
│   │   └── Link (12 points = 20% of 60)
│   │       ├── check_css_linked
│   │       └── check_internal_links_to_articles
│   └── CSS (40 points)
│       ├── Responsivity (20 points = 50% of 40)
│       │   ├── uses_relative_units
│       │   ├── check_media_queries
│       │   └── check_flexbox_usage
│       └── Style (20 points = 50% of 40)
│           └── has_style tests
│
├── Bonus (up to 40 points)
│   ├── Accessibility (8 points = 20% of 40)
│   │   └── check_all_images_have_alt
│   └── Head Detail (32 points = 80% of 40)
│       ├── check_head_details
│       └── check_attribute_and_value
│
└── Penalty (up to 50 points deducted)
    ├── HTML (25 points = 50% of 50)
    │   ├── check_bootstrap_usage
    │   ├── check_id_selector_over_usage
    │   ├── has_forbidden_tag
    │   ├── check_html_direct_children
    │   └── check_tag_not_inside
    └── Project Structure (25 points = 50% of 50)
        ├── check_dir_exists
        └── check_project_structure
```

---

## Best Practices

### 1. **Balance Your Weights**
- Ensure all sibling subjects' weights add up logically
- Consider what aspects of the assignment are most important

### 2. **Use Meaningful Subject Names**
- Choose clear, descriptive names for subjects
- Group related tests together

### 3. **Don't Over-Penalize**
- Penalty weight should be reasonable (typically 30-50% max)
- Avoid making it impossible to pass with minor violations

### 4. **Start with Base**
- Focus on essential requirements in the base category
- Move optional/advanced features to bonus

### 5. **Test Granularity**
- Break complex requirements into multiple tests
- Each test should check one specific thing
- Use parameters to check multiple instances of the same requirement

### 6. **Document Your Tests**
- Keep track of what each test function does
- Ensure test names are self-explanatory

---

## Common Patterns

### Pattern 1: Multiple Instances
Check for multiple occurrences of an element:
```json
{
  "has_tag": [
    ["article", 4],  // Must have 4 articles
    ["img", 5]       // Must have 5 images
  ]
}
```

### Pattern 2: Attribute-Value Pairs
Verify specific attribute values:
```json
{
  "check_attribute_and_value": [
    ["meta", "charset", "UTF-8"],
    ["meta", "name", "viewport"]
  ]
}
```

### Pattern 3: Forbidden Elements
Penalize unwanted features:
```json
{
  "has_forbidden_tag": [["script"]],
  "check_bootstrap_usage": []
}
```

---

## Next Steps

- **[Setup Configuration](./setup_config.md)** - Configure the pre-grading environment
- **[Feedback Configuration](./feedback_config.md)** - Customize student feedback
- **[Templates Guide](../templates/)** - Use pre-built test functions

---

## Summary

The criteria.json file:
- ✅ Defines the complete grading rubric as a tree structure
- ✅ Divides scoring into Base, Bonus, and Penalty categories
- ✅ Uses nested subjects to organize and weight tests
- ✅ Contains leaf nodes (tests) that perform actual checks
- ✅ Drives the entire grading calculation process

Understanding this structure is crucial for creating effective and fair autograded assignments.
