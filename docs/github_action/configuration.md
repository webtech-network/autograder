# GitHub Action configuration reference

This page describes how to configure `webtech-network/autograder@main` in your workflow and what each input affects at runtime.

## Recommended workflow skeleton

### Repo mode (default)

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

### External mode

```yaml
name: Autograder (External)
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  grading:
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
          execution-mode: "external"
          grading-config-id: "42"                              # internal DB id
          autograder-cloud-url: ${{ secrets.AUTOGRADER_CLOUD_URL }}
          autograder-cloud-token: ${{ secrets.AUTOGRADER_CLOUD_TOKEN }}
          submission-language: "python"                        # optional
          feedback-type: "default"
          template-preset: "input_output"                      # required by the parser; value is ignored in external mode
```

## Inputs

From [`action.yml`](https://github.com/webtech-network/autograder/blob/main/action.yml):

| Input | Required | Default | Notes |
|---|---:|---|---|
| `github-token` | no | `${{ github.token }}` | Used for GitHub API operations (repo/check run access). |
| `template-preset` | yes | - | Template key used by the grading pipeline. Built-ins include `webdev`, `api`, and `input_output`. In external mode the pipeline reads the template from the cloud config, but this field is still required by the parser. |
| `feedback-type` | yes | - | `default` or `ai`. |
| `custom-template` | no | - | Currently not usable because `template-preset: custom` is rejected by `github_action/main.py`. |
| `openai-key` | no | - | Required only when `feedback-type` is `ai`. |
| `app-token` | no | - | Optional token for repository access; if omitted, runtime falls back to `github-token`. |
| `include-feedback` | no | `"false"` | Must be `"true"` or `"false"` string. Ignored in external mode (value is taken from the cloud config). |
| `execution-mode` | no | `"repo"` | `"repo"` or `"external"`. Determines where grading configuration is loaded from. |
| `grading-config-id` | no | - | Internal DB id of the grading config on the Autograder Cloud. Required when `execution-mode` is `external`. |
| `autograder-cloud-url` | no | - | Base URL of the Autograder Cloud instance (e.g. `https://cloud.example.com`). Required when `execution-mode` is `external`. |
| `autograder-cloud-token` | no | - | Integration token for the Autograder Cloud API. Required when `execution-mode` is `external`. Should be stored as a repository secret. |
| `submission-language` | no | - | Language of the student submission (e.g. `python`, `java`). Validated against the cloud config's `languages` list. Defaults to the first language in the list when omitted. Only used in `external` mode. |

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

### Repo mode secrets

- `ENGINE` (or another secret mapped to `openai-key`) when using AI feedback.
- Optional token secret mapped to `app-token` if you need separate credentials.

### External mode secrets

| Secret | Maps to input | Description |
|--------|--------------|-------------|
| `AUTOGRADER_CLOUD_URL` | `autograder-cloud-url` | Base URL of the Autograder Cloud instance |
| `AUTOGRADER_CLOUD_TOKEN` | `autograder-cloud-token` | Integration token (set `AUTOGRADER_INTEGRATION_TOKEN` on the server) |

> Generate a strong token on the server: `openssl rand -hex 32`

### Permissions

`permissions: write-all` is required in **repo mode** because the Action may:

- update the workflow check run with score summary;
- commit `relatorio.md` when feedback is enabled.

In **external mode**, no GitHub repository write operations are performed, so elevated permissions are not required.

## Troubleshooting

### `FileNotFoundError: criteria.json file not found`

- Ensure your workflow checks out repository to `path: submission`.
- Ensure config is at `submission/.github/autograder/criteria.json`.
- This error only occurs in **repo mode**; in external mode, config is fetched from the cloud.

### `grading-config-id`, `autograder-cloud-url`, or `autograder-cloud-token` missing

- All three are required when `execution-mode` is `external`.
- The entrypoint validates these before starting the pipeline and exits non-zero if any are absent.

### `OpenAI API key is required for AI feedback mode`

- Provide `openai-key` when `feedback-type: ai`.

### `Invalid value for --include-feedback`

- Use exact strings: `"true"` or `"false"`.

### Check run not updated

- Current implementation searches for a check run named `grading`.
- Keep your job id/name aligned with that expectation.

## See also

- Module internals: [README.md](README.md)
- External mode deep-dive: [external-mode.md](external-mode.md)
- Demo repository walkthrough: [demo-autograder.md](demo-autograder.md)
