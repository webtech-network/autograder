# 🌍 Localization (i18n) System

The Autograder features a robust, multi-language localization system that allows all student-facing feedback, error messages, and test reports to be delivered in the student's preferred language.

## Architecture Overview

The system follows an "English Internals + Structured Locales" strategy:
- **Source Code**: All internal logic, variable names, and developer-facing logs remain in English.
- **Student-Facing Text**: Externalized into centralized JSON catalogs for maximum interoperability with other services.
- **Dynamic Selection**: The language is selected per-submission via the `locale` parameter (e.g., `pt-br`).

## The `t()` Function

The core of the system is the `t(key, locale=..., **kwargs)` function, located in `autograder/translations`.

### Usage Example

```python
from autograder.translations import t

# Basic translation
name = t("web_dev.html.check_head.description", locale="pt-br")

# Translation with variables
report = t(
    "web_dev.html.has_tag.report", 
    locale="en", 
    tag="div", 
    found_count=2, 
    required_count=5
)
```

### Key Features
- **Nested Lookup**: Supports dot-notation (e.g., `a.b.c`) to traverse hierarchical dictionaries.
- **Graceful Fallback**: If a key is missing in the target locale (e.g., `pt-br`), it automatically falls back to the default locale (`en`).
- **Closed Locale Set**: Supported locales are declared once in `autograder/models/locale.py` (`en`, `pt-br`). `Submission`, the HTTP API (422) and the GitHub Action (argument error) accept exactly that set through `parse_locale`, which ignores case and treats `_` like `-` (`pt_BR` → `pt-br`). Anything else is rejected, never replaced by English, and never used to build a file path.
- **Variable Interpolation**: Uses standard Python `.format()` syntax for dynamic values.

---

## Translation Catalogs

Catalogs are JSON files located in `autograder/translations/`. JSON keeps translation keys portable across applications and command-line tools.

### Catalog Structure (Nested)

We use a nested structure to organize strings by domain and feature:

```json
// autograder/translations/en.json
{
    "web_dev": {
        "html": {
            "check_head": {
                "description": "Checks if a tag exists in the <head>.",
                "report": {
                    "found": "Tag <{tag}> found.",
                    "not_found": "Tag <{tag}> not found."
                }
            }
        }
      }
}
```

### Main Categories
1.  **`preflight`**: Errors during environment setup and requirement checks.
2.  **`feedback`**: Report headers, category labels (Essential vs. Bonus), and instructions.
3.  **`ai`**: Prompts used by the `AiExecutor`.
4.  **`web_dev`**: Specialized test strings for the Web Development library.

---

## Adding a New Language

1.  Add the identifier to `Locale` in `autograder/models/locale.py` (e.g., `PT_BR = "pt-br"`).
2.  Create its catalog in `autograder/translations/`, using **snake_case** for the filename (e.g., `pt_br.json`), by copying `en.json`.
3.  Regenerate the wire schemas (`python scripts/generate_contract_schemas.py`). Both hosts accept the new locale from the same declaration; a missing catalog fails at import.

## Best Practices

1.  **Never Hardcode**: Any string that a student will see must use `t()`.
2.  **Use Dot-Notation**: Use descriptive paths that reflect the module structure.
3.  **Keep Parity**: Always ensure that new keys added to `en.json` are also added to local catalogs (e.g., `pt_br.json`) to avoid unexpected fallbacks.
4.  **Leaf Strings**: Ensure the path points to a string, not a sub-dictionary. For example, use `report.found` instead of just `report`.
