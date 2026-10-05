# Step 1: Load Template

## Purpose

The Load Template step is the entry point of the pipeline. It loads the grading template that defines which test functions are available for the assignment. Without a template, no tests can be matched or executed.

## How It Works

`compile_definition` has already resolved the canonical built-in identifiers
(`input_output`, `webdev`, `api`, `static_analysis`) or trusted Python instances
supplied through `templates={identifier: instance}`. It validates each template
contract before the pipeline is built. This internal step attaches those same
instances as a list in the result's `data` field. It does not load uploaded code
or resolve the registry a second time.

## Dependencies

Definition compilation. This is the first runtime step in the pipeline.

## Input

| Source | Data |
|--------|------|
| Constructor | `templates: list[Template]` — already compiled trusted instances |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `list[Template]` | The compiled template instances with their evaluators |
| `status` | `StepStatus.SUCCESS` | On successful load |

## What a Template Contains

A `Template` provides:
- **`template_name`** — Display name (e.g., "Input/Output Testing")
- **`template_description`** — What the template is designed for
- **`requires_sandbox`** — Whether test execution needs an isolated container (e.g., `True` for `input_output`, `False` for `webdev`)
- **`tests`** — Dictionary of `TestFunction` instances keyed by name
- **`get_test(name)`** — Retrieves a specific test function by name

Available built-in templates:

| Identifier | Name | Requires Sandbox | Use Case |
|------------|------|-----------------|----------|
| `input_output` | Input/Output Testing | Yes | Command-line programs with stdin/stdout |
| `webdev` | Web Development | No | HTML/CSS/JS file validation |
| `api` | API Testing | Yes | HTTP endpoint validation |
| `static_analysis` | Static Analysis | No | Code-quality checks and AI algorithm validation |

## Failure Scenarios

Unknown identifiers and invalid template contracts raise `DefinitionValidationError`
at compilation, before execution. Python callers use the
[supported facade](../contracts/CATALOG.md); step constructors are internal.

## Source

`autograder/steps/load_template_step.py` → `TemplateLoaderStep`

`autograder/services/template_library_service.py` → `TemplateLibraryService`
