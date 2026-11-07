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

There are no releases before 1.0.0: `main` is the only channel. `action.yml`
runs `docker://ghcr.io/webtech-network/autograder-action:main`, so a job pulls
that image (Python 3.13, the engine, the Action and `git`) and builds nothing.

Every push to `main` runs the Verify workflow (`.github/workflows/verify.yml`).
Only after every verification job of that commit passed, its `publish` job
rebuilds the images from the commit, checks them again (`make test-images`,
`make sandbox-build-all`) and runs `make publish-images`
(`scripts/publish_images.py`), which publishes, in this order:

| Image | Published as |
| --- | --- |
| Runtime images (`autograder-sandbox-<name>`) | The content-derived references `sandbox_config.yml` pins, each once; a published reference is never overwritten. |
| API, sandbox manager, Action (`autograder-api`, `autograder-sandbox-manager`, `autograder-action`) | `sha-<commit>` (immutable, the full commit SHA), then `main` (moves to this commit). |

It publishes nothing unless the commit is still the head of `main`: an older
commit whose verification finished after a newer one never moves `main` back.
It then confirms each reference as the workflow token sees the registry (a
push the registry does not serve fails the job) and warns for each package an
anonymous runner cannot pull yet. These checks run after every push, so a red
`publish` job may already have moved `main`: read its log before assuming the
previous image is still current. A pull request publishes nothing.

| `uses:` | Image |
| --- | --- |
| `webtech-network/autograder@main` | `autograder-action:main`: built and verified from the newest verified commit of `main`. |

`@main` reads `action.yml` from the head of `main` and runs the image of the
newest *verified* commit. While a new commit is being verified (up to about 45
minutes) the two can differ by that commit; a commit that fails verification
publishes nothing, so `main` keeps the last verified image. Before 1.0.0 there
is no reproducible pin: any `uses:` ref, including a commit SHA, runs the
`main` image. The `0.1.0`–`0.5.0` tags predate this and are not maintained;
the `1.1.2`, `v1` and `v0.0.0-285-test` tags never named this image. Do not use
them in `uses:`.

**Package visibility.** GitHub creates each package private the first time
`main` publishes it. A runner pulls without credentials, so an organization
admin makes each package public once (organization → Packages → the package →
Package settings → Change visibility → Public): `autograder-action` and every
runtime image `autograder-sandbox-<name>`, which the Action pulls on the
runner; `autograder-api` and `autograder-sandbox-manager` too if deployments
pull them anonymously. The `publish` job names any that is still private in a
warning. Confirm as a runner sees it:
`DOCKER_CONFIG="$(mktemp -d)" docker manifest inspect ghcr.io/webtech-network/autograder-action:main`
must print a manifest, not `denied` or `unauthorized`.

To test a change before it reaches `main`, build and run the image locally the way a runner
does (`make images`, then `docker run` with the workspace mounted at
`/github/workspace`, `GITHUB_WORKSPACE=/github/workspace` and the
`runs.env` variables of `action.yml`; `tests/images/` does exactly this), or,
in a branch of a fork, set `runs.image` to `Dockerfile.actions` and use
`<fork>/autograder@<branch>`: the runner then builds the image from that branch.

### The 1.0.0 release (plan)

The first release is 1.0.0, cut once the refactor
([#363](https://github.com/webtech-network/autograder/issues/363)) is complete.
Nothing of it runs or is checked before then. The plan, to be implemented with
the release:

1. Choose a commit `C` of `main` whose `publish` job succeeded.
2. A hand-run release job re-tags `C`'s verified images `sha-<C>` as `1.0.0`
   without rebuilding them, never overwriting an existing `1.0.0`.
3. It commits, on top of `C` and outside `main`, only the change of
   `runs.image` to `autograder-action:1.0.0`, tags that commit `1.0.0` and
   creates the GitHub Release from the tag. `@1.0.0` then runs exactly the
   image verified from `C`, with `C`'s interface; `main` keeps running `:main`.


- [Quick start](quick-start.md)
- [Inputs and outputs](configuration.md)
- [Cloud publication](external-mode.md)
- [Contract decisions](../contracts/DECISIONS.md)
- [Executable conformance examples](../contracts/CONFORMANCE.md)
