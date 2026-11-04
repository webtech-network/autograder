# Responsibilities and dependencies

This is the one current map of who owns what. It describes the code as
implemented; the [integration contracts](../contracts/DECISIONS.md) are the
normative versions of each boundary, and this page links to them instead of
repeating their schemas.

## Dependency direction

```text
 web/  (HTTP host)          github_action/  (Actions host)
   │  configs, jobs,           │  repository files, artifact,
   │  persistence, delivery    │  optional cloud publication
   └──────────────┬────────────┘
                  ▼
         execution_host/   composes HostCapabilities:
                  │        DockerHost / DockerSession, S3FixtureProvider,
                  │        ConfiguredAssessmentProvider (OpenAI)
                  ▼
         sandbox_manager/  container leases, run_process, private control API
                  │
                  ▼
           autograder/     core: contracts, compilation, assessment, grading,
                           feedback. Imports none of the packages above.
```

Arrows point from a package to what it may import. Every layer may import the
core; the core receives hosts only as values in `HostCapabilities`.
`tests/unit/test_architecture.py` enforces exactly these directions (core imports
no host package, `sandbox_manager` no host, `execution_host` no web/Actions code)
plus a runtime check that importing every core module loads no host or provider
SDK. It does not prescribe classes or folders.

## Core (`autograder/`)

