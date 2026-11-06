# Template Library

## What it is

Templates define the available test functions for a grading context (input/output, API, web development, etc.).

`BUILTIN_TEMPLATES` (`autograder/template_library/__init__.py`) is the only
built-in registry: identifiers mapped to shared template instances, read by
compilation, discovery and the definition JSON Schema.

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

Each key resolves to a `Template(name, description, evaluators)`: a display
name, a description and evaluator instances registered under their own `name`.
Templates declare no requirements; each evaluator declares its own
`required_capabilities`.

Every evaluator of these templates, with its parameters, defaults, constraints,
required capabilities and an example, is listed in the generated
[evaluator reference](../reference/evaluators.md). It is rendered from the same
contracts `compile_definition` validates against, so it cannot disagree with the
compiler; `make contracts` (part of `make verify`) fails when a contract changes
without `python scripts/generate_reference.py`.

## How it integrates with the pipeline

1. **Compile definition** resolves templates, validates their contracts and binds evaluator identifiers to normalized parameters.
2. **Load Template / Build Tree** attach the compiled instances and tree.
3. **Grade** executes bound tests with parameters from the criteria tree.

This means template validation is front-loaded, not deferred to scoring time.

## Extending templates

The one recipe for a new evaluator, with runnable static and execution examples,
is [Adding an evaluator](../architecture/extending.md), including the built-in
checklist. A new built-in template is one entry in `BUILTIN_TEMPLATES`.

## Trusted Python extensions and discovery

Pass already-instantiated `Template` objects using
`compile_definition(definition, templates={"local": template})` or
`evaluate_submission(submission, definition=definition, templates={"local": template})`.
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
- Leaving a parameter without an English `description` (a unit test rejects it; the description is the documentation)
- Using `evaluation.session` in an evaluator that does not declare `sandbox_execution` or `http_network` (it receives `None`)

## Continue reading

- [Evaluator reference](../reference/evaluators.md)
- [Definition reference](../reference/definition.md)
- [Adding an evaluator](../architecture/extending.md)
- [Compile templates](../pipeline/01-load-template.md)
- [Input/Output Template](../template-library/input_output.md)
- [API Testing Template](../template-library/api_testing.md)
- [Web Development Template](../template-library/web_dev.md)
- [Static Analysis Template](../template-library/static_analysis.md)
