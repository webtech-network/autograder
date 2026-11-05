# GitHub Actions adapter

The Action grades one checkout with the same v1 definition and terminal outcome
used by the HTTP service and Python API. Configuration source and result
publication are independent choices. Any workflow job name works; repository
write permissions are unnecessary.

Repo mode loads `.github/autograder/definition.json`. External mode fetches a
validated cloud configuration and binds its revision/hash. Both modes select an
explicit allowed language, or infer it when only one is allowed, and use the
same locale input. The host supplies sandbox/provider infrastructure required by
the selected evaluators. JSON definitions cannot load executable custom plugins.

Every grading execution first writes `.autograder/outcome.json`, scalar outputs,
and an Actions summary. Feedback, when generated, is written to
`.autograder/feedback.md`. A workflow can explicitly upload these as artifacts.
Cloud publication happens only with `upload-to-cloud: "true"`; it writes the
retryable attestation to `.autograder/delivery.json` before sending it.

A completed grade of zero is a successful Action. Failed grading, invalid
configuration, unreadable input, and failed publication fail the Action. Failed
publication retains the completed grade; it never submits a contradictory
failed-grading record. A later workflow may publish saved `delivery.json` through
`retry-delivery-path` without running evaluators again. Retries reuse the
`Idempotency-Key` derived from the saved outcome, so a retried delivery returns the
original receipt instead of creating a duplicate ([replay safety](../contracts/REPLAY.md)).

Classroom check discovery/dashboard synchronization and automatic `relatorio.md`
commits are retired. Existing repository rubrics remain migratable through the
explicit legacy converter; the runtime accepts only the versioned definition.

## Versions and images

The Action runs a prebuilt image: `action.yml` pins
`docker://ghcr.io/webtech-network/autograder-action:<version>`, so a job pulls
it (Python 3.13, the engine, the Action and `git`) and builds nothing. Each
version is one immutable image and one git tag of the same name, on the commit
the image was built from:

| `uses:` | Image |
| --- | --- |
| `webtech-network/autograder@<version>` (e.g. `@0.6.0`) | `autograder-action:<version>`, built from that tag. Reproducible: pin this. |
| `webtech-network/autograder@main` | The version `action.yml` names on `main`: the latest release, not unreleased commits. |

Raising the version in `action.yml` is the release. When that commit reaches
`main` and every verification job passed, CI builds the image from scratch,
checks it (`make test-images`), tags the commit with the version and publishes
the image (`make action-publish`). A published version is never overwritten, and
a version already tagged on another commit stops the release. Until the release
job finishes, `@main` names an image the registry does not have yet.

To test an unreleased change, build and run the image locally the way a runner
does (`make images`, then `docker run` with the workspace mounted at
`/github/workspace`, `GITHUB_WORKSPACE=/github/workspace` and the
`runs.env` variables of `action.yml`; `tests/images/` does exactly this), or,
in a branch of a fork, set `runs.image` to `Dockerfile.actions` and use
`<fork>/autograder@<branch>`: the runner then builds the image from that branch.

- [Quick start](quick-start.md)
- [Inputs and outputs](configuration.md)
- [Cloud publication](external-mode.md)
- [Contract decisions](../contracts/DECISIONS.md)
- [Executable conformance examples](../contracts/CONFORMANCE.md)
