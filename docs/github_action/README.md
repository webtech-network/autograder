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

`main` only ever names a published, public image: CI runs `make action-check`
without registry credentials on every pull request into `main` and on `main`,
and it fails while the image `action.yml` pins cannot be pulled anonymously
(missing, or a private package). So `@main` never points at an image a
runner cannot pull.

### Releasing a version

1. On a branch, raise the version in `action.yml` (`runs.image`) and open the
   pull request into `main`. Its `make action-check` fails until step 3.
2. Run the Verify workflow on that branch: Actions → Verify → Run workflow, or
   `gh workflow run verify.yml --ref <branch>`. After every verification job
   passed, the `action-release` job builds the image from scratch, checks it
   (`make test-images`), publishes it (`make action-publish`) and only then
   tags the commit with the version. A published version is never overwritten,
   a version already tagged on another commit stops the release, and a re-run
   resumes an interrupted one. The tag is on the commit the image was built
   from, which is the branch commit, not the merge commit on `main`.
3. The first release creates the GHCR package `autograder-action` as private.
   Make it public once (organization → Packages → `autograder-action` →
   Package settings → Change visibility → Public). Confirm it as a runner
   sees it, without credentials:
   `DOCKER_CONFIG="$(mktemp -d)" docker manifest inspect ghcr.io/webtech-network/autograder-action:<version>`
   must print a manifest, not `denied` or `unauthorized`.
4. Re-run the pull request's checks; `make action-check` now passes and the
   pull request can merge.
5. Release notes stay manual, as for `0.1.0`–`0.5.0`: create the GitHub Release
   from the existing `<version>` tag (`gh release create <version> --verify-tag`).

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
