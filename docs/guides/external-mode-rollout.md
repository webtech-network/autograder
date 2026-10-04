# External mode rollout

The v1 definition/outcome contract requires coordinated workflow and server
migration. Runtime support for the old split-file/parameter-list format is
removed; use the explicit offline converter and review its output first.

1. Aggregate legacy assignment settings into one JSON object containing
   `template_name`, explicit `languages`, `grading_criteria`, `setup_config`,
   `feedback_config`, and `include_feedback`.
2. Run `python -m autograder.services.definition_migration old.json definition.json`.
   Resolve reported ambiguous parameters, unsupported setup fields, and duplicate
   learning-resource labels. The converter preserves scoring and generates stable
   criterion IDs from their old paths; instructors should review those IDs.
3. Save the resulting definition through `POST /api/v1/configs` inside the
   `definition` field. Record the canonical configuration ID and revision/hash.
4. Change the workflow to the [new Action inputs](../github_action/configuration.md).
   Ordinary checkout no longer requires `path: submission`. Use an explicit
   `submission-root` and `definition-path` if retaining that layout.
5. Configure cloud URL and authentication token as workflow variables/secrets.
   The token must match the server's `AUTOGRADER_INTEGRATION_TOKEN`.
6. Choose `execution-mode: external` to fetch the definition, and separately
   choose `upload-to-cloud: "true"` to publish the finalized outcome. Local
   artifacts remain available with either configuration source.
7. Upload `.autograder/` using `actions/upload-artifact` with `if: always()`.
   Replace check-run synchronization and automatic feedback commits with the
   outcome/feedback artifacts and ordinary workflow summary.

Verify a known-good static assignment first: its canonical outcome has
`status: completed`, an authoritative finite score and tree, and the expected
provenance. Verify a known failed student criterion produces a completed zero
rather than a system failure. Verify unavailable required infrastructure produces
`status: failed` with null score and a safe structured error.

For cloud publication, verify the uploaded submission ID and stored outcome
match the retained artifact. An upload failure must leave that artifact intact;
inspect whether an uncertain POST was accepted before explicitly retrying saved
`delivery.json`. Delivery retry does not run grading again.

See [cloud execution and retry examples](../github_action/external-mode.md) and
[contract decisions](../contracts/DECISIONS.md).
