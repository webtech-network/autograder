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
- **Locale Normalization**: Common formats like `pt-br` are automatically normalized to `pt_br` to match Python module naming conventions.
- **Variable Interpolation**: Uses standard Python `.format()` syntax for dynamic values.

---

## Translation Catalogs

Catalogs are JSON files located in `autograder/translations/`. Using JSON allows the same translation keys to be shared across a multi-language ecosystem (e.g., Prisma API, Frontend, CLI).

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

1.  Create a new file in `autograder/translations/` named after the ISO 639-1 code + region, using **snake_case** for the filename (e.g., `pt_br.json`).
2.  Define the JSON structure by copying it from `en.json`.
3.  The new language will be automatically available via `t(..., locale="pt-br")`.

## Best Practices

1.  **Never Hardcode**: Any string that a student will see must use `t()`.
2.  **Use Dot-Notation**: Use descriptive paths that reflect the module structure.
3.  **Keep Parity**: Always ensure that new keys added to `en.json` are also added to local catalogs (e.g., `pt_br.json`) to avoid unexpected fallbacks.
4.  **Leaf Strings**: Ensure the path points to a string, not a sub-dictionary. For example, use `report.found` instead of just `report`.
