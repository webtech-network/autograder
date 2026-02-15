# Criteria Schema Documentation

## Overview

The criteria schema defines the grading rubric for assignments. It uses a hierarchical structure with categories, subjects, and tests.

## Schema Version: 2.0 (Current)

### Key Changes from Version 1.0

1. **Subjects as Arrays**: Subjects are now arrays with explicit `subject_name` field (instead of dictionaries with implicit names as keys)
2. **Named Parameters**: Test parameters are now named objects `[{"name": "param", "value": "val"}]` (instead of positional arrays)
3. **No Calls Array**: Each test object represents one execution (no `calls` array)
4. **Template Library Field**: Root config includes optional `test_library` field

## Schema Structure

### Root Configuration

```json
{
  "test_library": "web_dev",  // Optional: name of test template to use
  "base": { /* CategoryConfig */ },     // Required: base grading criteria
  "bonus": { /* CategoryConfig */ },    // Optional: bonus points
  "penalty": { /* CategoryConfig */ }   // Optional: penalty points
}
```

### Category Configuration

A category can contain either **subjects** OR **tests** (not both).

```json
{
  "weight": 100,                        // Weight of this category (0-100)
  "subjects": [ /* SubjectConfig[] */ ] // Array of subjects
  // OR
  "tests": [ /* TestConfig[] */ ]      // Array of tests
}
```

### Subject Configuration

A subject can contain either **nested subjects** OR **tests** (not both).

```json
{
  "subject_name": "html_structure",    // Required: name of the subject
  "weight": 40,                         // Weight of this subject (0-100)
  "subjects": [ /* SubjectConfig[] */ ] // Array of nested subjects
  // OR
  "tests": [ /* TestConfig[] */ ]      // Array of tests
}
```

### Test Configuration

```json
{
  "name": "has_tag",                   // Required: test function name
  "file": "index.html",                // Optional: target file
  "parameters": [                      // Optional: named parameters
    {
      "name": "tag",
      "value": "div"
    },
    {
      "name": "required_count",
      "value": 5
    }
  ]
}
```

## Complete Example

```json
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "html",
        "weight": 60,
        "subjects": [
          {
            "subject_name": "structure",
            "weight": 40,
            "tests": [
              {
                "file": "index.html",
                "name": "has_tag",
                "parameters": [
                  {"name": "tag", "value": "body"},
                  {"name": "required_count", "value": 1}
                ]
              },
              {
                "file": "index.html",
                "name": "has_tag",
                "parameters": [
                  {"name": "tag", "value": "header"},
                  {"name": "required_count", "value": 1}
                ]
              }
            ]
          },
          {
            "subject_name": "links",
            "weight": 20,
            "tests": [
              {
                "file": "index.html",
                "name": "check_css_linked"
              }
            ]
          }
        ]
      },
      {
        "subject_name": "css",
        "weight": 40,
        "tests": [
          {
            "file": "style.css",
            "name": "has_style",
            "parameters": [
              {"name": "property", "value": "margin"},
              {"name": "count", "value": 1}
            ]
          }
        ]
      }
    ]
  },
  "bonus": {
    "weight": 20,
    "subjects": [
      {
        "subject_name": "accessibility",
        "weight": 100,
        "tests": [
          {
            "file": "index.html",
            "name": "check_all_images_have_alt"
          }
        ]
      }
    ]
  },
  "penalty": {
    "weight": 30,
    "subjects": [
      {
        "subject_name": "bad_practices",
        "weight": 100,
        "tests": [
          {
            "file": "index.html",
            "name": "has_forbidden_tag",
            "parameters": [
              {"name": "tag", "value": "script"}
            ]
          }
        ]
      }
    ]
  }
}
```

## Validation Rules

### Category Level
- Must have either `subjects` OR `tests` (not both, not neither)
- Weight must be between 0 and 100
- If `subjects` is present, it must be a non-empty array

### Subject Level
- Must have `subject_name` field
- Must have either `subjects` OR `tests` (not both, not neither)
- Weight must be between 0 and 100
- If `subjects` is present, it must be a non-empty array

### Test Level
- Must have `name` field (test function name)
- `file` is optional (some tests don't target specific files)
- `parameters` is optional (empty array or omitted means no parameters)
- Each parameter must have `name` and `value` fields

### Weight Balancing
- Sibling subjects/tests have their weights automatically balanced to sum to 100
- Example: If you have 3 subjects with weights [30, 40, 50], they'll be scaled to [25, 33.33, 41.67]

## Parameter Handling

Parameters are converted from named objects to positional arguments when calling test functions:

```json
"parameters": [
  {"name": "tag", "value": "div"},
  {"name": "required_count", "value": 5}
]
```

Becomes: `test_function.execute("div", 5, files=submission_files)`

The order of parameters in the array determines the order of positional arguments.

## Special File Values

- `"file": "index.html"` - Target specific file
- `"file": "all"` - Pass all submission files to test
- `"file": null` or omitted - No specific file target

## Migration from Schema v1.0

### Old Format (v1.0)
```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "html_structure": {
        "weight": 40,
        "tests": [
          {
            "name": "has_tag",
            "file": "index.html",
            "calls": [
              ["div", 5],
              ["h1", 2]
            ]
          }
        ]
      }
    }
  }
}
```

### New Format (v2.0)
```json
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "html_structure",
        "weight": 40,
        "tests": [
          {
            "name": "has_tag",
            "file": "index.html",
            "parameters": [
              {"name": "tag", "value": "div"},
              {"name": "required_count", "value": 5}
            ]
          },
          {
            "name": "has_tag",
            "file": "index.html",
            "parameters": [
              {"name": "tag", "value": "h1"},
              {"name": "required_count", "value": 2}
            ]
          }
        ]
      }
    ]
  }
}
```

### Key Differences
1. Each test execution is now a separate test object (no `calls` array)
2. Subjects use array format with `subject_name` field
3. Parameters are named objects instead of positional arrays
4. Added optional `test_library` field at root

## Best Practices

1. **Clear Naming**: Use descriptive `subject_name` values
2. **Logical Grouping**: Group related tests under subjects
3. **Weight Distribution**: Assign weights based on importance
4. **Parameter Names**: Use clear parameter names that match test function signatures
5. **File Organization**: Specify file paths relative to submission root

## Pydantic Models

The schema is validated using Pydantic models:

- `CriteriaConfig` - Root configuration
- `CategoryConfig` - Category (base/bonus/penalty)
- `SubjectConfig` - Subject node
- `TestConfig` - Test configuration
- `ParameterConfig` - Named parameter

These models provide:
- Automatic validation
- Type checking
- Helpful error messages
- IDE autocomplete support

