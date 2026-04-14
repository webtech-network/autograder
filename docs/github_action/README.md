# GitHub Action module

This module packages the Autograder as a Docker-based GitHub Action so repositories can grade submissions automatically in CI.

It is primarily designed for GitHub Classroom style workflows, but can be used by any repository that follows the expected directory contract.

## What it does

When a workflow runs:

1. Reads student files from `submission/`.
2. Reads grading config from `submission/.github/autograder/`.
3. Builds and executes the Autograder pipeline.
4. Updates the GitHub check run with the final score.
5. Optionally commits `relatorio.md` with feedback.

## Internal architecture

| Component | Responsibility |
|---|---|
| [`action.yml`](https://github.com/webtech-network/autograder/blob/main/action.yml) | Declares Action inputs/outputs and maps inputs to container env vars. |
| [`Dockerfile.actions`](https://github.com/webtech-network/autograder/blob/main/Dockerfile.actions) | Builds runtime image used by the Action. |
| [`github_action/entrypoint.sh`](https://github.com/webtech-network/autograder/blob/main/github_action/entrypoint.sh) | Validates required env vars and executes Python entrypoint with flags. |
| [`github_action/main.py`](https://github.com/webtech-network/autograder/blob/main/github_action/main.py) | Parses arguments, validates runtime options, reads submission files, and starts grading. |
| [`github_action/github_action_service.py`](https://github.com/webtech-network/autograder/blob/main/github_action/github_action_service.py) | Builds pipeline from JSON configs and handles GitHub export operations. |
| [`github_action/github_classroom_exporter.py`](https://github.com/webtech-network/autograder/blob/main/github_action/github_classroom_exporter.py) | Export adapter that reports score and feedback through `GithubActionService`. |

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

## Reference repository

Use **[`webtech-network/demo-autograder`](https://github.com/webtech-network/demo-autograder)** as the baseline implementation. It demonstrates a working workflow, config files, and expected repository layout.

## Next

- Configuration details: [configuration.md](configuration.md)
- Demo walkthrough: [demo-autograder.md](demo-autograder.md)
