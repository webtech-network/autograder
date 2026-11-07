# Adding an evaluator

This is the one extension recipe. A new evaluator changes only four things: its
implementation, its parameter contract, its registration in a trusted template
and its tests. It needs no step enum, no generic dispatch change, no host change
and no Docker. Where the parts fit is shown in the
[responsibility map](overview.md).

Everything an evaluator author uses is imported from `autograder` (the examples
import nothing else from the engine, and `tests/unit/test_architecture.py`
checks it): `TestFunction`, `AiTestFunction`, `EvaluationInput`,
`ParameterIssue`, `TestResult`, `Template`, `EvaluationError`, the process
contract (`ProcessRequest`, `ProcessResult`, `ProcessStatus`, `lines_to_stdin`,
`split_command`) and `BaseExecutionTest`.

## Runnable examples

Both examples run offline from the repository root and are executed by
`tests/unit/test_architecture.py`, which also checks this table against
discovery (`describe_templates`).

| Example | Template | Evaluator | Required capabilities |
| --- | --- | --- | --- |
| `examples/contracts/custom_evaluator.py` | `trusted_text` | `contains_text` | none |
| `examples/contracts/execution_evaluator.py` | `program_checks` | `prints_line` | `sandbox_execution` |

```sh
python -m examples.contracts.custom_evaluator      # static: contains_text(needle)
python -m examples.contracts.execution_evaluator   # runs the program in a fake session
```

`python -m examples.contracts.host_provider` shows the same recipe for an AI
evaluator (`AiTestFunction.build_prompt`) with a host-supplied provider.

## 1. Implement the check

Subclass `TestFunction` and write
`execute(self, evaluation, *, <parameters>) -> TestResult`. `evaluation` is the
typed `EvaluationInput` (`files`, `language`, `locale`, `session`); everything
about one submission arrives in the call, because one instance serves every
submission and thread. Return a finite score in 0–100 for an ordinary
assessment. Raise `EvaluationError` with a fixed, safe message for a provider or
system failure: that fails the run instead of scoring zero.

```python
class ContainsText(TestFunction):
    name = "contains_text"
    description = "Check whether any selected file contains a literal string."

    def execute(self, evaluation: EvaluationInput, *,
                needle: Annotated[str, Field(min_length=1, description="Text to find")]) -> TestResult:
        found = any(needle in file.content for file in evaluation.files)
        return TestResult(self.name, 100 if found else 0, "Found" if found else "Missing")
```

## 2. Declare the parameter contract

The annotated keyword-only parameters of `execute` *are* the contract: they
generate validation, normalization and the published JSON Schema. Put
constraints in `Annotated[..., Field(...)]`; a plain `str` accepts an empty
string. Rules that JSON Schema cannot express (cross-field checks, language
coverage, command quoting) go in the pure `validate_parameters` hook, which runs
at compilation and returns `ParameterIssue`s. File needs are class attributes
(`file_extensions`, `minimum_files`, `uses_context_files`, `accepts_file`); see
[FILES.md](../contracts/FILES.md).

A criterion must not pass a submission just because the author omitted a
parameter: give presence thresholds a default of at least 1 (`ge=1`) and make
lists of things to find or forbid nonempty (`min_length=1`). A prohibition or
limit check, which passes when what it looks for is absent, sets the class
attribute `absence_check` to the reason; the catalog publishes it.

Validate at compilation, not at grading: a value that would only fail when the
evaluator runs (a regular expression, a path, a command) must be rejected by the
contract (`Field(pattern=...)`, a Pydantic validator) or by `validate_parameters`.

## 3. Register it

A template is a named collection of evaluator instances; each is registered
under its own `name`, so identifiers are never restated:

```python
TEMPLATE = Template("Trusted text", "One local, trusted evaluator", [ContainsText()])
```

Pass it to `compile_definition`, `build_pipeline` or `evaluate_submission` with
`templates={identifier: TEMPLATE}`. A template declares no requirements of its
own: capabilities come only from its evaluators. Uploaded code is not
supported. Reference the evaluator as a criterion `type`, with a distinct `id`.

## 4. Test it

Test the evaluator by calling `execute` with an explicit `EvaluationInput`, and
test the registration by compiling and grading a definition, as the examples'
tests do.

## Built-in evaluator checklist

A built-in evaluator is added to its template's evaluator list under
`autograder/template_library/`; a new built-in template is one entry in
`BUILTIN_TEMPLATES` (`autograder/template_library/__init__.py`), the only
registry. These steps are enforced by the named tests, which run with the unit
and web suites; `tests/unit/test_architecture.py` checks that each named test
exists.

