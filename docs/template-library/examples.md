# Complete Configuration Examples

Ready-to-use grading configurations you can copy and adapt for your assignments.

## Input/Output Examples

### Hello World (Minimal)

The simplest possible configuration — one test, one input, one expected output.

```json
{
  "external_assignment_id": "hello-world-001",
  "template_name": "input_output",
  "languages": ["python"],
  "criteria_config": {
    "base": {
      "tests": [
        {
          "name": "expect_output",
          "parameters": [
            { "name": "inputs", "value": [] },
            { "name": "expected_output", "value": "Hello, World!" },
            { "name": "program_command", "value": "python3 hello.py" }
          ]
        }
      ]
    }
  }
}
```

### Calculator with Edge Cases

Tests arithmetic operations with bonus for advanced features and penalty for forbidden imports.

```json
{
  "external_assignment_id": "calculator-001",
  "template_name": "input_output",
  "languages": ["python", "java"],
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "Basic Operations",
          "weight": 60,
          "tests": [
            {
              "name": "expect_output",
              "parameters": [
                { "name": "inputs", "value": ["add", "5", "3"] },
                { "name": "expected_output", "value": "8" },
                { "name": "program_command", "value": { "python": "python3 calc.py", "java": "javac Calc.java && java Calc" } }
              ],
              "weight": 25
            },
            {
              "name": "expect_output",
              "parameters": [
                { "name": "inputs", "value": ["subtract", "10", "4"] },
                { "name": "expected_output", "value": "6" },
                { "name": "program_command", "value": { "python": "python3 calc.py", "java": "javac Calc.java && java Calc" } }
              ],
              "weight": 25
            },
            {
              "name": "expect_output",
              "parameters": [
                { "name": "inputs", "value": ["multiply", "6", "7"] },
                { "name": "expected_output", "value": "42" },
                { "name": "program_command", "value": { "python": "python3 calc.py", "java": "javac Calc.java && java Calc" } }
              ],
              "weight": 25
            },
            {
              "name": "expect_output",
              "parameters": [
                { "name": "inputs", "value": ["divide", "20", "5"] },
                { "name": "expected_output", "value": "4.0" },
                { "name": "program_command", "value": { "python": "python3 calc.py", "java": "javac Calc.java && java Calc" } }
              ],
              "weight": 25
            }
          ]
        },
        {
          "subject_name": "Error Handling",
          "weight": 40,
          "tests": [
            {
              "name": "dont_fail",
              "parameters": [
                { "name": "user_input", "value": "invalid" },
                { "name": "program_command", "value": { "python": "python3 calc.py", "java": "javac Calc.java && java Calc" } }
              ],
              "weight": 50
            },
            {
              "name": "dont_fail",
              "parameters": [
                { "name": "user_input", "value": "" },
                { "name": "program_command", "value": { "python": "python3 calc.py", "java": "javac Calc.java && java Calc" } }
              ],
              "weight": 50
            }
          ]
        }
      ]
    },
    "bonus": {
      "weight": 15,
      "tests": [
        {
          "name": "expect_output",
          "parameters": [
            { "name": "inputs", "value": ["power", "2", "8"] },
            { "name": "expected_output", "value": "256" },
            { "name": "program_command", "value": { "python": "python3 calc.py", "java": "javac Calc.java && java Calc" } }
          ]
        }
      ]
    },
    "penalty": {
      "weight": 20,
      "tests": [
        {
          "name": "forbidden_import",
          "parameters": [
            { "name": "forbidden_imports", "value": ["eval", "exec", "os", "subprocess"] }
          ]
        }
      ]
    }
  }
}
```

### File Generator

Tests a program that creates output files.

```json
{
  "external_assignment_id": "file-gen-001",
  "template_name": "input_output",
  "languages": ["python"],
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "File Creation",
          "weight": 60,
          "tests": [
            {
              "name": "expect_file_artifact",
              "parameters": [
                { "name": "program_command", "value": "python3 generate.py" },
                { "name": "inputs", "value": ["Alice", "25"] },
                { "name": "artifact_path", "value": "output/report.txt" },
                { "name": "expected_content", "value": "Name: Alice\nAge: 25" },
                { "name": "match_mode", "value": "exact" }
              ]
            }
          ]
        },
        {
          "subject_name": "CSV Output",
          "weight": 40,
          "tests": [
            {
              "name": "expect_file_artifact",
              "parameters": [
                { "name": "program_command", "value": "python3 generate.py" },
                { "name": "inputs", "value": ["Bob", "30"] },
                { "name": "artifact_path", "value": "output/data.csv" },
                { "name": "expected_content", "value": "name,age" },
                { "name": "match_mode", "value": "contains" }
              ]
            }
          ]
        }
      ]
    }
  }
}
```

