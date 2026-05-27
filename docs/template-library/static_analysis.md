# Static Analysis Template (`static_analysis`)

The Static Analysis template provides test functions for evaluating code quality, structure, and faithfulness to specific algorithms without executing the code. It leverages regular expressions, structural analysis (AST), and AI-based verification.

> **Template name for configs:** `static_analysis`  
> **Requires sandbox:** No (currently performed server-side on file contents)  
> **Supported languages:** Python, Java, Node.js, C, C++

---

## Test Functions

### `forbidden_import`

Statically analyzes submission files to check if any forbidden libraries were imported. This is useful for ensuring students implement logic themselves rather than using high-level libraries.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `forbidden_imports` | list[string] | ✓ | List of library/module names whose import is forbidden. |
| `submission_language` | string | ✓ | Submission language (e.g., `python`, `java`). Required to identify correct import patterns. |

**Scoring:** 100 if no forbidden imports are found, 0 if any violation is detected.

**Example:**
```json
{
  "name": "forbidden_import",
  "parameters": {
    "forbidden_imports": ["math", "numpy"],
    "submission_language": "python"
  },
  "weight": 50
}
```

---

### `forbidden_keyword`

Statically analyzes submission files using structural analysis (`ast-grep`) to detect forbidden language constructs. Unlike regex, this is context-aware and won't flag keywords inside comments or strings.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `forbidden_keywords` | list[string] | ✗ | List of predefined constructs to forbid (e.g., `for_loop`, `eval_call`). |
| `custom_ast_grep_rules` | list[dict] | ✗ | List of custom `ast-grep` rules to apply for advanced matching. |

**Supported Predefined Keywords:**

| Language | Supported Keywords |
|----------|--------------------|
| **Python** | `for_loop`, `while_loop`, `eval_call`, `exec_call` |
| **Java** | `for_loop`, `while_loop` |
| **Node.js** | `for_loop`, `while_loop`, `eval_call` |
| **C++ / C** | `for_loop`, `while_loop`, `do_while_loop` |

**Scoring:** 100 if no forbidden constructs are found, 0 otherwise.

**Example:**
```json
{
  "name": "forbidden_keyword",
  "parameters": {
    "forbidden_keywords": ["while_loop"]
  },
  "weight": 50
}
```

---

### `ai_sorting_algorithm` / `ai_search_algorithm` / `ai_graph_algorithm`

Uses AI to verify that the submission correctly implements a specific algorithm (e.g., "Quick Sort", "Dijkstra") and ensures it is not just a wrapper around a built-in library function.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `algorithm_name` | string | ✓ | Specific name of the algorithm to verify. |

**Requires:** A valid `OPENAI_API_KEY` configured in the environment.

**Scoring:** 100 if the AI confirms a faithful implementation, 0 otherwise.

**Example:**
```json
{
  "name": "ai_sorting_algorithm",
  "parameters": {
    "algorithm_name": "Quick Sort"
  },
  "weight": 100
}
```

---

## Usage Example

```json
{
  "external_assignment_id": "sorting-logic-assignment",
  "template_name": "static_analysis",
  "languages": ["python"],
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "Constraints",
          "weight": 40,
          "tests": [
            {
              "name": "forbidden_import",
              "parameters": { "forbidden_imports": ["bisect"], "submission_language": "python" },
              "weight": 50
            },
            {
              "name": "forbidden_keyword",
              "parameters": { "forbidden_keywords": ["for_loop"] },
              "weight": 50
            }
          ]
        },
        {
          "subject_name": "Implementation",
          "weight": 60,
          "tests": [
            {
              "name": "ai_sorting_algorithm",
              "parameters": { "algorithm_name": "Recursive Merge Sort" },
              "weight": 100
            }
          ]
        }
      ]
    }
  }
}
```
