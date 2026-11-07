# Test your rubric

Check a definition before students depend on it, in two steps: validate it,
then grade a good and a bad submission of your own and read what a student
would read. From a checkout of this repository (`uv sync`), one command does
both:

```sh
python -m execution_host.check examples/tutorial/python-io/definition.json \
  --submission examples/tutorial/python-io/good --submission examples/tutorial/python-io/bad
```

The sections below explain each step and the other ways to run it.

## 1. Validate the definition

Validation runs every check grading would, without grading anything: unknown
or misspelled fields, parameters an evaluator does not accept, commands that
use shell syntax, languages a check cannot handle, time limits. Any service
running the autograder answers it (it needs the integration token, like every
configuration call):

```bash
curl -X POST "$AUTOGRADER_URL/api/v1/configs/validate" \
  -H "Authorization: Bearer $AUTOGRADER_INTEGRATION_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @examples/tutorial/python-io/definition.json
```

A valid definition comes back with every default filled in and its
`definition_hash`. Anything wrong is a `422` that names each problem and its
exact place. Writing `input` where `expect_output` expects `inputs`:

<!-- rejected: examples/tutorial/python-io/definition.json -->
```json
{
  "id": "sum-positive",
  "type": "expect_output",
  "name": "Adds two positive numbers",
  "parameters": {"program_command": "python3 main.py", "input": ["2", "3"], "expected_output": "5"}
}
```

is answered with:

<!-- validate-response -->
```json
{
  "detail": [
    {
      "code": "INVALID_DEFINITION",
      "path": ["criteria", "base", "tests", 0, "parameters", "input"],
      "message": "`expect_output` has no parameter `input`; did you mean `inputs`?"
    }
  ]
}
```

The `path` leads from the top of the definition to the field: here, the
first criterion of `base`. Rules that relate several fields point at the field
to change too: a `base` weight other than 100 at `["criteria","base","weight"]`,
preparation for a language the definition does not allow at
`["preparation","languages","java"]`. A misspelled template, evaluator or
parameter names the closest correct one, and an evaluator from a template the
definition does not list names that template. Publishing a definition
(`POST /api/v1/configs`) applies the same checks, so a definition that
validates is one the service accepts.

From a checkout of this repository, the check command gives the same answer
without a service, one line per error at its JSON path:

```sh
python -m execution_host.check examples/tutorial/python-io/definition.json
```

For example ``templates[0]: Unknown template `web_dev`; did you mean `webdev`? [UNKNOWN_TEMPLATE]``.
For a valid definition it also states the sandbox time the definition needs per
language and the most this machine's `sandbox_config.yml` grants.

Python gives the same answer as well:

<!-- runs -->
```python
import json
from pathlib import Path

from autograder import compile_definition

compiled = compile_definition(json.loads(Path("examples/tutorial/python-io/definition.json").read_text()))
print(compiled.definition_hash)
```

`compile_definition` raises `DefinitionValidationError`, whose `errors()` are
the list above.

## 2. Grade your own submissions

Write a solution that should score 100 and one with the mistakes you expect,
grade both and read the reports. Check that:

* the good submission scores 100 and loses nothing to `penalty`;
* each mistake costs what you intended, and nothing else;
* every message tells the student what to fix.

Three to five representative submissions usually show whether the weights
match what you meant ([Scores](scoring.md)).

**With the check command**, give each submission as a directory:

```sh
python -m execution_host.check examples/tutorial/compiled/definition.json --language c \
  --submission examples/tutorial/compiled/good --submission examples/tutorial/compiled/bad
```

Each `--submission` directory (repeatable) is read as the GitHub Action reads a
checkout and graded through the same pipeline; criteria that run code use one
sandbox at a time on your local Docker, as the Action does on its runner. The
command prints every criterion's score and report, then the rendered feedback
(or `Feedback: disabled`). A failed grading prints its code, explanation and,
for a failed setup step, the step's output. `--language` selects the language
when the definition allows several, `--locale` the feedback language, and
`--min-score N` fails a submission that completes below `N`.

| Exit status | Meaning |
| --- | --- |
| `0` | The definition is valid and every submission completed (at or above `--min-score`). |
| `1` | The definition is invalid, or a submission failed to grade or scored below `--min-score`. |
| `2` | The check could not run: a usage error, an unreadable file or directory, or no Docker, runtime image or AI provider for grading. |

To run it on every change to a repository that holds the definition and a
reference solution, use the Action's image and give it the runner's Docker:

```yaml
name: Check definition
on: [pull_request, workflow_dispatch]
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate the definition and grade the reference solution
        run: >
          docker run --rm --volume "$PWD:/work" --workdir /work
          --volume /var/run/docker.sock:/var/run/docker.sock
          --entrypoint python ghcr.io/webtech-network/autograder-action:main
          -m execution_host.check .github/autograder/definition.json
          --submission solution --min-score 100
```

Omit `--submission` (and the Docker socket) to validate only.

**Over HTTP**, create the configuration and submit both versions as in
[Run the HTTP service](../getting-started/first-grading-workflow.md); the
submission's details hold the outcome and report. **With the GitHub Action**,
commit the definition and each version to a test repository with the
[quick start](../github_action/quick-start.md) workflow; the run's artifact
holds them.

A web page needs no sandbox, so a checkout grades it directly:

<!-- runs -->
```python
import json
from pathlib import Path

from autograder import Submission, SubmissionFile, evaluate_submission

folder = Path("examples/tutorial/web-page")
definition = json.loads((folder / "definition.json").read_text())
files = {path.name: SubmissionFile(path.name, path.read_text()) for path in (folder / "bad").iterdir()}
outcome = evaluate_submission(Submission("me", "me", "web-page", files), definition=definition)
assert outcome.score == 23.67
print(outcome.feedback.content)
```

Criteria that run the program need a sandbox: grade those with the check
command, the HTTP service or the Action.

Keep your test submissions next to the definition, as the
[tutorial examples](tutorial.md#what-the-examples-score) do, and grade them again
after every change to the rubric.