---

## Web Development Examples

### Portfolio Page

A personal portfolio with HTML structure, CSS styling, and responsive design.

```json
{
  "external_assignment_id": "portfolio-001",
  "template_name": "webdev",
  "languages": ["python"],
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "Project Files",
          "weight": 10,
          "tests": [
            {
              "name": "check_project_structure",
              "parameters": [{ "name": "expected_structure", "value": "index.html" }],
              "weight": 50
            },
            {
              "name": "check_dir_exists",
              "parameters": [{ "name": "dir_path", "value": "css" }],
              "weight": 50
            }
          ]
        },
        {
          "subject_name": "HTML Structure",
          "weight": 35,
          "tests": [
            {
              "name": "has_tag",
              "file": "index.html",
              "parameters": [{ "name": "tag", "value": "header" }, { "name": "required_count", "value": 1 }],
              "weight": 15
            },
            {
              "name": "has_tag",
              "file": "index.html",
              "parameters": [{ "name": "tag", "value": "section" }, { "name": "required_count", "value": 3 }],
              "weight": 20
            },
            {
              "name": "has_tag",
              "file": "index.html",
              "parameters": [{ "name": "tag", "value": "footer" }, { "name": "required_count", "value": 1 }],
              "weight": 15
            },
            {
              "name": "check_internal_links",
              "file": "index.html",
              "parameters": [{ "name": "required_count", "value": 3 }],
              "weight": 20
            },
            {
              "name": "uses_semantic_tags",
              "file": "index.html",
              "weight": 15
            },
            {
              "name": "check_head_details",
              "file": "index.html",
              "parameters": [{ "name": "detail_tag", "value": "title" }],
              "weight": 15
            }
          ]
        },
        {
          "subject_name": "CSS Styling",
          "weight": 35,
          "tests": [
            {
              "name": "check_css_linked",
              "file": "index.html",
              "weight": 15
            },
            {
              "name": "check_flexbox_usage",
              "file": "css/styles.css",
              "weight": 25
            },
            {
              "name": "check_media_queries",
              "file": "css/styles.css",
              "weight": 25
            },
            {
              "name": "uses_relative_units",
              "file": "css/styles.css",
              "weight": 20
            },
            {
              "name": "count_unused_css_classes",
              "parameters": [
                { "name": "html_file", "value": "index.html" },
                { "name": "css_file", "value": "css/styles.css" }
              ],
              "weight": 15
            }
          ]
        },
        {
          "subject_name": "Accessibility",
          "weight": 20,
          "tests": [
            {
              "name": "check_all_images_have_alt",
              "file": "index.html",
              "weight": 40
            },
            {
              "name": "check_headings_sequential",
              "file": "index.html",
              "weight": 30
            },
            {
              "name": "check_html_direct_children",
              "file": "index.html",
              "weight": 30
            }
          ]
        }
      ]
    },
    "penalty": {
      "weight": 10,
      "tests": [
        {
          "name": "check_no_inline_styles",
          "file": "index.html"
        }
      ]
    }
  }
}
```

### Bootstrap Grid Assignment

Tests proper use of Bootstrap's grid system and components.

```json
{
  "external_assignment_id": "bootstrap-grid-001",
  "template_name": "webdev",
  "languages": ["python"],
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "Bootstrap Setup",
          "weight": 15,
          "tests": [
            {
              "name": "check_bootstrap_linked",
              "file": "index.html"
            }
          ]
        },
        {
          "subject_name": "Grid System",
          "weight": 45,
          "tests": [
            {
              "name": "has_class",
              "file": "index.html",
              "parameters": [{ "name": "class_names", "value": ["container"] }, { "name": "required_count", "value": 1 }],
              "weight": 25
            },
            {
              "name": "has_class",
              "file": "index.html",
              "parameters": [{ "name": "class_names", "value": ["row"] }, { "name": "required_count", "value": 3 }],
              "weight": 35
            },
            {
              "name": "has_class",
              "file": "index.html",
              "parameters": [{ "name": "class_names", "value": ["col-*"] }, { "name": "required_count", "value": 6 }],
              "weight": 40
            }
          ]
        },
        {
          "subject_name": "Components",
          "weight": 40,
          "tests": [
            {
              "name": "has_class",
              "file": "index.html",
              "parameters": [{ "name": "class_names", "value": ["navbar"] }, { "name": "required_count", "value": 1 }],
              "weight": 25
            },
            {
              "name": "has_class",
              "file": "index.html",
              "parameters": [{ "name": "class_names", "value": ["card"] }, { "name": "required_count", "value": 3 }],
              "weight": 25
            },
            {
              "name": "has_class",
              "file": "index.html",
              "parameters": [{ "name": "class_names", "value": ["btn"] }, { "name": "required_count", "value": 2 }],
              "weight": 25
            },
            {
              "name": "has_class",
              "file": "index.html",
              "parameters": [{ "name": "class_names", "value": ["form-control"] }, { "name": "required_count", "value": 1 }],
              "weight": 25
            }
          ]
        }
      ]
    }
  }
}
```

