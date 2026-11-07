# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) as
[Versions and stability](docs/contracts/STABILITY.md) defines it. Steps that
users must take are in the
[migration notes](docs/contracts/DECISIONS.md#migration-notes).

## [Unreleased]

## [1.0.0] - 2026-11-06

The first release: the outcome of the codebase refactoring
([#363](https://github.com/webtech-network/autograder/issues/363)). One versioned
grading definition and one terminal outcome are shared by the Python API, the
HTTP service and the GitHub Action; the engine grades, and each host decides
how work is accepted, executed, isolated and published. Nothing before 1.0.0 is
compatible with it: Action consumers and HTTP integrators start with
[Upgrading to 1.0.0](docs/contracts/DECISIONS.md#upgrading-to-100). Every
breaking change below is marked **Breaking**.

### Added

- Versioned releases: a hand-run Release workflow re-tags the images verified
  from one commit of `main` and pins the Action to them, so
  `webtech-network/autograder@<version>` is reproducible
  ([Releases](docs/github_action/README.md#releases)); a
  [stability policy](docs/contracts/STABILITY.md) and this changelog.
- The grading definition v1 and terminal outcome v1 contracts, with
  generated JSON Schemas, checked-in valid and invalid examples, and stable
  criterion IDs ([Definitions](docs/contracts/DEFINITIONS.md),
  [Outcomes](docs/contracts/OUTCOMES.md)).
- Configuration resources with canonical IDs, assignment aliases, revisions and
  conditional `PATCH`; every accepted execution binds the definition snapshot,
  hash and revision it ran ([REST API](docs/API.md)).
- Durable HTTP acceptance: submissions are PostgreSQL jobs claimed by leased,
  fenced workers that survive restarts, and retryable failures are retried
  within the attempt budget (`WEB_RETRY_SECONDS`, `WEB_MAX_ATTEMPTS`)
  ([Durable jobs](docs/contracts/JOBS.md)).
- Replay-safe acceptance and external-result publication with
  `Idempotency-Key` ([Replay safety](docs/contracts/REPLAY.md)).
- Restricted attestation tokens (`AUTOGRADER_ATTESTATION_TOKENS`) that can only
  publish external results ([HTTP trust boundary](docs/contracts/AUTH.md)).
- Baseline comparison of two stored outcomes by criterion ID
  ([Comparison](docs/contracts/COMPARISON.md)) and the bounded deliberate
  execution API `POST /api/v1/execute` ([Execution](docs/contracts/EXECUTION.md)).
- A typed evaluator catalog with each evaluator's parameter JSON Schema and
  required capabilities, a generated evaluator and definition reference, and a
  trusted Python extension path (`Template`, `TestFunction`, injected
  templates) ([Catalog and Python API](docs/contracts/CATALOG.md),
  [Adding an evaluator](docs/architecture/extending.md)).
- `python -m execution_host.check`: validate a definition and grade reference
  solutions offline, as the hosts do ([Test your rubric](docs/author/testing.md)).
- Explained submission failures: students are told, localized and bounded, why
  a submission could not be graded; the default feedback report explains the
  rubric and how the score was computed ([Student feedback](docs/author/feedback.md)).
- The Action grades execution-based assignments on Linux GitHub-hosted runners
  in a sandbox on the runner's Docker daemon, with no setup step
  ([Action requirements](docs/github_action/README.md#requirements)).
- One host-wide sandbox budget (`general.max_sandboxes`) where saturation waits
  instead of failing, and one execution time budget per grading, enforced
  inside every sandbox ([Sandbox capacity](docs/contracts/JOBS.md#sandbox-capacity)).
- Startup checks: `python -m web.main --check` validates the API configuration,
  the API refuses a database at another migration revision, and hosts verify
  the pinned runtime images and the isolation runtime before serving.
- `make verify` and the Docker, database, image and Action tiers that CI runs
  on every pull request; the capacity benchmark
  `scripts/capacity_benchmark.py` ([Development guide](docs/guides/development.md#verification)).

### Changed

- **Breaking:** one definition file replaces the repository rubric files
  (`criteria.json`, `feedback.json`, `setup.json`) and template presets. Every
  test has an `id`, `type`, `name`, object `parameters` and `weight`; unknown
  fields are rejected, and the offline converter
  `python -m autograder.services.definition_migration` converts old definitions
  ([Definitions](docs/contracts/DECISIONS.md#definitions)).
<!-- ONB-07 (#433): pending its pull request; confirm this entry against the merged change before releasing. -->
- **Breaking:** the authoring vocabulary is simplified: a definition no longer
  lists `templates` or `criteria.base.weight`, `type` alone resolves an
  evaluator, and groups and tests share one label field, I/O evaluators one
  stdin parameter and presence checks one threshold name. Stored definitions
  convert with the offline converter and a database migration
  ([#433](https://github.com/webtech-network/autograder/issues/433)).
- **Breaking:** definitions that compiled but could not grade correctly are
  rejected: an explicit presence threshold of `0`, an empty forbid or find
  list, a standalone shell operator in a command, and a definition whose
  processes need more time than the host allows (`EXECUTION_BUDGET_EXCEEDED`)
  ([ONB-01](docs/contracts/DECISIONS.md#definitions-that-compile-no-longer-onb-01)).
- **Breaking:** every HTTP route except health, readiness and the template
  catalog requires the integration bearer token
  ([HTTP authentication](docs/contracts/DECISIONS.md#http-authentication-int-01)).
- **Breaking:** `POST /api/v1/submissions` answers `202` with a `Location`;
  polling is compact, and authenticated details carry the files as objects
  (`submission_files[name].content`)
  ([Submission details](docs/contracts/DECISIONS.md#submission-details)).
- **Breaking:** results are the terminal outcome v1. A grading that could not
  finish is `failed` with a null score and a coded error, never a zero; a
  student program's nonzero exit or timeout is an assessed zero; the
  sandbox's end is attributed from host evidence. `retryable: true` means the
  host's retries are exhausted. `locale` is `en` or `pt-br`, and
  `EXECUTION_ERROR` is the single code for unexpected failures
  ([Terminal outcomes](docs/contracts/DECISIONS.md#terminal-outcomes),
  [Processes](docs/contracts/DECISIONS.md#processes-arc-08-cor-01),
  [Execution retry](docs/contracts/DECISIONS.md#execution-retry-cor-03)).
- **Breaking:** student-controlled text in outcomes is bounded: reports over
  8 KiB and feedback over 256 KiB are excerpts, and migration `009` excerpts
  stored outcomes ([Outcomes](docs/contracts/OUTCOMES.md#size-bounds)).
- **Breaking:** processes get exact stdin (`inputs: []` is empty stdin), run
  without an implicit shell, and are killed with their children at their
  deadline; compile in `setup_commands`
  ([Processes](docs/contracts/DECISIONS.md#processes-arc-08-cor-01)).
- **Breaking:** the GitHub Action takes `definition-path` and writes
  `.autograder/outcome.json` with the `status`, `score` and `result-path`
  outputs; cloud publication happens only with `upload-to-cloud: "true"`,
  and the Action runs a prebuilt image instead of building one per job
  ([Upgrading to 1.0.0](docs/contracts/DECISIONS.md#upgrading-to-100)).
- **Breaking:** the template catalog drops `available_tests` and
  `requires_sandbox`; read `evaluators[].identifier` and
  `required_capabilities`
  ([Catalog](docs/contracts/DECISIONS.md#catalog-int-11-onb-08)).
- **Breaking:** trusted Python evaluators implement
  `execute(self, evaluation, *, <parameters>)` with typed keyword parameters,
  declare capabilities on the evaluator, run processes through
  `ProcessRequest`, and hosts supply execution, fixture and AI providers
  through `HostCapabilities`; compiled definitions and results are immutable
  ([Host capabilities](docs/contracts/DECISIONS.md#host-capabilities),
  [Evaluator file declarations](docs/contracts/DECISIONS.md#evaluator-file-declarations)).
- **Breaking:** `sandbox_config.yml` requires `general.runtime` (`runsc` by
  default, never a silent fallback to `runc`), `general.max_sandboxes` and a
  `runtimes:` map of pinned, content-versioned runtime images; sandboxes have a
  read-only root, and the control service requires `SANDBOX_API_TOKEN`
  ([Sandbox ownership and configuration](docs/contracts/DECISIONS.md#sandbox-ownership-and-configuration)).
- **Breaking:** migrations own the database schema; the API never creates
  tables and refuses any revision but its own head
  ([Existing databases](docs/contracts/JOBS.md#existing-databases)).
- Student runtimes are Python 3.13, Java 21, Node.js 24 and GCC 15.
- The API, sandbox manager and Action images contain only what their process
  imports; the AI provider is built once per host with a 180 s deadline and no
  hidden retries.
- Grading is faster: each web document is parsed once per grading, files,
  fixture sets and large stdin are staged in one transfer, and a sandboxed
  process costs about a third less under gVisor
  ([Per-test sandbox cost](docs/contracts/DECISIONS.md#per-test-sandbox-cost-prf-08)).
- The documentation is organized around authoring, integrating, extending and
  operating, with executed examples.

### Removed

- **Breaking:** the Action inputs `template-preset`, `custom-template`,
  `feedback-type`, `include-feedback`, `github-token`, `app-token` and
  `openai-key`, and the `result` and `total_score` outputs; GitHub Classroom
  check reporting and automatic `relatorio.md` commits.
- **Breaking:** the Upstash exporter; the settings `SANDBOX_POOL_SIZE`,
  `API_HOST`, `API_PORT`, `API_WORKERS`, `UPSTASH_REDIS_URL`,
  `UPSTASH_REDIS_TOKEN`, `CRITERIA_ASSETS_BUCKET_NAME`, `AWS_ACCESS_ID` and
  `SANDBOX_MAX_HANDLES`, which now stop startup when set
  ([Retired variables](docs/operate/configuration.md#retired-variables)).
- **Breaking:** the sandbox control routes `/run`, `/run-batch`, `/destroy` and
  `/request`, per-language `scale_limit` and `idle_timeout`, and the
  `sandbox-*:latest` runtime images.
- **Breaking:** the pipeline step framework, `PipelineExecution`, the result
  comparator, `TemplateLibraryService` and the other internal Python APIs
  listed in the [migration notes](docs/contracts/DECISIONS.md#migration-notes).
- Automated deployment from `main`; operators upgrade by hand
  ([Upgrade runbook](docs/operate/deployment.md#upgrade-runbook)).

### Fixed

- Invalid definitions are rejected before they are stored or accepted, instead
  of failing during grading.
- Provider, sandbox and publication failures are no longer reported as zero
  grades, and a completed grade is never reported as failed because its
  publication failed.
- A submission can no longer turn its grade into an infrastructure failure by
  killing the sandbox's processes, and a host-ended sandbox no longer
  fabricates a zero.
- Accepted HTTP submissions are no longer lost on restart.
- Sandbox containers are disposed of exactly once and never reused between
  gradings; a failed removal is retried and counted against capacity.
- `webtech-network/autograder@main` runs a published image.

### Security

- Previously unauthenticated configuration, submission and execution routes
  require a bearer token.
- Grading identity no longer comes from credentials, the Action refuses
  untrusted events and runners for cloud publication, and the student's code
  never sees the workflow token
  ([Identity and trust](docs/github_action/trust.md)).
- Submissions run with a read-only root, bounded writable memory and no
  network, under gVisor on the HTTP host.

[Unreleased]: https://github.com/webtech-network/autograder/compare/1.0.0...HEAD
[1.0.0]: https://github.com/webtech-network/autograder/releases/tag/1.0.0
