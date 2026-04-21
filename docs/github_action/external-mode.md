# External mode

External mode lets the GitHub Action load grading configuration from a central **Autograder Cloud** instance instead of reading JSON files from the student repository. Results are posted back to the same instance, making every submission visible through the Cloud's submission endpoints.

---

## Overview

In **repo mode** (the default), configuration travels with the student repository:

```
student repo  →  criteria.json / feedback.json / setup.json  →  pipeline  →  check run + relatorio.md
```

In **external mode**, configuration is owned by the instructor and hosted on the Cloud:

```
Autograder Cloud  →  grading config  →  pipeline  →  Autograder Cloud (result)
```

The student repository only needs to contain the source code under `submission/`. No config files are required.

---

## Call sequence

```
GitHub Action
    │
    ├─── GET /api/v1/configs/id/{grading_config_id}   ─────► Autograder Cloud
    │         (auth: AUTOGRADER_CLOUD_TOKEN)                       │
    │◄────────────────────────────────────────────────────── config JSON
    │
    ├─── build_pipeline(criteria_config, template, …)
    │
    ├─── run_autograder(pipeline, student_name, files)
    │         (grading runs locally inside the Action container)
    │
    └─── POST /api/v1/submissions/external-results    ─────► Autograder Cloud
              (auth: AUTOGRADER_CLOUD_TOKEN)
```

### Failure path

If grading raises an exception after the config is fetched, a failure payload (`status: "failed"`, `final_score: 0`) is submitted to the Cloud **before** the Action exits non-zero. This guarantees the Cloud always records a terminal state for every run.

```
run_autograder() raises
    │
    ├─── POST /api/v1/submissions/external-results  (status: "failed")
    │
    └─── SystemExit(1)
```

If the config fetch itself fails (network error, 404, invalid token), no result is posted and the Action exits non-zero immediately.

---

## Required secrets

Configure these as **repository secrets** (or organization secrets shared across classroom repos):

| Secret | Description |
|--------|-------------|
| `AUTOGRADER_CLOUD_URL` | Base URL of your Autograder Cloud instance, e.g. `https://autograder.myschool.edu` |
| `AUTOGRADER_CLOUD_TOKEN` | Integration token (`AUTOGRADER_INTEGRATION_TOKEN` value set on the server) |

> Generate a strong token: `openssl rand -hex 32`

---

## Workflow example

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
          grading-config-id: "42"
          autograder-cloud-url: ${{ secrets.AUTOGRADER_CLOUD_URL }}
          autograder-cloud-token: ${{ secrets.AUTOGRADER_CLOUD_TOKEN }}
          submission-language: "python"
          feedback-type: "default"
          template-preset: "input_output"    # required by the parser; value unused in external mode
```

### `submission-language`

- Optional. When omitted, the first language in the cloud config's `languages` list is used.
- When provided, it is validated against the `languages` list. An unsupported value causes the Action to exit non-zero **without posting a result**.

---

## Step-by-step setup

1. **Deploy the Autograder Cloud** and confirm the API is reachable.
2. **Generate an integration token** and set `AUTOGRADER_INTEGRATION_TOKEN` on the server.
3. **Create a grading configuration** via `POST /api/v1/configs` and note the returned `id`.
4. **Add secrets** `AUTOGRADER_CLOUD_URL` and `AUTOGRADER_CLOUD_TOKEN` to the repository (or organisation).
5. **Add the workflow file** above to `.github/workflows/autograder.yml` in each student repository.
6. **Push a submission** and verify a result appears under `GET /api/v1/submissions/config/{id}`.

---

## Differences from repo mode

| Behaviour | Repo mode | External mode |
|-----------|-----------|---------------|
| Config source | `submission/.github/autograder/*.json` | Autograder Cloud API |
| `include_feedback` | From `include-feedback` action input | From cloud config |
| Result export | GitHub check run + `relatorio.md` | Autograder Cloud API |
| Repository write permissions needed | Yes (`write-all`) | No |
| Failure reporting | GitHub check run status | `POST /api/v1/submissions/external-results` with `status: "failed"` |

---

## Troubleshooting

### `CloudClientError: 401`
The `AUTOGRADER_CLOUD_TOKEN` does not match the server's `AUTOGRADER_INTEGRATION_TOKEN`.  Regenerate and update both.

### `CloudClientError: 404`
The `grading-config-id` does not exist on the server.  Verify the id with `GET /api/v1/configs`.

### `ValueError: Language 'X' not supported`
The `submission-language` value is not in the config's `languages` list.  Update the cloud config or correct the workflow input.

### `ValueError: Config has no languages defined`
The cloud config's `languages` list is empty.  Update the config to include at least one language.

### Action exits non-zero but no result on Cloud
Config fetch failed before any result could be posted.  Check the Action log for the specific error (network, auth, or missing arguments).

---

## See also

- [configuration.md](configuration.md) — full inputs reference
- [README.md](README.md) — module architecture
- [API documentation](../API.md) — Cloud API endpoints
- [Rollout guide](../guides/external-mode-rollout.md) — migration and operational checklist
