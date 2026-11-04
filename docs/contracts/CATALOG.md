# Template catalog and Python facade (INT-11)

This implements #373 using the normalized definition from INT-05 (#367) and
the terminal outcome contract. Registry resolution and parameter validation stay
in `compile_definition`; discovery reads the same trusted evaluator instances.

## Supported surface

```python
from autograder import compile_definition, describe_templates, evaluate_submission

catalog = describe_templates()
compiled = compile_definition(definition_json, templates={"local": template_instance})
outcome = evaluate_submission(submission, definition=compiled)
terminal_json = outcome.model_dump(mode="json")
```

`compile_definition` validates and normalizes without provisioning resources.
`evaluate_submission` accepts raw, validated or compiled definitions, optional
trusted `templates` and optional `provenance`; it uses the submission's locale,
finalizes cleanup and returns only the immutable terminal outcome. Invalid
definitions raise `DefinitionValidationError`; execution failures return a failed
outcome with null score/tree. `build_pipeline` remains available for existing
callers. Pipeline classes, steps, registry and mutable execution state are internal,
not a compatibility promise. Everything an evaluator author needs is importable
from `autograder`: `Template`, `TestFunction`, `AiTestFunction`, `EvaluationInput`,
`ParameterIssue`, `TestResult`, `Submission`, `SubmissionFile`, `EvaluationError`,
`ProcessRequest`, `ProcessResult`, `ProcessStatus`, `lines_to_stdin`,
`split_command` and `BaseExecutionTest` (ONB-08). The examples import nothing
else from the engine, which `tests/unit/test_architecture.py` enforces.

Injected values must be `Template(name, description, evaluators)` instances;
each evaluator is registered under its own `name`. Compilation calls
`validate_contract()`, rejects duplicate identifiers and validates parameters.
Injected identifiers override built-ins only for that call; they do not mutate
the global library. Passing a `CompiledDefinition` reuses it unchanged, with its
instances; adding `templates` revalidates its canonical snapshot without normalizing again.
Python code is trusted and runs in process. HTTP and Action JSON contain only
identifier lists; neither transport accepts source code, module paths or plugins.

The executable offline example is
[`examples/contracts/custom_evaluator.py`](https://github.com/webtech-network/autograder/blob/main/examples/contracts/custom_evaluator.py):

```sh
python -m examples.contracts.custom_evaluator
```

It compiles a local `contains_text` evaluator (implementation, `Annotated`
contract and registration only), infers the single language, and
returns a completed score of 100 for `<h1>Hello</h1>`. No Docker, credentials or
network are needed. Missing text is an assessed zero, not an infrastructure failure.
`python -m examples.contracts.execution_evaluator` shows an evaluator built on
`BaseExecutionTest` (which declares `sandbox_execution`) running the program
through a fake session. Both follow
[Adding an evaluator](../architecture/extending.md).

## Catalog wire contract

`GET /api/v1/templates` returns `TemplateCatalog`: `templates` plus a
`capabilities` map explaining resource requirements and deployment limitations.
`GET /api/v1/templates/{template_name}` returns `TemplateDescription`. Both have
explicit OpenAPI response models. An unknown identifier returns 404; a host whose
catalog service is not initialized returns 503. Discovery never probes Docker,
network access or credentials and is not an availability/health endpoint.

| Model | Fields |
| --- | --- |
| TemplateDescription | `identifier`, display `name`, `description`, `evaluators` |
| EvaluatorDescription | `identifier`, `description`, `parameters_schema`, `sample_parameters`, `required_capabilities`, `supported_languages`, `absence_check` |

`identifier` is the actual registry key accepted as a template or criterion `type`.
`parameters_schema` is generated from the evaluator's `config_schema` (explicit
or derived from the annotated keyword-only parameters of `execute`/`build_prompt`),
including each field's `description`, with unknown top-level parameters forbidden exactly as
in compilation. Samples include normalized defaults and must validate through
that same contract. Simple required values are generated from the schema;
evaluators with domain-specific constraints provide `example_parameters` on their
implementation. Invalid samples fail discovery rather than publishing misleading
examples. Samples illustrate valid parameters, not runnable student programs.

