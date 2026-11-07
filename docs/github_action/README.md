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

Releases are versioned `MAJOR.MINOR.PATCH`, from 1.0.0
([versions and stability](../contracts/STABILITY.md)); `main` is the development
channel between them. Either way a job pulls a prebuilt image (Python 3.13, the
engine, the Action and `git`) and builds nothing:

| `uses:` | `runs.image` | Image |
| --- | --- | --- |
| `webtech-network/autograder@<version>` | `autograder-action:<version>` | Exactly the image verified from the commit the release was cut from, with that commit's `action.yml`. Reproducible: pin this. |
| `webtech-network/autograder@main` | `autograder-action:main` | The image of the newest verified commit of `main`. |

Every push to `main` runs the Verify workflow (`.github/workflows/verify.yml`).
Only after every verification job of that commit passed, its `publish` job
rebuilds the images from the commit, checks them again (`make test-images`,
`make sandbox-build-all`) and runs `make publish-images`
(`scripts/publish_images.py`), which publishes, in this order:

| Image | Published as |
| --- | --- |
| Runtime images (`autograder-sandbox-<name>`) | The content-derived references `sandbox_config.yml` pins, each once; a published reference is never overwritten. |
| API, sandbox manager, Action (`autograder-api`, `autograder-sandbox-manager`, `autograder-action`) | `sha-<commit>` (the full commit SHA), never overwritten: a re-run of the job for the same commit keeps the first run's images. Then `main`, moved in the registry to those same `sha-<commit>` manifests. |

It publishes nothing unless the commit is still the head of `main`: an older
commit whose verification finished after a newer one never moves `main` back.
It confirms each reference as the workflow token sees the registry (a push the
registry does not serve fails the job) and warns for each package an anonymous
runner cannot pull yet. A `main` that does not serve the `sha-<commit>`
manifests fails the job too, so a red `publish` job may already have moved
`main`: read its log before assuming the previous image is still current. A
pull request publishes nothing.

`@main` reads `action.yml` from the head of `main` and runs the image of the
newest *verified* commit. While a new commit is being verified (up to about 45
minutes) the two can differ by that commit; a commit that fails verification
publishes nothing, so `main` keeps the last verified image. Any `uses:` ref
other than a release tag, including a commit SHA, runs that moving `main` image.
The tags older than 1.0.0 (`0.1.0`–`0.5.0`, `1.1.2`, `v1`, `v0.0.0-285-test`)
do not run this Action; see
[upgrading to 1.0.0](../contracts/DECISIONS.md#upgrading-to-100).

**Package visibility.** GitHub creates each package private the first time
`main` publishes it. A runner pulls without credentials, so an organization
admin makes each package public once (organization → Packages → the package →
Package settings → Change visibility → Public): `autograder-action` and every
runtime image `autograder-sandbox-<name>`, which the Action pulls on the
runner; `autograder-api` and `autograder-sandbox-manager` too if deployments
pull them anonymously. The `publish` and release jobs name any that is still
private in a warning. Confirm as a runner sees it:
`DOCKER_CONFIG="$(mktemp -d)" docker manifest inspect ghcr.io/webtech-network/autograder-action:main`
must print a manifest, not `denied` or `unauthorized`.

To test a change before it reaches `main`, build and run the image locally the way a runner
does (`make images`, then `docker run` with the workspace mounted at
`/github/workspace`, `GITHUB_WORKSPACE=/github/workspace` and the
`runs.env` variables of `action.yml`; `tests/images/` does exactly this), or,
in a branch of a fork, set `runs.image` to `Dockerfile.actions` and use
`<fork>/autograder@<branch>`: the runner then builds the image from that branch.

### Releases

A maintainer releases a commit `C` of `main` by hand, with the Release workflow
(`.github/workflows/release.yml`); nothing else tags or releases. It rebuilds
nothing: it runs `make release` (`scripts/release.py`), which first checks, and
refuses with nothing changed unless:

* `C` is a full commit SHA on `main`, and its `Publish images from main` job
  succeeded, so the registry serves the `sha-<C>` images verification passed;
* at `C`, `pyproject.toml` declares the version, `CHANGELOG.md` has its
  section, and `action.yml` runs `autograder-action:main`;
* no tag of that version exists, and no image is tagged with it except the
  `sha-<C>` manifest itself (left by an interrupted run of the same release).

It then tags the `sha-<C>` manifests of the API, sandbox manager and Action
images with the version, by digest; commits on top of `C`, outside `main`,
the one change of `runs.image` to `autograder-action:<version>`; pushes only
the annotated tag `<version>` naming that commit; and creates the GitHub
Release from the tag with the changelog section as its notes. `@<version>` then
runs exactly the image verified from `C`, with `C`'s interface, while `main`
keeps running `:main`. A version is released once: a tag or an image tag of it
is never moved. The maintainer steps are in the
[development guide](../guides/development.md#releasing).


- [Quick start](quick-start.md)
- [Inputs and outputs](configuration.md)
- [Cloud publication](external-mode.md)
- [Contract decisions](../contracts/DECISIONS.md)
- [Executable conformance examples](../contracts/CONFORMANCE.md)