### Interactive JS Page

Tests JavaScript DOM manipulation and query string handling.

```json
{
  "external_assignment_id": "interactive-js-001",
  "template_name": "webdev",
  "languages": ["python"],
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "HTML Structure",
          "weight": 25,
          "tests": [
            {
              "name": "has_tag",
              "file": "index.html",
              "parameters": [{ "name": "tag", "value": "main" }, { "name": "required_count", "value": 1 }],
              "weight": 50
            },
            {
              "name": "check_css_linked",
              "file": "index.html",
              "weight": 50
            }
          ]
        },
        {
          "subject_name": "JavaScript",
          "weight": 50,
          "tests": [
            {
              "name": "js_uses_feature",
              "file": "js/app.js",
              "parameters": [{ "name": "feature", "value": "addEventListener" }],
              "weight": 25
            },
            {
              "name": "js_uses_dom_manipulation",
              "file": "js/app.js",
              "parameters": [
                { "name": "methods", "value": ["getElementById", "querySelector", "createElement"] },
                { "name": "required_count", "value": 3 }
              ],
              "weight": 35
            },
            {
              "name": "js_has_json_array_with_id",
              "file": "js/data.js",
              "parameters": [
                { "name": "required_key", "value": "id" },
                { "name": "min_items", "value": 5 }
              ],
              "weight": 25
            },
            {
              "name": "js_uses_query_string_parsing",
              "file": "js/app.js",
              "weight": 15
            }
          ]
        },
        {
          "subject_name": "CSS",
          "weight": 25,
          "tests": [
            {
              "name": "check_flexbox_usage",
              "file": "css/styles.css",
              "weight": 50
            },
            {
              "name": "check_media_queries",
              "file": "css/styles.css",
              "weight": 50
            }
          ]
        }
      ]
    },
    "penalty": {
      "weight": 20,
      "subjects": [
        {
          "subject_name": "Code Quality",
          "weight": 50,
          "tests": [
            {
              "name": "uses_forbidden_method",
              "file": "js/app.js",
              "parameters": [{ "name": "method", "value": "document.write" }],
              "weight": 50
            },
            {
              "name": "count_global_vars",
              "file": "js/app.js",
              "parameters": [{ "name": "max_allowed", "value": 5 }],
              "weight": 50
            }
          ]
        },
        {
          "subject_name": "Best Practices",
          "weight": 50,
          "tests": [
            {
              "name": "has_no_js_framework",
              "parameters": [
                { "name": "html_file", "value": "index.html" },
                { "name": "js_file", "value": "js/app.js" }
              ],
              "weight": 50
            },
            {
              "name": "check_no_inline_styles",
              "file": "index.html",
              "weight": 50
            }
          ]
        }
      ]
    }
  }
}
```

---

## API Testing Examples

### Simple REST API

```json
{
  "external_assignment_id": "rest-api-001",
  "template_name": "api",
  "languages": ["python"],
  "setup_config": {
    "python": {
      "required_files": ["app.py"],
      "setup_commands": [
        "pip install flask",
        "python3 app.py &"
      ]
    }
  },
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "Server Health",
          "weight": 20,
          "tests": [
            {
              "name": "health_check",
              "parameters": [{ "name": "endpoint", "value": "/health" }]
            }
          ]
        },
        {
          "subject_name": "User Endpoints",
          "weight": 80,
          "tests": [
            {
              "name": "check_response_json",
              "parameters": [
                { "name": "endpoint", "value": "/api/users/1" },
                { "name": "expected_key", "value": "id" },
                { "name": "expected_value", "value": 1 }
              ],
              "weight": 50
            },
            {
              "name": "check_response_json",
              "parameters": [
                { "name": "endpoint", "value": "/api/users/1" },
                { "name": "expected_key", "value": "name" },
                { "name": "expected_value", "value": "Alice" }
              ],
              "weight": 50
            }
          ]
        }
      ]
    }
  }
}
```
