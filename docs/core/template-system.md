# Template System

## What it is

Templates define the available test functions for a grading context (input/output, API, web development, etc.).

The `TemplateLibraryService` loads and caches template instances from a registry.

## Why it matters

- Keeps grading logic reusable across assignments
- Prevents assignment configs from referencing unknown tests
- Decouples rubric configuration from concrete test implementation

## Built-in template identifiers

Current registry keys:

- `input_output`
- `api`
- `webdev`

Each key resolves to a template class with:

- `template_name`
- `template_description`
- `requires_sandbox`
- `tests` map of available `TestFunction` objects

## How it integrates with the pipeline

1. **Load Template** resolves the chosen template.
2. **Build Tree** validates and binds test names from criteria config to concrete test functions.
3. **Grade** executes bound tests with parameters from the criteria tree.

This means template validation is front-loaded, not deferred to scoring time.

## Extending templates

To add a new template:

1. Implement template and test functions under `autograder/template_library/`.
2. Register it in `TemplateLibraryService._TEMPLATE_REGISTRY`.
3. Add docs for available tests and parameters.

## Current limitation

`load_custom_template()` exists but currently raises `NotImplementedError`. Built-in templates are the supported path today.

## Common mistakes

- Reusing test names with different semantics across templates
- Skipping documentation for template parameters
- Assuming sandbox availability in templates that declare `requires_sandbox = False`

## Continue reading

- [Pipeline Step: Load Template](../pipeline/01-load-template.md)
- [Input/Output Template](../template-library/input_output.md)
- [API Testing Template](../template-library/api_testing.md)
- [Web Development Template](../template-library/web_dev.md)
