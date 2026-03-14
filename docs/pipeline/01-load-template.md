# Step 1: Load Template

## Purpose

The Load Template step is the entry point of the pipeline. It loads the grading template that defines which test functions are available for the assignment. Without a template, no tests can be matched or executed.

## How It Works

The step uses the `TemplateLibraryService` singleton to load a template by name. There are two paths:

1. **Built-in template** — Loaded from the template registry by identifier (e.g., `"input_output"`, `"web_dev"`, `"api_testing"`).
2. **Custom template** — User-provided template object. This path is planned but not yet implemented; it will require sandboxed loading for security.

The loaded `Template` object is stored in the step result's `data` field, making it available to all subsequent steps.

## Dependencies

None. This is the first step in the pipeline.

## Input

| Source | Data |
|--------|------|
| Constructor | `template_name: str` — identifier of the template to load |
| Constructor | `custom_template` (optional) — user-provided template object |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `Template` | The loaded template instance with all its test functions |
| `status` | `StepStatus.SUCCESS` | On successful load |

## What a Template Contains

A `Template` provides:
- **`template_name`** — Display name (e.g., "Input/Output Testing")
- **`template_description`** — What the template is designed for
- **`requires_sandbox`** — Whether test execution needs an isolated container (e.g., `True` for `input_output`, `False` for `web_dev`)
- **`tests`** — Dictionary of `TestFunction` instances keyed by name
- **`get_test(name)`** — Retrieves a specific test function by name

Available built-in templates:

| Identifier | Name | Requires Sandbox | Use Case |
|------------|------|-----------------|----------|
| `input_output` | Input/Output Testing | Yes | Command-line programs with stdin/stdout |
| `web_dev` | Web Development | No | HTML/CSS/JS file validation |
| `api_testing` | API Testing | Yes | HTTP endpoint validation |

## Failure Scenarios

- Template name not found in the registry → `StepStatus.FAIL` with error message listing available templates.
- Custom template loading attempted → `NotImplementedError` (feature not yet implemented).

## Source

`autograder/steps/load_template_step.py` → `TemplateLoaderStep`

`autograder/services/template_library_service.py` → `TemplateLibraryService`
