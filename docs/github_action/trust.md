# Action identity and runner trust (INT-02)

The Action keeps three identities apart:

| Identity | Meaning | Source | Used for |
| --- | --- | --- | --- |
| **Submitter** | Who owns the graded work | `submitter-id` / `submitter-name`, else the repository | `external_user_id`, `username`, history |
| **Actor** | Who started or re-ran the workflow | `GITHUB_ACTOR`, `GITHUB_TRIGGERING_ACTOR` | provenance only |
| **Producer** | Which credential published the attestation | the bearer token's principal (`attestation:<name>`) | authorization and replay keys ([AUTH.md](../contracts/AUTH.md)) |

Credentials never become an identity: tokens are not written to the outcome,
`delivery.json`, outputs, summaries, logs or submission metadata, and the sandbox
that runs submission code receives none of the runner's environment.

## Identity mapping

| Situation | `submitter-id` | Resulting `external_user_id` | `username` |
| --- | --- | --- | --- |
| Prisma dispatches grading for a student | Prisma's opaque student ID | that ID, e.g. `prisma:student:8f1c` | `submitter-name` or the ID |
| Ordinary one-repository-per-student grading (GitHub Classroom) | omitted | `github-repository:<GITHUB_REPOSITORY_ID>` | `owner/repository` |
| Local/operator run outside Actions | omitted | `local` | `local` |

The assignment identity is the canonical `grading-config-id`, and the definition
revision is bound in the outcome provenance. The workflow actor is **never** a
fallback for the submitter: an instructor re-running a student's workflow does not
take ownership of the grade.

### Prisma example

```yaml
on:
  repository_dispatch:
    types: [grade-submission]   # sent by Prisma with the student/commit to grade
jobs:
  grade:
    runs-on: ubuntu-latest      # GitHub-hosted
    steps:
      - uses: actions/checkout@v4
        with:
          repository: ${{ github.event.client_payload.repository }}
          ref: ${{ github.event.client_payload.commit }}
          path: submission
      - uses: webtech-network/autograder@main
        with:
          submission-root: submission
          definition-path: grader/definition.json   # from the instructor's grader repository
          submitter-id: ${{ github.event.client_payload.student_id }}
          submitter-name: ${{ github.event.client_payload.student_name }}
          grading-config-id: ${{ vars.AUTOGRADER_CONFIG_ID }}
          grading-config-revision: ${{ vars.AUTOGRADER_CONFIG_REVISION }}
          autograder-cloud-url: ${{ vars.AUTOGRADER_CLOUD_URL }}
          autograder-cloud-token: ${{ secrets.AUTOGRADER_ATTESTATION_TOKEN }}
          upload-to-cloud: "true"
```

The workflow lives in an instructor-controlled repository, so students control
neither the workflow nor its secrets.

### Ordinary repository example

```yaml
on: push
jobs:
  grade:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: webtech-network/autograder@main   # grades the repository; no publication
      - uses: actions/upload-artifact@v4
        if: always()
        with: {name: autograder, path: .autograder/}
```

Without `submitter-id` the repository is the submitter. Results stay in the
workflow artifact and summary; see the trust table before adding publication.

## Run provenance

Every published attestation stores `submission_metadata`:

```json
{
  "submitter_source": "input",
  "github": {
    "repository": "classroom/hello-alice", "repository_id": "424242",
    "event_name": "push", "ref": "refs/heads/main",
    "event_sha": "<GITHUB_SHA>",
    "evaluated_commit": "<HEAD of submission-root>",
    "evaluated_tree_matches_commit": true,
    "run_id": "9001", "run_attempt": "2",
    "workflow_ref": "classroom/hello-alice/.github/workflows/grade.yml@refs/heads/main",
    "actor": "alice", "triggering_actor": "instructor-bob",
    "runner_environment": "github-hosted"
  }
}
```

