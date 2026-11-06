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

## Requirements

Static and AI criteria need nothing from the runner. Criteria and preparation
that run code (I/O, commands, setup and compilation) need Docker on the runner:
the Action runs the submission in one sandbox of the selected language on the
runner's Docker daemon, pulling that language's pinned runtime image (from
about 46 MB for Python to about 364 MB for Java, uncompressed) when the runner
lacks it, and removes the sandbox before it publishes
anything. Every Linux GitHub-hosted runner (`runs-on: ubuntu-latest`) qualifies
with no extra step; no `SANDBOX_*` setting, sandbox service or `docker login` is
needed. Isolation and its limits are in
[Runner execution boundary](trust.md#runner-execution-boundary).

Without a reachable Docker daemon (for example a self-hosted runner without
Docker), such a definition fails before grading, writes no outcome, and the log
says:

```text
ERROR: Docker is not available to the Action. This definition runs <language> code, which the Action executes in a sandbox on the runner's Docker daemon (/var/run/docker.sock). ...
```

Container actions run only on Linux runners; macOS and Windows runners cannot
run this Action at all.

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

`@main` reads `action.yml` from `main` but runs the image built at the
`<version>` tag, so the two must be what was released together. The
`Service and Action images` job of `verify.yml` runs `make action-check` on
every pull request into `main` and on every push to `main`. It fails unless:

- the `<version>` tag is an ancestor of the checked commit (the image was built
  from code `main` contains);
- nothing released changed since that tag: `action.yml`, `Dockerfile.actions`,
  `.dockerignore`, and every path that Dockerfile copies (`pyproject.toml`,
  `uv.lock`, `sandbox_config.yml`, `autograder/`, `execution_host/`,
  `sandbox_manager/`, `github_action/`). A change to any of them needs a new
  version and release, even one that only changes engine code;
- the pinned image can be pulled without credentials (it fails for a missing
  image or a private package);
- so can every runtime image the release's `sandbox_config.yml` pins: the
  Action pulls the selected language's image on the runner.

What enforces this today: the pull request's check is red, and `deploy` needs
that job, so a `main` commit that fails it is not deployed. A red check blocks
the merge only once the `main` ruleset requires the job
([Required checks](../guides/development.md#required-checks)); until the
repository owner adds it, maintainers must not merge into `main` while it is
red.

### Releasing a version

1. On a branch that is up to date with `main`, raise the version in
   `action.yml` (`runs.image`) and open the pull request into `main`. Its
   `make action-check` fails until step 3. Any later commit on the branch (or
   merged from `main`) that changes a released path makes it fail again: raise
   the version and release again.
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
   must print a manifest, not `denied` or `unauthorized`. Each runtime package
   `sandbox_config.yml` pins (`autograder-sandbox-<language>`, published from
   `main` by `sandbox-images.yml`) must be public the same way;
   `make action-check` names any that is not.
4. Re-run the pull request's checks; `make action-check` now passes and the
   pull request can merge. Merge it with a merge commit, not squash or
   rebase: those leave the tagged commit out of `main`, and
   `make action-check` on `main` then fails (and holds back the API deploy)
   until a new version is released. The check gates the merge only once the
   ruleset requires it ([Required checks](../guides/development.md#required-checks));
   until then, confirm it is green yourself before merging.
5. Release notes stay manual, as for `0.1.0`–`0.5.0`: create the GitHub Release
   from the existing `<version>` tag (`gh release create <version> --verify-tag`).

Releases are the `x.y.z` tags from `0.1.0` on. The older `1.1.2`, `v1` and
`v0.0.0-285-test` tags are not releases and do not name this image: do not use
them in `uses:`.

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
