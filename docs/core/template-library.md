# Template Library

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
- `static_analysis`

Each key resolves to a template class with:

- `template_name`
- `template_description`
- `requires_sandbox`
- `tests` map of available `TestFunction` objects

## Static Analysis Template (`static_analysis`)

Static analysis runs on submission files without executing code (no sandbox required). It includes both rule-based checks and AI-assisted algorithm validation.

Available tests:

- `forbidden_import` — Parameters: `forbidden_imports` (list of strings). Submission language is runtime context, never an authored parameter.
- `forbidden_keyword` — Parameters: `forbidden_keywords` (list of strings), `custom_ast_grep_rules` (list of rule dicts).
- `ai_sorting_algorithm` — Parameters: `algorithm_name` (string).
- `ai_search_algorithm` — Parameters: `algorithm_name` (string).
- `ai_graph_algorithm` — Parameters: `algorithm_name` (string).

AI algorithm tests require a valid `OPENAI_API_KEY` to be configured in the API environment.

## How it integrates with the pipeline

1. **Compile definition** resolves templates, validates their contracts and binds evaluator identifiers to normalized parameters.
2. **Load Template / Build Tree** attach the compiled instances and tree.
3. **Grade** executes bound tests with parameters from the criteria tree.

This means template validation is front-loaded, not deferred to scoring time.

## Extending templates

To add a built-in template:

1. Implement template and test functions under `autograder/template_library/`.
2. Register it in `TemplateLibraryService._TEMPLATE_REGISTRY`.
3. Supply an annotated parameter signature or `config_schema`; discovery derives JSON Schema from that same contract.

## Trusted Python extensions and discovery

Pass already-instantiated `Template` objects using
`compile_definition(definition, templates={"local": MyTemplate()})` or
`evaluate_submission(submission, definition=definition, templates={"local": MyTemplate()})`.
Compilation calls `validate_contract()` and retains the injected instances when
the compiled definition is passed to evaluation. No registry modification is needed.
The former unimplemented `load_custom_template()` has been removed.

`describe_templates()` and HTTP `GET /api/v1/templates` publish typed evaluator
identifiers, parameter schemas, validated samples, required capabilities and known
language constraints. HTTP and Action JSON resolve built-ins only; uploaded Python
source and plugin loading are unsupported. See the [catalog and Python contract](../contracts/CATALOG.md)
for migration, deployment limits and the runnable offline example.

## Common mistakes

- Reusing test names with different semantics across templates
- Skipping documentation for template parameters
- Assuming sandbox availability in templates that declare `requires_sandbox = False`

## Continue reading

- [Pipeline Step: Load Template](../pipeline/01-load-template.md)
- [Input/Output Template](../template-library/input_output.md)
- [API Testing Template](../template-library/api_testing.md)
- [Web Development Template](../template-library/web_dev.md)
- [Static Analysis Template](../template-library/static_analysis.md)
