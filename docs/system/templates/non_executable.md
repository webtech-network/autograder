## **Non-Executable Template Guide**

This guide provides instructions for configuring assignments that **do not** require executing student code in a sandbox environment. These templates are ideal for assignments involving static files like web development (HTML, CSS, JS) and written essays.

### **Web Dev Template**

The Web Dev template is designed for testing HTML, CSS, and JavaScript projects. Since it analyzes static files, no sandbox configuration is needed.

#### `criteria.json` Configuration

Here is an example of a `criteria.json` file for a Web Dev assignment:

```
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects": {
      "html": {
        "weight": 60,
        "tests": [
          {
            "file": "index.html",
            "name": "has_tag",
            "calls": [
              ["body", 1],
              ["header", 1]
            ]
          }
        ]
      },
      "css": {
        "weight": 40,
        "tests": [
          {
            "file": "style.css",
            "name": "uses_relative_units"
          }
        ]
      }
    }
  }
}

```

#### **Configuration Tips**

* **`file`**: Make sure the `file` path in each test object correctly points to the student's submission file you want to test (e.g., `index.html`, `css/style.css`).

* **`name`**: The `name` of the test must match one of the available test functions in the Web Dev template.

* **`calls`**: The `calls` array contains the arguments for the test function. For example, `["body", 1]` in the `has_tag` test checks if the `<body>` tag appears at least once.

### **Essay Template**

The Essay template uses AI to grade written assignments. Like the Web Dev template, it analyzes a static text file and doesn't require a sandbox.

#### `criteria.json` Configuration

Here is a sample `criteria.json` for an essay assignment:

```
{
  "test_library": "essay",
  "base": {
    "weight": 100,
    "subjects": {
      "foundations": {
        "weight": 60,
        "tests": [
          {
            "file": "essay.txt",
            "name": "thesis_statement"
          },
          {
            "file": "essay.txt",
            "name": "clarity_and_cohesion"
          }
        ]
      },
      "prompt_adherence": {
        "weight": 40,
        "tests": [
          {
            "file": "essay.txt",
            "name": "adherence_to_prompt",
            "calls": [
              [ "Analyze the primary causes of the Industrial Revolution." ]
            ]
          }
        ]
      }
    }
  }
}

```

#### **Configuration Tips**

* **`file`**: Ensure this points to the text file containing the student's essay (e.g., `essay.txt`).

* **`name`**: Use the names of the AI-powered essay tests, such as `thesis_statement`, `grammar_and_spelling`, or `argument_strength`.

* **`calls`**: Some tests, like `adherence_to_prompt`, require you to provide the essay prompt as an argument in the `calls` array.
