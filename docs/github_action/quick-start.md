# Action quick start

Copy the tested [static definition](../contracts/v1/examples/static-conformance.json)
to `.github/autograder/definition.json` in the repository being graded.

This static evaluator does not require a sandbox or provider. Add `index.html`
and an ordinary workflow; its job name is arbitrary:

```yaml
name: Grade
on: [push, workflow_dispatch]
permissions:
  contents: read
jobs:
  assess:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: webtech-network/autograder@main
        id: grade
        with:
          locale: pt-br
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: grading-outcome
          path: .autograder/
```

## Code that runs

The same workflow grades criteria that run the submission. Replace the
definition with the tested [Python I/O definition](../contracts/v1/examples/python-io.json)
and commit a `main.py` that prints the sum of two input lines; for a compiled
language, the [C I/O definition](../contracts/v1/examples/c-io.json) compiles
`main.c` in a setup command first. Nothing else changes: on `ubuntu-latest` the
Action runs the program in a sandbox on the runner's Docker, with no network
and none of the workflow's tokens, and removes it before the step ends
([requirements](README.md#requirements)). CI runs exactly this workflow on every
change to the Action.

## Check the definition first

Before students push, check the definition and grade a reference solution with
it. From a checkout of this repository (`uv sync`), with the reference solution
in a directory:

```sh
python -m execution_host.check .github/autograder/definition.json --submission solution
```

The command compiles the definition exactly as the Action and the HTTP service
do and prints each error at its JSON path, for example
``templates[0]: Unknown template `web_dev`; did you mean `webdev`? [UNKNOWN_TEMPLATE]``.
It states the sandbox time the definition needs per language and the most this
host grants. Each `--submission` directory (repeatable) is read as the Action
reads a checkout and graded through the same pipeline; criteria that run code
use one sandbox at a time on the local Docker, as the Action does on the runner.
It prints every criterion's score and report, then the rendered feedback (or
`Feedback: disabled`). A failed grading prints its code, explanation and, for a
failed setup step, the step's output. `--language` selects the language when
the definition allows several, `--locale` the feedback language, and
`--min-score N` fails a reference that completes below `N`.

| Exit status | Meaning |
| --- | --- |
| `0` | The definition is valid and every reference completed (at or above `--min-score`). |
| `1` | The definition is invalid, or a reference failed to grade or scored below `--min-score`. |
| `2` | The check could not run: a usage error, an unreadable file or directory, or no Docker, runtime image or AI provider for grading. |

As an optional CI step in the repository that holds the definition and its
reference solution, run the same command from the Action's image, giving it the
runner's Docker:

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

## Results

The Action summary shows status and authoritative score. The artifact contains
the canonical outcome and optional feedback. Feedback generation does not edit
a repository branch. A low grade completes successfully; add your own workflow
threshold gate if needed.

For an existing split configuration, convert `criteria.json`, `feedback.json`
and `setup.json` once: assemble a legacy JSON object with `template_name`, explicit `languages`,
`grading_criteria`, `feedback_config`, and `setup_config`, then run:

```bash
python -m autograder.services.definition_migration old.json definition.json
```

See the [contract migration guide](../contracts/DECISIONS.md). Review generated IDs and
paths before committing the v1 definition; ambiguous legacy parameters are
rejected instead of guessed. If your old checkout used `path: submission`,
either use ordinary checkout or set `submission-root: submission` and the
matching `definition-path: submission/.github/autograder/definition.json`.

See [cloud publication](external-mode.md) for cloud configuration and optional
post-grading upload.