| Step | Enforced by |
| --- | --- |
| Register the instance in its template; the template contract and evaluator call shape validate | `tests/unit/test_template_contract.py::test_builtin_templates_validate_contract` |
| The catalog sample validates and compiles for every supported language (add `example_parameters` when constraints need domain knowledge) | `tests/unit/test_catalog.py::test_every_catalog_evaluator_resolves_and_its_sample_compiles` |
| Discovery reports exactly the capabilities the evaluator declares | `tests/unit/test_catalog.py::test_discovery_capabilities_come_only_from_evaluators_including_mixed_templates` |
| Every `t("key")` exists in `autograder/translations/en.json` and `pt_br.json`, with the same placeholders | `tests/unit/test_translations.py::test_all_source_keys_exist`, `tests/unit/test_translations.py::test_placeholders_match` |
| Static evaluators (no `ai_provider`): a passing and a failing case in `tests/builtin_evaluator_cases.py`, recorded in `tests/builtin_evaluator_golden.json` | `tests/unit/test_builtin_evaluator_golden.py::test_golden_cases_cover_every_static_builtin_with_both_outcomes` |
| Regenerate the wire schemas with `python scripts/generate_contract_schemas.py` (the definition schema carries every evaluator's parameters) | `tests/unit/test_config_models.py::test_checked_in_schema_is_current`, `tests/web/test_template_catalog.py::test_openapi_gives_typed_template_and_evaluator_models` |
| Give every parameter an English `description` and regenerate the [evaluator reference](../reference/evaluators.md) with `python scripts/generate_reference.py` (`make contracts` fails on a stale page) | `tests/unit/test_generated_reference.py::test_every_discovery_text_is_a_nonempty_default_locale_description`, `tests/unit/test_generated_reference.py::test_checked_in_reference_matches_the_contracts` |
| The reference's example criterion for the evaluator compiles as written | `tests/unit/test_generated_reference.py::test_generated_criterion_examples_compile_as_written` |

`tests/unit/test_non_vacuous_criteria.py` also checks that, with only its
required parameters, no presence check passes an irrelevant project.

Not enforced, so reviewers check them: execution and API evaluators get a real
Docker case beside `tests/integration/test_builtin_io_evaluators.py` (golden
cases cover static evaluators only); scoring semantics the parameters cannot
state are explained in its `description` (and `absence_check`), which the
[evaluator reference](../reference/evaluators.md) renders; runtime-only failures are moved to compilation
(see step 2).

## Evaluators that run code

The only difference is a declaration on the evaluator. An evaluator with
`required_capabilities = ("sandbox_execution",)` makes the run acquire one
execution session for the bound language, stage the files and preparation, and
pass it as `evaluation.session`; other evaluators, including static ones in the
same template, receive `None`, and a run that selects none of them acquires
nothing. Such an evaluator also declares `process_timeouts`, the deadline of
every process one assessment may run (for example `(30,)`; registration rejects
an execution evaluator without it): the run's execution budget, and so the
sandbox's lifetime, is derived from these declarations
([CAPABILITIES.md](../contracts/CAPABILITIES.md#execution-budget)). Run every
process through `session.run_process(ProcessRequest...)` (explicit argv or an
explicit shell, exact stdin, a deadline within the declared ones) and grade the
returned `ProcessResult`. A program that exits non-zero or times out is an
assessed result; `not_started` and session exceptions are infrastructure
failures. See [PROCESSES.md](../contracts/PROCESSES.md).

Most execution evaluators subclass `BaseExecutionTest`, which declares the
capability and its one 30 s run and supplies the shared steps: `run_program(evaluation,
program_command, inputs)` runs the bound language's command (a string, a
language map or `CMD`, checked at compilation) with exact stdin lines, and
`assessed_failure(result, locale)` returns the assessed zero for a timeout or
nonzero exit. `run_program` itself returns the assessed zero `TestResult` when
the submission exhausted its sandbox or its workspace entry point (`./a.out`)
is missing, and `assessed_failure` passes that through. The built-in I/O evaluators use the same base. It is defined in
`autograder/models/abstract/execution_test.py`, so `import autograder` does not
build the built-in templates. It checks `program_command` at compilation only
when the evaluator takes that parameter.

`examples/contracts/execution_evaluator.py` teaches this with `FakeSession`, a
few lines implementing the `ExecutionSession` protocol that answer every process
with a scripted `ProcessResult`. Its tests check the exact argv and stdin, that
the run closes the session once, the assessed-zero versus infrastructure-failure
split, and that a host without the capability fails before acquisition.

### Host composition

Evaluator code never chooses a host. Hosts pass `HostCapabilities` whose
`execution` is a callable from the bound `Language` and the run's
`ExecutionBudget` to an owned session that lives at least
`budget.session_seconds`, and whose `max_session_seconds` states the longest
session the host grants:

```python
from execution_host.docker import DockerHost

host = DockerHost(mode="local")          # or mode="remote", api_url=<sandbox control API>
try:
    outcome = evaluate_submission(submission, definition=compiled, capabilities=host.capabilities)
finally:
    host.close()
```

The web and Actions hosts already compose this; an evaluator registered in a
template they load runs there unchanged. Images per language come from
`sandbox_config.yml` `runtimes:` ([LANGUAGES.md](../contracts/LANGUAGES.md)), and
sandbox ownership is described in [SANDBOX.md](../contracts/SANDBOX.md). Real
isolation is verified by the Docker integration tests, not by the fake session.

## Do not

- add a pipeline step, registry of steps or diagnostic name for one evaluator;
- read runtime values (`language`, `session`, `files`) from parameters, which
  compilation rejects;
- keep per-submission state on `self`;
- import a host package (`web`, `github_action`, `execution_host`,
  `sandbox_manager`) or an SDK client from the evaluator.
