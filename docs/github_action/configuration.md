# Configuration Reference

Complete reference for all inputs, outputs, secrets, and permissions required by `webtech-network/autograder@main`.

---

## Inputs

All inputs are defined in [`action.yml`](https://github.com/webtech-network/autograder/blob/main/action.yml).

### Core inputs

| Input | Required | Default | Description |
|-------|:--------:|---------|-------------|
| `template-preset` | **yes** | — | Template key for the grading pipeline. Built-in values: `webdev`, `api`, `input_output`. In external mode the value is ignored (template comes from the cloud config), but the field is still **required by the parser**. |
| `feedback-type` | **yes** | — | Feedback generation strategy: `"default"` (rule-based) or `"ai"` (OpenAI-powered). |
| `github-token` | no | `${{ github.token }}` | GitHub token for API operations (check run updates, repo access). |
| `openai-key` | no | — | OpenAI API key. **Required** when `feedback-type` is `"ai"`. |
| `app-token` | no | — | Separate token for repository access. Falls back to `github-token` if omitted. |
| `include-feedback` | no | `"false"` | `"true"` or `"false"`. When true, generates feedback and commits `relatorio.md`. **Ignored in external mode** (value is taken from the cloud config). |
| `locale` | no | `"en"` | Locale for feedback messages. Supported: `"en"`, `"pt-br"`. |

### External mode inputs

These inputs are required **only** when `execution-mode` is `"external"`:

| Input | Required | Default | Description |
|-------|:--------:|---------|-------------|
| `execution-mode` | no | `"repo"` | `"repo"` or `"external"`. Determines where grading config is loaded from. |
| `grading-config-id` | conditional | — | Internal database ID of the grading config on the Autograder Cloud. Must be an integer. |
| `autograder-cloud-url` | conditional | — | Base URL of the Autograder Cloud instance (e.g. `https://autograder.myschool.edu`). Trailing slashes are stripped automatically. |
| `autograder-cloud-token` | conditional | — | Bearer token for the Cloud API. Must match `AUTOGRADER_INTEGRATION_TOKEN` on the server. |
| `submission-language` | no | — | Language of the student submission (e.g. `"python"`, `"java"`, `"javascript"`). Validated against the cloud config's `languages` list. Defaults to the first language in the list when omitted. |

### Unsupported inputs

| Input | Status | Notes |
|-------|--------|-------|
| `custom-template` | ❌ Not usable | `template-preset: custom` is rejected by the entrypoint. Reserved for future use. |

---

## Outputs

| Output | Description |
|--------|-------------|
| `result` | Base64-encoded JSON containing grading results. |

---

## Configuration files (repo mode)

When running in repo mode, the Action reads configuration from `submission/.github/autograder/`:

### `criteria.json` (required)

Defines the grading rubric — the hierarchical criteria tree with weighted subjects and tests.

```json
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "content_and_style",
        "weight": 50,
        "subjects": [...]
      }
    ]
  }
}
```

Key fields:

- `test_library` — which template library to use (`web_dev`, `input_output`, `api_testing`)
- `base.subjects` — hierarchical tree of subjects, each with `weight` and either `subjects` (children) or `tests`
- Each test specifies `file`, `name` (test function), and optional `parameters`

### `feedback.json` (optional)

Controls feedback generation behavior. Can be an empty object `{}`.

```json
{
  "general": {
    "show_score": true,
    "show_passed_tests": false,
    "add_report_summary": true
  },
  "default": {}
}
```

### `setup.json` (optional)

Provides setup configuration for the grading environment. Can be an empty object `{}`.

```json
{}
```

---

## Secrets

### Repo mode

| Secret | Maps to input | When needed |
|--------|:-------------:|-------------|
| `ENGINE` (or custom name) | `openai-key` | When using `feedback-type: "ai"` |
| Custom token secret | `app-token` | When separate credentials are needed for repo access |

### External mode

| Secret | Maps to input | Description |
|--------|:-------------:|-------------|
| `AUTOGRADER_CLOUD_URL` | `autograder-cloud-url` | Base URL of the Autograder Cloud |
| `AUTOGRADER_CLOUD_TOKEN` | `autograder-cloud-token` | Integration token matching server's `AUTOGRADER_INTEGRATION_TOKEN` |

!!! tip "Generating a secure token"
    ```bash
    openssl rand -hex 32
    ```
    Set this as `AUTOGRADER_INTEGRATION_TOKEN` on the server and as `AUTOGRADER_CLOUD_TOKEN` in your repository/org secrets.

---

## Permissions

### Repo mode

```yaml
permissions: write-all
```

Required because the Action may:

- Update the workflow check run with the score summary
- Commit `relatorio.md` when feedback is enabled
- The check run export looks for a check run named **`grading`** — keep your job name aligned

### External mode

No elevated permissions required. The Action only communicates with the Autograder Cloud API and does not write to the repository.

---

## Environment variables (internal)

The `action.yml` maps inputs to container environment variables consumed by `entrypoint.sh`:

| Input | Environment variable |
|-------|---------------------|
| `github-token` | `GITHUB_TOKEN` |
| `template-preset` | `TEMPLATE_PRESET` |
| `feedback-type` | `FEEDBACK_TYPE` |
| `custom-template` | `CUSTOM_TEMPLATE` |
| `openai-key` | `OPENAI_KEY` |
| `app-token` | `APP_TOKEN` |
| `include-feedback` | `INCLUDE_FEEDBACK` |
| `execution-mode` | `EXECUTION_MODE` |
| `grading-config-id` | `GRADING_CONFIG_ID` |
| `autograder-cloud-url` | `AUTOGRADER_CLOUD_URL` |
| `autograder-cloud-token` | `AUTOGRADER_CLOUD_TOKEN` |
| `submission-language` | `SUBMISSION_LANGUAGE` |
| `locale` | `LOCALE` |

Additionally, the Action uses these GitHub-provided variables:

| Variable | Usage |
|----------|-------|
| `GITHUB_WORKSPACE` | Root path for file operations |
| `GITHUB_ACTOR` | Student username (passed as `--student-name`) |
| `GITHUB_REPOSITORY` | Repository identifier for API calls |
| `GITHUB_RUN_ID` | Workflow run ID for check run updates |
| `GITHUB_SHA` | Commit SHA included in result metadata |
| `GITHUB_REF` | Branch ref included in result metadata |

---

## Validation rules

The entrypoint enforces these rules before starting the pipeline:

| Condition | Error |
|-----------|-------|
| `feedback-type: "ai"` without `openai-key` | `ValueError: OpenAI API key is required for AI feedback mode` |
| `execution-mode: "external"` without `grading-config-id` | `ValueError: grading-config-id is required` |
| `execution-mode: "external"` without `autograder-cloud-url` | `ValueError: autograder-cloud-url is required` |
| `execution-mode: "external"` without `autograder-cloud-token` | `ValueError: autograder-cloud-token is required` |
| `grading-config-id` not parseable as integer | `ValueError: grading-config-id must be an integer` |
| `include-feedback` not `"true"` or `"false"` | `ValueError: Invalid value for --include-feedback` |
| `template-preset: "custom"` | `SystemExit: Currently, this system does not accept custom templates` |

---

## Troubleshooting

### `FileNotFoundError: criteria.json file not found`

- Ensure your workflow checks out to `path: submission`
- Verify the config is at `submission/.github/autograder/criteria.json`
- This error only occurs in repo mode

### Check run not updated with score

- The export logic searches for a check run named **`grading`**
- Ensure your job name matches: `jobs: grading:`

### `Invalid value for --include-feedback`

- Use exact strings: `"true"` or `"false"` (not booleans)

### `OpenAI API key is required for AI feedback mode`

- Provide `openai-key` input when `feedback-type: "ai"`

---

## See also

- [Overview](README.md) — how the Action works
- [Quick Start Guide](quick-start.md) — complete setup walkthrough
- [External Mode](external-mode.md) — cloud-based grading details
