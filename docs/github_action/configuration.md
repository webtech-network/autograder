# GitHub Action configuration reference

This page describes how to configure `webtech-network/autograder@main` in your workflow and what each input affects at runtime.

## Recommended workflow skeleton

```yaml
name: Autograder
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  grading:
    permissions: write-all
    runs-on: ubuntu-latest
    if: github.actor != 'github-classroom[bot]'
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          path: submission

      - name: Run Autograder
        uses: webtech-network/autograder@main
        with:
          template-preset: "webdev"
          feedback-type: "default"
          include-feedback: "true"
          openai-key: ${{ secrets.ENGINE }}
```

## Inputs

From [`action.yml`](https://github.com/webtech-network/autograder/blob/main/action.yml):

| Input | Required | Default | Notes |
|---|---:|---|---|
| `github-token` | no | `${{ github.token }}` | Used for GitHub API operations (repo/check run access). |
| `template-preset` | yes | - | Template key used by the grading pipeline. Built-ins include `webdev`, `api`, and `input_output`. |
| `feedback-type` | yes | - | `default` or `ai`. |
| `custom-template` | no | - | Currently not usable because `template-preset: custom` is rejected by `github_action/main.py`. |
| `openai-key` | no | - | Required only when `feedback-type` is `ai`. |
| `app-token` | no | - | Optional token for repository access; if omitted, runtime falls back to `github-token`. |
| `include-feedback` | no | `"false"` | Must be `"true"` or `"false"` string. Controls whether feedback step is included. |

## Outputs

`action.yml` declares:

| Output | Description |
|---|---|
| `result` | Base64-encoded JSON with grading results. |

## Required repository structure

The Action loads config from the checkout rooted at `submission/`:

```text
submission/
  .github/
    autograder/
      criteria.json   # required
      feedback.json   # optional (can be {})
      setup.json      # optional (can be {})
```

It also reads student files recursively from `submission/`, excluding `.git` and `.github` directories.

## Secrets and permissions

### Typical secrets

- `ENGINE` (or another secret mapped to `openai-key`) when using AI feedback.
- Optional token secret mapped to `app-token` if you need separate credentials.

### Permissions

`permissions: write-all` is commonly used because the Action may:

- update the workflow check run with score summary;
- commit `relatorio.md` when feedback is enabled.

## Troubleshooting

### `FileNotFoundError: criteria.json file not found`

- Ensure your workflow checks out repository to `path: submission`.
- Ensure config is at `submission/.github/autograder/criteria.json`.

### `OpenAI API key is required for AI feedback mode`

- Provide `openai-key` when `feedback-type: ai`.

### `Invalid value for --include-feedback`

- Use exact strings: `"true"` or `"false"`.

### Check run not updated

- Current implementation searches for a check run named `grading`.
- Keep your job id/name aligned with that expectation.

## See also

- Module internals: [README.md](README.md)
- Demo repository walkthrough: [demo-autograder.md](demo-autograder.md)
