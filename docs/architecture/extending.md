# Adding an evaluator

This is the one extension recipe. A new evaluator changes only four things: its
implementation, its parameter contract, its registration in a trusted template
and its tests. It needs no step enum, no generic dispatch change, no host change
and no Docker. Where the parts fit is shown in the
[responsibility map](overview.md).

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

## 3. Register it

Put the instance in a trusted `Template`'s `tests` dict under its `name`, then
pass the template to `compile_definition`, `build_pipeline` or
`evaluate_submission` with `templates={identifier: instance}`. Built-in
evaluators are registered the same way in
`autograder/services/template_library_service.py`. Uploaded code is not
supported. Reference the evaluator as a criterion `type`, with a distinct `id`.

## 4. Test it

Test the evaluator by calling `execute` with an explicit `EvaluationInput`, and
test the registration by compiling and grading a definition, as the examples'
tests do. For built-in evaluators, `tests/unit/test_catalog.py` already checks
that discovery and compilation agree; nothing else needs registering.

## Evaluators that run code

The only difference is a declaration. An evaluator with
`required_capabilities = ("sandbox_execution",)` makes the run acquire one
execution session for the bound language, stage the files and preparation, and
pass it as `evaluation.session`; other evaluators receive `None`. Run every
process through `session.run_process(ProcessRequest...)` (explicit argv or an
explicit shell, exact stdin, a deadline) and grade the returned
`ProcessResult`. A program that exits non-zero or times out is an assessed
result; `not_started` and session exceptions are infrastructure failures. See
[PROCESSES.md](../contracts/PROCESSES.md).

`examples/contracts/execution_evaluator.py` teaches this with `FakeSession`, a
few lines implementing the `ExecutionSession` protocol that answer every process
with a scripted `ProcessResult`. Its tests check the exact argv and stdin, that
the run closes the session once, the assessed-zero versus infrastructure-failure
split, and that a host without the capability fails before acquisition.

### Host composition

Evaluator code never chooses a host. Hosts pass `HostCapabilities` whose
`execution` is a callable from `Language` to an owned session:

```python
from execution_host.docker import DockerHost

host = DockerHost(mode="local")          # or DockerHost.from_environment()
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
