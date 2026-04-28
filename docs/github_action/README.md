# GitHub Action module

This module packages the Autograder as a Docker-based GitHub Action so repositories can grade submissions automatically in CI.

It is primarily designed for GitHub Classroom style workflows, but can be used by any repository that follows the expected directory contract.

## Execution modes

| Mode | How config is loaded | When to use |
|------|---------------------|-------------|
| `repo` (default) | From config files checked out inside `submission/.github/autograder/` | Repository-based setups where grading config lives in the student repo |
| `external` | Fetched from the Autograder Cloud API at runtime | Centralised setups where a single Autograder Cloud instance manages all assignments |

## What it does (repo mode)

When a workflow runs in `repo` mode:

1. Reads student files from `submission/`.
2. Reads grading config from `submission/.github/autograder/`.
3. Builds and executes the Autograder pipeline.
4. Updates the GitHub check run with the final score.
5. Optionally commits `relatorio.md` with feedback.

## What it does (external mode)

When a workflow runs in `external` mode:

1. Fetches the grading configuration from the Autograder Cloud (`GET /api/v1/configs/id/{id}`).
2. Reads student files from `submission/`.
3. Builds and executes the Autograder pipeline.
4. Posts the grading result back to the Autograder Cloud (`POST /api/v1/submissions/external-results`).
5. If grading fails for any reason, posts a `failed` status payload before exiting non-zero.

## Internal architecture

| Component | Responsibility |
|---|---|
| [`action.yml`](https://github.com/webtech-network/autograder/blob/main/action.yml) | Declares Action inputs/outputs and maps inputs to container env vars. |
| [`Dockerfile.actions`](https://github.com/webtech-network/autograder/blob/main/Dockerfile.actions) | Builds runtime image used by the Action. |
| [`github_action/entrypoint.sh`](https://github.com/webtech-network/autograder/blob/main/github_action/entrypoint.sh) | Validates required env vars and executes Python entrypoint with flags. |
| [`github_action/main.py`](https://github.com/webtech-network/autograder/blob/main/github_action/main.py) | Parses arguments, validates runtime options, reads submission files, and starts grading. |
| [`github_action/github_action_service.py`](https://github.com/webtech-network/autograder/blob/main/github_action/github_action_service.py) | Builds pipeline from JSON configs and handles GitHub export operations. |
| [`github_action/github_classroom_exporter.py`](https://github.com/webtech-network/autograder/blob/main/github_action/github_classroom_exporter.py) | Export adapter that reports score and feedback through `GithubActionService`. |
| [`github_action/cloud_client.py`](https://github.com/webtech-network/autograder/blob/main/github_action/cloud_client.py) | HTTP client for the Autograder Cloud API (config fetch + result submission). Uses exponential back-off on 5xx/network errors; raises `CloudClientError` on 4xx. |
| [`github_action/cloud_exporter.py`](https://github.com/webtech-network/autograder/blob/main/github_action/cloud_exporter.py) | Export adapter for external mode. Builds the `ExternalResultCreate` payload and calls `CloudClient`. Provides `submit_failure()` for the failure path. |

## Repository contract required by the Action

Your workflow should checkout repository content into a folder named `submission`:

```yaml
- uses: actions/checkout@v4
  with:
    path: submission
```

Inside that checkout, the Action expects:

- `submission/.github/autograder/criteria.json` (required)
- `submission/.github/autograder/feedback.json` (optional, empty object allowed)
- `submission/.github/autograder/setup.json` (optional, empty object allowed)

## Important runtime notes

- `template-preset: custom` is currently rejected by the Action entrypoint.
- `feedback-type: ai` requires `openai-key`.
- The current notification logic looks for a check run named `grading`.
- `include-feedback: "true"` enables feedback generation and may update `relatorio.md`.
- In `external` mode, `include_feedback` is taken from the cloud config, **not** from the `include-feedback` action input.
- In `external` mode, `submission-language` is validated against the `languages` list in the cloud config. Omitting it defaults to the first language in that list.

## Reference repository

Use **[`webtech-network/demo-autograder`](https://github.com/webtech-network/demo-autograder)** as the baseline implementation. It demonstrates a working workflow, config files, and expected repository layout.

## Next

- Configuration details: [configuration.md](configuration.md)
- External mode deep-dive: [external-mode.md](external-mode.md)
- Demo walkthrough: [demo-autograder.md](demo-autograder.md)