`evaluated_commit` is `git rev-parse HEAD` in the submission root — the files
actually graded — which may differ from the event's `GITHUB_SHA` (for example a
pull request merge commit, or a checkout of another ref). It is `null` when the
root is not a Git checkout. `evaluated_tree_matches_commit` is `false` when any
graded file under the root is modified, untracked or ignored (`.git`, `.github`
and `.autograder` are not graded and are not considered).

### Executions and retries

| Event | Grading | Attestation key | Result |
| --- | --- | --- | --- |
| Run 9001 attempt 1 | runs | `action-outcome:<execution A>` | submission 41 |
| Retry attempt 1's `delivery.json` | none | same key | submission 41 (replayed) |
| Re-run: run 9001 attempt 2 (by anyone) | runs again | `action-outcome:<execution B>` | submission 42, same submitter |

See [replay safety](../contracts/REPLAY.md).

## Trust table

Anyone who controls a workflow file or the runner can read the secrets given to
that workflow and can therefore publish any score with them. An uploaded result
is the producer's **claim**; authentication proves which credential sent it, not
that this server executed the grader or that the grade is correct.

| Event / runner | Who controls the workflow and code | Secrets available | Publication |
| --- | --- | --- | --- |
| `push`, `workflow_dispatch`, `schedule`, `repository_dispatch` in an **instructor-owned** repository, GitHub-hosted runner | instructors | yes | **supported, authoritative** |
| Same events in a **student-writable** repository | the student (can edit workflows) | yes | supported, but the attestation is **student-controlled**: treat it as unverified, or grade server-side |
| `pull_request` from the same repository | writers of the repository | yes | supported (same caveat as above) |
| `pull_request` from a fork | the fork author | no repository secrets | **refused** by the Action |
| `pull_request_target` | base workflow with fork code | yes | **refused** — would expose secrets to fork code |
| `workflow_run` | follows a possibly untrusted run | yes | **refused** — artifacts of the triggering run may be forged |
| Any other event | — | — | **refused** |
| Self-hosted runner | whoever administers the runner; previous jobs may persist state | yes | refused unless `trusted-self-hosted-runner: "true"`; only for ephemeral runners dedicated to an instructor-owned repository |
| Outside GitHub Actions (operator shell) | the operator | the operator's | allowed |

Minimum permissions: the Action needs no `GITHUB_TOKEN` scopes (use
`permissions: {contents: read}` for checkout). Use a **restricted attestation
token** (`AUTOGRADER_ATTESTATION_TOKENS` on the server) together with
`grading-config-revision`; it can only publish outcomes and cannot read source,
configurations or other grades. `execution-mode: external` reads the configuration
and therefore needs the integration token: use it only in instructor-owned
workflows, never in student-writable repositories.

**Untrusted work** (student-writable repositories, forks): the authoritative path
is server-side grading. Prisma (a trusted broker) submits the student's files with
`POST /api/v1/submissions`, and this server executes the grader in its own sandbox.
Workflow artifacts may still be shown to students as unofficial feedback.

## Runner execution boundary

The Action runs submission code through the same Docker sandbox profile as the
web host (`SANDBOX_MODE=local` with a docker socket, or `remote`): no network, no
capabilities, resource limits, only the submission files copied in, and no
environment variables from the runner. The Action owns its sandboxes for the run
and disposes them before publishing. `tests/integration/test_action_runner_boundary.py`
verifies with real Docker that tokens, provider keys and the docker socket are not
visible to submission code.

## Migration

* `student-name` (implicitly `GITHUB_ACTOR`) is removed; passing it fails with
  guidance. Pass `submitter-id`/`submitter-name`, or rely on the repository fallback.
  Existing histories keyed by GitHub login keep their old `external_user_id`; new
  attestations use the new identity.
* `submission_metadata` changed from `{repository, commit_sha, run_id, actor, ref}`
  to `{submitter_source, github: {...}}` above; `commit_sha` is now `event_sha`, and
  `evaluated_commit` is new.
* Publication from `pull_request_target`, `workflow_run`, fork pull requests,
  unknown events and self-hosted runners now fails unless explicitly supported.
* Switch publication workflows to a restricted attestation token plus
  `grading-config-revision`.
