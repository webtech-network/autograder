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
