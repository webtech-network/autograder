# Examples

Every example the documentation, the browser demo and the GitHub Action quick
start use lives here, and the test suite compiles every definition in this
directory (`tests/unit/test_shipped_examples.py`).

| Directory | What it holds | Used by |
| --- | --- | --- |
| `tutorial/` | The three tutorial assignments, each a `definition.json` with a `good/` and a `bad/` submission, graded in real sandboxes by `tests/integration/test_tutorial_assignments.py` | [Author tutorial](../docs/author/tutorial.md) |
| `definitions/` | One small definition per kind of assignment (Python and C I/O, several languages, file artifacts, web pages, static and AI checks, nested feedback) and `invalid/` definitions with the exact errors they produce (`invalid/manifest.json`) | [Definitions contract](../docs/contracts/DEFINITIONS.md), [Action quick start](../docs/github_action/quick-start.md), the packaged-Action CI fixtures |
| `assets/` | The calculator definitions and student programs of the browser demo, plus web, API and fixture examples | Browser demo, `assets/curl_examples.sh` |
| `fixtures/` | The teacher data file `assets/fixture_io/` reads, uploaded to the development stack's bucket by its `storage-init` service | [Languages, files and setup](../docs/author/preparation.md#teacher-provided-files) |
| `contracts/` | Runnable trusted-Python examples | [Adding an evaluator](../docs/architecture/extending.md) |
| `demo/` | The browser demo | See below |

## Check an example

Check a definition, then grade a submission with it (code-running criteria use
a sandbox on the local Docker), from the repository root:

```sh
python -m execution_host.check examples/tutorial/python-io/definition.json --submission examples/tutorial/python-io/good
python -m execution_host.check examples/assets/web_dev/definition.json --submission examples/assets/web_dev
```

See [Test your rubric](../docs/author/testing.md).

## Trusted Python examples

Run them offline from the repository root:
`python -m examples.contracts.custom_evaluator` (a static evaluator),
`python -m examples.contracts.execution_evaluator` (an evaluator that runs the
program, taught with a fake execution session),
`python -m examples.contracts.host_provider` (an AI evaluator with a
host-supplied provider) and `python -m examples.contracts.requested_feedback`
(the same grade with feedback disabled and enabled).

## Browser demo

Start the API (`make start-autograder`), then `make examples-demo` and open
`http://localhost:8080/demo/`. Enter the API's address and its integration
token (`AUTOGRADER_INTEGRATION_TOKEN`) on the landing page: creating
configurations, submitting, polling and reading details all require it. The
token stays in the browser's session storage.

`assets/curl_examples.sh validate-io` validates a calculator definition
without saving it; `create-io` and `create-web` create configurations.
`AUTOGRADER_API_URL` changes the API's base URL.
