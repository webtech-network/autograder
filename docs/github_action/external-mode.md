# Cloud configuration and publication

External mode fetches one cloud definition by its canonical configuration ID.
It validates the same model as local mode and records the exact normalized hash
and revision in the terminal outcome. Cloud configuration does not imply upload:
Replace `42` with an active configuration whose definition allows `python`,
set the workflow variable and secret, and ensure the service is reachable from
the runner. The checkout must contain the files expected by that definition.

```yaml
name: Grade and publish
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
          execution-mode: external
          grading-config-id: "42"
          autograder-cloud-url: ${{ vars.AUTOGRADER_CLOUD_URL }}
          autograder-cloud-token: ${{ secrets.AUTOGRADER_CLOUD_TOKEN }}
          submission-language: python
          locale: pt-br
          upload-to-cloud: "true"
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: grading-outcome
          path: .autograder/
```

Remove `upload-to-cloud` to retain artifacts without publication. Local repo mode
can also publish: provide the cloud ID/URL/token and `upload-to-cloud: "true"`.
The selected cloud revision must have the same normalized definition hash.

The upload envelope contains `grading_config_id`, `definition_snapshot`, the
exact finished `outcome`, opaque student identity, selected language, and GitHub
metadata. Cloud credentials never appear in that artifact. The API validates
provenance and outcome invariants as an authenticated host attestation.

GET configuration requests may retry transient errors. Result POST makes one
attempt because automatic retries are unsafe until replay deduplication is
implemented. Delivery failure fails the Action, retains `.autograder/outcome.json`
and `.autograder/delivery.json`, and leaves the grading status intact. Failed
evaluation also has a retained failed outcome with null score, which may be
published through the same path.

After checking whether an uncertain delivery was already accepted, download the
saved artifact and add this step to a separate workflow to retry the attestation
without reevaluation:

```yaml
- uses: webtech-network/autograder@main
  with:
    retry-delivery-path: saved-artifact/delivery.json
    autograder-cloud-url: ${{ vars.AUTOGRADER_CLOUD_URL }}
    autograder-cloud-token: ${{ secrets.AUTOGRADER_CLOUD_TOKEN }}
```

`submission-id` is emitted only after successful upload. Upload errors identify
delivery separately from grading; there is no second synthetic failed-grading
upload. No callback/check-run name or repository write token is required.
