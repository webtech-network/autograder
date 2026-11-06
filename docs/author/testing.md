# Test your rubric

Check a definition before students depend on it, in two steps: validate it,
then grade a good and a bad submission of your own and read what a student
would read.

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
      "message": "Extra inputs are not permitted"
    }
  ]
}
```

The `path` leads from the top of the definition to the field: here, the
first criterion of `base`. Publishing a definition (`POST /api/v1/configs`)
applies the same checks, so a definition that validates is one the service
accepts.

From a checkout of this repository, Python gives the same answer without a
service:

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

Criteria that run the program need a sandbox: grade those through the HTTP
service or the Action.

Keep your test submissions next to the definition, as the
[tutorial examples](tutorial.md#what-the-examples-score) do, and grade them again
after every change to the rubric.