`required_capabilities` contains `sandbox_execution`, `http_network`, `ai_provider`
or `structural_analysis`, exactly as the evaluator implementation declares them;
runtime acquisition reads the same declaration. A template adds nothing, so a
static evaluator in an execution template requires nothing and acquires no
session. API evaluators declare `http_network` alone: the assessed-server session
it implies is the execution session for that run. `supported_languages`
contains known canonical language constraints (`python`, `java`, `node`, `cpp`,
`c`), derived from the static evaluators' language maps. Null means no declared
evaluator-specific restriction; it does not promise host execution support.
There is no duplicate evaluator prose or parameter-schema registry.

`absence_check` is the evaluator's `absence_check` attribute: for a prohibition
or limit check (`has_forbidden_tag`, `forbidden_import`, `count_global_vars`, ...)
it says why the evaluator passes when what it looks for is absent. It is null
for presence checks, which cannot pass an irrelevant submission with only their
required parameters (see [DEFINITIONS.md](DEFINITIONS.md)).

The finite built-in catalog is returned in full; there is no pagination or
user-uploaded catalog storage. Python discovery may merge trusted local instances
using `describe_templates(templates={...})`. Custom examples remain author-owned;
compilation is authoritative for cross-field and language-specific checks.

## Deployment and migration

ONB-08 removes the template-level `requires_sandbox` flag. The catalog wire
models drop `TemplateDescription.requires_sandbox` and
`EvaluatorDescription.requires_sandbox` (removed, not deprecated: the field
duplicated, and for mixed templates contradicted, `required_capabilities`).
Clients that read it use `"sandbox_execution" in required_capabilities` (or
`http_network` for API evaluators). `health_check` and `check_response_json`
now report `["http_network"]` instead of `["http_network", "sandbox_execution"]`.
Trusted Python callers build templates as `Template(name, description,
[evaluator, ...])` instead of subclassing with `tests`, `template_name`,
`template_description` and `requires_sandbox`, and import authoring types from
`autograder`. `TemplateLibraryService` is replaced by the read-only
`autograder.template_library.BUILTIN_TEMPLATES` mapping; the package no longer
re-exports template classes. Definitions, stored snapshots and their hashes are
unchanged, so no database migration is needed.

Static checks need no sandbox or AI setup. Execution still uses the configured
host's sandbox manager and supported language pools. API evaluators need an HTTP
port mapping, which the current local pool does not expose. AI evaluators need
a host-supplied assessment provider; structural rules need `ast-grep-py`. Missing
resources fail execution rather than becoming student zeroes. Requirements for
unused evaluators do not cause sandbox or AI provisioning for a static assignment.

The catalog response removes the redundant `available_tests` list. Consumers use
`evaluators[].identifier`; language constraints are per evaluator. Python callers
of the internal library's metadata methods now receive Pydantic models; serialize
with `model_dump(mode="json")`. The checked-in OpenAPI snapshot includes the new
models. Deploy catalog clients and server together if a client required the old
field. No database migration or definition schema-version change is needed.

Remove calls to the never-implemented `load_custom_template()` and pass instances
through `templates={...}` instead. All public definitions use `templates: [id]`;
comma-separated strings and plugin/source objects are rejected. The internal load
step now attaches compiled instances and performs no second registry resolution.

## File selection and host composition

The unused `required_file` and `required_file_type` properties have been removed.
See [evaluator file selection](FILES.md) for explicit targets, source types,
zero/one/many requirements and context. These declarations control assessment
input and are separate from execution capability requirements.

Trusted Python callers pass `capabilities=HostCapabilities(...)` to
`build_pipeline` or `evaluate_submission`. The core does not construct providers,
read credentials or choose an AI model. HTTP and Actions compose their concrete
services outside the core. See [host capabilities](CAPABILITIES.md) for typed
preparation, ownership, cleanup and missing-capability behavior.

These changes complete the overlapping file/capability work tracked by #228 and
#376 without claiming that the broader #363 investigation or other phase work is
complete. Transport/storage validation is documented in [submission input](SUBMISSIONS.md).
