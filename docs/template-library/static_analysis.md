# Static Analysis Template (`static_analysis`)

The Static Analysis template provides test functions for evaluating code quality, structure, and faithfulness to specific algorithms without executing the code. It leverages regular expressions, structural analysis (AST), and AI-based verification.

Parameters, defaults, constraints and capabilities of every evaluator below are in the generated [evaluator reference](../reference/evaluators.md#static_analysis); this page explains what the checks mean.

> **Template name for configs:** `static_analysis`  
> **Requires sandbox:** No (currently performed server-side on file contents)  
> **Supported languages:** Python, Java, Node.js, C, C++

---

## Test Functions

### `forbidden_import`

Statically analyzes submission files to check if any forbidden libraries were imported. This is useful for ensuring students implement logic themselves rather than using high-level libraries.

**Scoring:** 100 if no forbidden imports are found, 0 if any violation is detected.

**Example:**
```json
{
  "id": "forbidden-import",
  "type": "forbidden_import",
  "name": "Forbidden import",
  "parameters": {
    "forbidden_imports": [
      "math",
      "numpy"
    ]
  },
  "weight": 50
}
```

---

### `forbidden_keyword`

Statically analyzes submission files using structural analysis (`ast-grep`) to detect forbidden language constructs. Unlike regex, this is context-aware and won't flag keywords inside comments or strings.

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
  "id": "forbidden-keyword",
  "type": "forbidden_keyword",
  "name": "Forbidden keyword",
  "parameters": {
    "forbidden_keywords": [
      "while_loop"
    ]
  },
  "weight": 50
}
```

---

### `ai_sorting_algorithm` / `ai_search_algorithm` / `ai_graph_algorithm`

Uses AI to verify that the submission correctly implements a specific algorithm (e.g., "Quick Sort", "Dijkstra") and ensures it is not just a wrapper around a built-in library function.

**Requires:** A valid `OPENAI_API_KEY` configured in the environment.

**Scoring:** 100 if the AI confirms a faithful implementation, 0 otherwise.

**Example:**
```json
{
  "id": "ai-sorting-algorithm",
  "type": "ai_sorting_algorithm",
  "name": "Ai sorting algorithm",
  "parameters": {
    "algorithm_name": "Quick Sort"
  },
  "weight": 100
}
```

---

## Usage Example

Complete, schema-checked definitions are [`static-conformance.json`](../contracts/v1/examples/static-conformance.json) and [`static-ai.json`](../contracts/v1/examples/static-ai.json) (AI criteria need a host AI provider). Over HTTP, send the definition as `definition` in the configuration envelope (`POST /api/v1/configs`, see [API.md](../API.md)). A snippet above is one criterion; [DEFINITIONS.md](../contracts/DEFINITIONS.md) describes the whole object.
