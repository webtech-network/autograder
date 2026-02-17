# Configuration Examples

This document provides comprehensive examples for configuring grading criteria.

## Table of Contents

- [Simple Configurations](#simple-configurations)
- [Hierarchical Rubrics](#hierarchical-rubrics)
- [Input/Output Examples](#inputoutput-examples)
- [Web Development Examples](#web-development-examples)
- [API Testing Examples](#api-testing-examples)
- [Complete Assignment Examples](#complete-assignment-examples)

## Simple Configurations

### Basic Single Test

The simplest possible configuration - one test, full weight.

```json
{
  "test_library": "input_output",
  "base": {
    "tests": [
      {
        "name": "expect_output",
        "parameters": {
          "inputs": ["Alice"],
          "expected_output": "Hello, Alice!",
          "program_command": "python3 greeting.py"
        },
        "weight": 100
      }
    ]
  }
}
```

### Multiple Tests (Equal Weight)

```json
{
  "test_library": "input_output",
  "base": {
    "tests": [
      {
        "name": "expect_output",
        "parameters": {
          "inputs": ["Alice"],
          "expected_output": "Hello, Alice!",
          "program_command": "python3 greeting.py"
        },
        "weight": 50
      },
      {
        "name": "expect_output",
        "parameters": {
          "inputs": ["Bob"],
          "expected_output": "Hello, Bob!",
          "program_command": "python3 greeting.py"
        },
        "weight": 50
      }
    ]
  }
}
```

### With Bonus Points

```json
{
  "test_library": "input_output",
  "base": {
    "tests": [
      {
        "name": "expect_output",
        "parameters": {
          "inputs": [],
          "expected_output": "Hello, World!",
          "program_command": "python3 hello.py"
        }
      }
    ]
  },
  "bonus": {
    "weight": 10,
    "tests": [
      {
        "name": "expect_output",
        "parameters": {
          "inputs": [],
          "expected_output_contains": "with colors",
          "program_command": "python3 hello.py"
        }
      }
    ]
  }
}
```

## Hierarchical Rubrics

### Two-Level Subject Hierarchy

```json
{
  "test_library": "input_output",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "Functionality",
        "weight": 70,
        "tests": [
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["5"],
              "expected_output": "120",
              "program_command": "python3 factorial.py"
            },
            "weight": 50
          },
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["0"],
              "expected_output": "1",
              "program_command": "python3 factorial.py"
            },
            "weight": 50
          }
        ]
      },
      {
        "subject_name": "Code Quality",
        "weight": 30,
        "tests": [
          {
            "name": "check_file_exists",
            "parameters": {
              "filename": "factorial.py"
            }
          }
        ]
      }
    ]
  }
}
```

### Three-Level Nested Hierarchy

```json
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "Structure",
        "weight": 50,
        "subjects": [
          {
            "subject_name": "HTML Tags",
            "weight": 60,
            "tests": [
              {
                "name": "has_tag",
                "parameters": {"tag": "header"},
                "weight": 33
              },
              {
                "name": "has_tag",
                "parameters": {"tag": "main"},
                "weight": 34
              },
              {
                "name": "has_tag",
                "parameters": {"tag": "footer"},
                "weight": 33
              }
            ]
          },
          {
            "subject_name": "Semantic HTML",
            "weight": 40,
            "tests": [
              {
                "name": "has_tag",
                "parameters": {"tag": "nav"}
              }
            ]
          }
        ]
      },
      {
        "subject_name": "Styling",
        "weight": 50,
        "tests": [
          {
            "name": "check_css_property",
            "parameters": {
              "selector": "body",
              "property": "font-family"
            }
          }
        ]
      }
    ]
  }
}
```

## Input/Output Examples

### Command-Line Calculator

```json
{
  "test_library": "input_output",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "Addition",
        "weight": 25,
        "tests": [
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["add", "5", "3"],
              "expected_output": "8",
              "program_command": "python3 calculator.py"
            }
          }
        ]
      },
      {
        "subject_name": "Subtraction",
        "weight": 25,
        "tests": [
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["subtract", "10", "4"],
              "expected_output": "6",
              "program_command": "python3 calculator.py"
            }
          }
        ]
      },
      {
        "subject_name": "Multiplication",
        "weight": 25,
        "tests": [
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["multiply", "6", "7"],
              "expected_output": "42",
              "program_command": "python3 calculator.py"
            }
          }
        ]
      },
      {
        "subject_name": "Division",
        "weight": 25,
        "tests": [
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["divide", "20", "5"],
              "expected_output": "4",
              "program_command": "python3 calculator.py"
            }
          }
        ]
      }
    ]
  },
  "bonus": {
    "weight": 10,
    "tests": [
      {
        "name": "expect_output",
        "parameters": {
          "inputs": ["power", "2", "8"],
          "expected_output": "256",
          "program_command": "python3 calculator.py"
        }
      }
    ]
  }
}
```

### File Processing

```json
{
  "test_library": "input_output",
  "base": {
    "tests": [
      {
        "name": "expect_output",
        "parameters": {
          "inputs": ["data.txt"],
          "expected_output_contains": "Total lines: 10",
          "program_command": "python3 file_reader.py"
        },
        "weight": 50
      },
      {
        "name": "check_exit_code",
        "parameters": {
          "command": "python3 file_reader.py nonexistent.txt",
          "expected_exit_code": 1
        },
        "weight": 50
      }
    ]
  }
}
```

## Web Development Examples

### Landing Page

```json
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "HTML Structure",
        "weight": 40,
        "tests": [
          {
            "name": "has_tag",
            "parameters": {"tag": "header", "required_count": 1},
            "weight": 25
          },
          {
            "name": "has_tag",
            "parameters": {"tag": "nav", "required_count": 1},
            "weight": 25
          },
          {
            "name": "has_tag",
            "parameters": {"tag": "main", "required_count": 1},
            "weight": 25
          },
          {
            "name": "has_tag",
            "parameters": {"tag": "footer", "required_count": 1},
            "weight": 25
          }
        ]
      },
      {
        "subject_name": "CSS Styling",
        "weight": 30,
        "tests": [
          {
            "name": "has_class",
            "parameters": {"class_names": ["container"], "required_count": 1},
            "weight": 50
          },
          {
            "name": "check_css_property",
            "parameters": {
              "selector": "body",
              "property": "background-color"
            },
            "weight": 50
          }
        ]
      },
      {
        "subject_name": "Accessibility",
        "weight": 30,
        "tests": [
          {
            "name": "has_attribute",
            "parameters": {"tag": "img", "attribute": "alt"},
            "weight": 50
          },
          {
            "name": "has_attribute",
            "parameters": {"tag": "button", "attribute": "aria-label"},
            "weight": 50
          }
        ]
      }
    ]
  },
  "bonus": {
    "weight": 10,
    "tests": [
      {
        "name": "check_bootstrap_linked",
        "parameters": {"framework": "bootstrap"}
      }
    ]
  }
}
```

### Responsive Bootstrap Site

```json
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "Bootstrap Integration",
        "weight": 20,
        "tests": [
          {
            "name": "check_bootstrap_linked",
            "parameters": {"framework": "bootstrap"}
          }
        ]
      },
      {
        "subject_name": "Grid System",
        "weight": 40,
        "tests": [
          {
            "name": "has_class",
            "parameters": {
              "class_names": ["container", "container-fluid"],
              "required_count": 1
            },
            "weight": 30
          },
          {
            "name": "has_class",
            "parameters": {
              "class_names": ["row"],
              "required_count": 3
            },
            "weight": 35
          },
          {
            "name": "has_class",
            "parameters": {
              "class_names": ["col-*"],
              "required_count": 6
            },
            "weight": 35
          }
        ]
      },
      {
        "subject_name": "Components",
        "weight": 40,
        "tests": [
          {
            "name": "has_class",
            "parameters": {"class_names": ["navbar"], "required_count": 1},
            "weight": 25
          },
          {
            "name": "has_class",
            "parameters": {"class_names": ["card"], "required_count": 3},
            "weight": 25
          },
          {
            "name": "has_class",
            "parameters": {"class_names": ["btn"], "required_count": 2},
            "weight": 25
          },
          {
            "name": "has_class",
            "parameters": {"class_names": ["form-control"], "required_count": 1},
            "weight": 25
          }
        ]
      }
    ]
  }
}
```

## API Testing Examples

### REST API Endpoints

```json
{
  "test_library": "api_testing",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "Health Check",
        "weight": 10,
        "tests": [
          {
            "name": "health_check",
            "parameters": {"endpoint": "/health"}
          }
        ]
      },
      {
        "subject_name": "GET Endpoints",
        "weight": 40,
        "tests": [
          {
            "name": "check_status_code",
            "parameters": {
              "endpoint": "/api/users",
              "method": "GET",
              "expected_status": 200
            },
            "weight": 50
          },
          {
            "name": "check_response_json",
            "parameters": {
              "endpoint": "/api/users/1",
              "expected_key": "id",
              "expected_value": 1
            },
            "weight": 50
          }
        ]
      },
      {
        "subject_name": "POST Endpoints",
        "weight": 30,
        "tests": [
          {
            "name": "check_status_code",
            "parameters": {
              "endpoint": "/api/users",
              "method": "POST",
              "body": {"name": "John", "email": "john@example.com"},
              "expected_status": 201
            }
          }
        ]
      },
      {
        "subject_name": "Error Handling",
        "weight": 20,
        "tests": [
          {
            "name": "check_status_code",
            "parameters": {
              "endpoint": "/api/users/9999",
              "method": "GET",
              "expected_status": 404
            }
          }
        ]
      }
    ]
  }
}
```

## Complete Assignment Examples

### Python Quiz Game

Complete configuration for a text-based quiz game.

```json
{
  "test_library": "input_output",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "Basic Functionality",
        "weight": 50,
        "tests": [
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["Paris", "Blue", "4"],
              "expected_output_contains": "Score: 3/3",
              "program_command": "python3 quiz.py"
            },
            "weight": 100
          }
        ]
      },
      {
        "subject_name": "Input Validation",
        "weight": 30,
        "tests": [
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["", "", ""],
              "expected_output_contains": "Score: 0/3",
              "program_command": "python3 quiz.py"
            },
            "weight": 50
          },
          {
            "name": "expect_output",
            "parameters": {
              "inputs": ["paris", "BLUE", "Four"],
              "expected_output_contains": "Score:",
              "program_command": "python3 quiz.py"
            },
            "weight": 50
          }
        ]
      },
      {
        "subject_name": "Code Structure",
        "weight": 20,
        "tests": [
          {
            "name": "check_file_exists",
            "parameters": {"filename": "quiz.py"}
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
        "parameters": {
          "inputs": ["Paris", "Blue", "4", "yes", "Rome", "Green"],
          "expected_output_contains": "Continue?",
          "program_command": "python3 quiz.py"
        }
      }
    ]
  },
  "penalty": {
    "weight": -10,
    "tests": [
      {
        "name": "timeout_test",
        "parameters": {
          "command": "python3 quiz.py",
          "timeout_seconds": 5
        }
      }
    ]
  }
}
```

### Full-Stack Todo App

Configuration for testing both frontend and backend.

```json
{
  "test_library": "api_testing",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "API Endpoints",
        "weight": 60,
        "subjects": [
          {
            "subject_name": "Create Todo",
            "weight": 40,
            "tests": [
              {
                "name": "check_status_code",
                "parameters": {
                  "endpoint": "/api/todos",
                  "method": "POST",
                  "body": {"title": "Test Task", "completed": false},
                  "expected_status": 201
                }
              }
            ]
          },
          {
            "subject_name": "List Todos",
            "weight": 30,
            "tests": [
              {
                "name": "check_response_json",
                "parameters": {
                  "endpoint": "/api/todos",
                  "expected_key": "todos"
                }
              }
            ]
          },
          {
            "subject_name": "Update Todo",
            "weight": 30,
            "tests": [
              {
                "name": "check_status_code",
                "parameters": {
                  "endpoint": "/api/todos/1",
                  "method": "PUT",
                  "body": {"completed": true},
                  "expected_status": 200
                }
              }
            ]
          }
        ]
      },
      {
        "subject_name": "Frontend",
        "weight": 40,
        "test_library": "web_dev",
        "tests": [
          {
            "name": "has_tag",
            "parameters": {"tag": "form"},
            "weight": 40
          },
          {
            "name": "has_tag",
            "parameters": {"tag": "ul"},
            "weight": 30
          },
          {
            "name": "has_class",
            "parameters": {"class_names": ["todo-item"]},
            "weight": 30
          }
        ]
      }
    ]
  },
  "bonus": {
    "weight": 10,
    "tests": [
      {
        "name": "check_status_code",
        "parameters": {
          "endpoint": "/api/todos/1",
          "method": "DELETE",
          "expected_status": 204
        }
      }
    ]
  }
}
```