| Responsibility | Where | Contract |
| --- | --- | --- |
| Versioned definition, normalization, immutable compiled definition (`compile_definition`, `compile_snapshot`) | `models/contracts/definition.py` | [DEFINITIONS.md](../contracts/DEFINITIONS.md) |
| Evaluator contract: `TestFunction`/`AiTestFunction`, parameter contracts derived from `execute`, `validate_parameters`, `accepts_file`; trusted `Template` registries | `models/abstract/`, `models/contracts/parameter_contract.py` | [CATALOG.md](../contracts/CATALOG.md), [Adding an evaluator](extending.md) |
| Discovery (`describe_templates`) read from the same registry | `models/contracts/catalog.py` | [CATALOG.md](../contracts/CATALOG.md) |
| Built-in evaluators and their registry | `template_library/`, `services/template_library_service.py` | [Template Library](../core/template-library.md) |
| Language identity (the only language list) | `models/language.py` | [LANGUAGES.md](../contracts/LANGUAGES.md) |
| Submission input and evaluator file selection | `models/dataclass/submission.py`, `services/file_selection.py` | [SUBMISSIONS.md](../contracts/SUBMISSIONS.md), [FILES.md](../contracts/FILES.md) |
| Host capability protocols: `ExecutionSession` (`run_process`), `ServerSession`, `AssessmentProvider`, fixture `reference -> bytes` | `models/capabilities.py`, `models/execution.py`, `models/process.py` | [CAPABILITIES.md](../contracts/CAPABILITIES.md), [PROCESSES.md](../contracts/PROCESSES.md) |
| Run order: bind language, validate, acquire/prepare a session, assess, grade, requested feedback, close, finalize | `autograder.py` (`AutograderPipeline.run`), `services/preparation.py` | [Grading flow](../core/pipeline-architecture.md) |
| Assessment: ordinary evaluators one by one, all AI criteria in one provider batch, results keyed by criterion ID | `services/assessment.py` | [DECISIONS.md](../contracts/DECISIONS.md#ai-batching-inside-assessment-arc-07) |
| Result model and scoring: frozen `ResultOutcomeTree` built once; one scoring definition; definition-vs-outcome verification | `services/grading.py`, `models/contracts/scoring.py`, `models/contracts/verification.py` | [OUTCOMES.md](../contracts/OUTCOMES.md) |
| Requested feedback (focus ranking + the default report) | `services/feedback.py`, `services/focus_service.py`, `services/report/` | [Feedback Generation](../core/feedback-generation.md) |
| Baseline comparison: pure `compare_outcomes` over two completed canonical outcomes and their bound definitions, joined by criterion ID; never a grading stage | `models/contracts/comparison.py` | [Baseline Comparison](../features/baseline_comparison.md) |
| Terminal outcome v1 and the facade (`evaluate_submission`, `build_pipeline`) | `models/contracts/outcome.py`, `facade.py` | [OUTCOMES.md](../contracts/OUTCOMES.md) |

The core never imports Docker, S3, OpenAI, HTTP frameworks or databases, never
interprets platform identities or database IDs, and keeps no process globals for
hosts. Diagnostics are optional observations, never data for later operations
([diagnostics](pipeline_execution_tracking.md)).

## Execution infrastructure (`sandbox_manager/`)

Owns Docker containers: pools keyed by the domain `Language`; one owner from
`get_sandbox(language)` to `dispose(sandbox)`, which forgets a sandbox only after
Docker confirms removal (a failed removal is *quarantined*: still tracked,
counted against capacity and retried with backoff); used sandboxes are never
returned to a pool. Containers carry owner-lease labels, startup reclaims only
provably dead owners, and operators use `python -m sandbox_manager.reclaim` for
the rest. It also owns the single Docker profile and limits, `run_process` with
exact stdin and confirmed termination, artifact readback, and the private
bearer-authenticated control API (one worker) with its remote client. Language-to-image mapping is host configuration
(`sandbox_config.yml` `runtimes:`). See [SANDBOX.md](../contracts/SANDBOX.md),
[PROCESSES.md](../contracts/PROCESSES.md) and
[Sandbox Manager Internals](sandbox_manager.md).

## Host composition (`execution_host/`)

Builds the `HostCapabilities` a host passes to the core: `DockerHost` (local or
remote manager, one `DockerSession` per run), `S3FixtureProvider` (uncached
`reference -> bytes`, `FixtureNotFound` for a missing key) and
`ConfiguredAssessmentProvider` (OpenAI, configured from the environment). A new
host or provider is a new value here or in a host, not a core change.

## Hosts (`web/`, `github_action/`)

Hosts collect files, authenticate, choose the definition identity and revision,
accept and schedule work, persist or publish the finalized outcome, and retry
delivery without grading again.

- **HTTP** (`web/`): one bearer-token trust boundary for every non-public route
  (integration and per-producer attestation principals,
  [AUTH.md](../contracts/AUTH.md)); configuration resources with revisions and
  conditional `PATCH`; durable PostgreSQL submission jobs with leased workers and
  outcome receipts ([JOBS.md](../contracts/JOBS.md)); replay-safe acceptance and
  attestation through `Idempotency-Key` ([REPLAY.md](../contracts/REPLAY.md));
  polling and authenticated details; external result attestation (verified with
  the same `verify_outcome_tree` as local grades); the read-only baseline
  comparison route; and bounded deliberate execution. See
  [Web Module](web_module.md), [API.md](../API.md) and
  [Deliberate Code Execution](../features/deliberate_code_execution.md).
- **GitHub Actions** (`github_action/`): compiles the repository definition (or
  reloads the selected cloud revision's snapshot), grades with
  `DockerHost.from_environment()`, saves the canonical artifact, then optionally
  publishes it as an attestation. Submitter, actor and producer identities stay
  separate and runner trust is enforced ([Identity and Trust](../github_action/trust.md)).
  See [GitHub Action](../github_action/README.md).

## Current behavior and plans

Everything above is implemented and tested. The following are **not**
implemented and must not be described as current behavior:

- No shipped host supplies `server_execution`; API-testing criteria fail with
  `SERVER_CAPABILITY_UNAVAILABLE`.
- Durable jobs are claimed in submission order by a fixed worker count;
  there is no priority, fairness or quota scheduling policy.
- Sandbox handles of the control API live in one process; there is no shared
  handle store or distributed sandbox provisioning.
- Feedback has one mode (`default`); there is no AI report mode.
- Fixtures are not cached; any future cache must meet the identity and
  invalidation rules in [CAPABILITIES.md](../contracts/CAPABILITIES.md).
