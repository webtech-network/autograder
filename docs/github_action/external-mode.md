# External Mode

External mode lets the GitHub Action load grading configuration from a central **Autograder Cloud** instance instead of reading JSON files from the student repository. Results are posted back to the Cloud, making every submission visible through its API.

---

## When to use external mode

- You manage a multi-repository classroom and want a **single place** to configure grading criteria.
- You want grading results stored centrally rather than scattered across individual check runs.
- You need to change grading criteria without pushing commits to every student repo.

---

## How it works

```
GitHub Action
    │
    ├── GET /api/v1/configs/id/{grading_config_id}  ──────► Autograder Cloud
    │       (auth: Bearer AUTOGRADER_CLOUD_TOKEN)                │
    │◄──────────────────────────────────────────────────── config JSON
    │
    ├── build_pipeline(criteria_config, template, …)
    │
    ├── run_autograder(pipeline, student_name, files)
    │       (grading runs locally inside the Action container)
    │
    └── POST /api/v1/submissions/external-results   ──────► Autograder Cloud
            (auth: Bearer AUTOGRADER_CLOUD_TOKEN)
```

### Failure handling

If grading raises an exception **after** the config is fetched, a failure payload is submitted before the Action exits:

```
run_autograder() raises  ──► POST external-results (status: "failed", score: 0)  ──► exit 1
```

If the config fetch itself fails (network, 404, bad token), no result is posted and the Action exits non-zero immediately.

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
          template-preset: "input_output"
          locale: "pt-br"
```

!!! note
    `template-preset` is required by the argument parser but its value is **ignored** in external mode — the template comes from the cloud config.

---

## Required inputs

| Input | Description |
|-------|-------------|
| `execution-mode` | Must be `"external"` |
| `grading-config-id` | Integer ID of the grading config on the Cloud |
| `autograder-cloud-url` | Base URL of the Autograder Cloud (e.g. `https://autograder.myschool.edu`) |
| `autograder-cloud-token` | Bearer token matching the server's `AUTOGRADER_INTEGRATION_TOKEN` |
| `template-preset` | Any valid value (required by parser, not used) |
| `feedback-type` | `"default"` or `"ai"` |

### Optional inputs

| Input | Default | Description |
|-------|---------|-------------|
| `submission-language` | First language in config | Validated against the cloud config's `languages` list |
| `locale` | `"en"` | Locale for feedback messages (`"en"`, `"pt-br"`) |
| `openai-key` | — | Required only when `feedback-type: "ai"` |

---

## Differences from repo mode

| Behaviour | Repo mode | External mode |
|-----------|-----------|---------------|
| Config source | `submission/.github/autograder/*.json` | Autograder Cloud API |
| `include_feedback` | From `include-feedback` action input | From cloud config field |
| Result export | GitHub check run + `relatorio.md` | Autograder Cloud API |
| Repository write permissions | Required (`write-all`) | Not required |
| Failure reporting | Check run status | `POST external-results` with `status: "failed"` |
| Student repo needs config files | Yes | No |

---

## Cloud config structure

When fetched from `GET /api/v1/configs/id/{id}`, the config contains:

```json
{
  "id": 42,
  "template_name": "input_output",
  "languages": ["python", "java"],
  "include_feedback": true,
  "criteria_config": { "...": "criteria tree JSON" },
  "feedback_config": { "...": "feedback settings" },
  "setup_config": { "...": "setup options" }
}
```

| Field | Corresponds to (repo mode) |
|-------|---------------------------|
| `criteria_config` | `criteria.json` |
| `feedback_config` | `feedback.json` |
| `setup_config` | `setup.json` |
| `template_name` | `template-preset` action input |
| `include_feedback` | `include-feedback` action input |
| `languages` | Available submission languages |

---

## Result payload

The Action submits this payload to `POST /api/v1/submissions/external-results`:

```json
{
  "grading_config_id": 42,
  "external_user_id": "student-github-username",
  "username": "student-github-username",
  "language": "python",
  "status": "completed",
  "final_score": 85.5,
  "feedback": "## Grading Report\n...",
  "result_tree": { "...": "full result tree" },
  "focus": { "...": "focus analysis" },
  "execution_time_ms": 3421,
  "error_message": null,
  "submission_metadata": {
    "repository": "org/student-repo",
    "commit_sha": "abc123...",
    "run_id": "12345678",
    "actor": "student-username",
    "ref": "refs/heads/main"
  }
}
```

On failure, `status` is `"failed"`, `final_score` is `0.0`, and `error_message` contains the exception description.

---

## Setup guide

### Step 1: Deploy the Autograder Cloud

Ensure the API is running and reachable from GitHub Actions runners:

```bash
curl https://your-cloud-url/api/v1/health
```

### Step 2: Generate an integration token

```bash
openssl rand -hex 32
```

Set this as `AUTOGRADER_INTEGRATION_TOKEN` on the server before starting the API.

### Step 3: Create a grading configuration

Use `POST /api/v1/configs` to create a config. Note the returned `id`.

```bash
curl -X POST https://your-cloud-url/api/v1/configs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "input_output",
    "languages": ["python"],
    "include_feedback": true,
    "criteria_config": { "...": "your criteria" },
    "feedback_config": {},
    "setup_config": {}
  }'
```

### Step 4: Add repository secrets

Add to the repository (or organisation level for all classroom repos):

| Secret | Value |
|--------|-------|
| `AUTOGRADER_CLOUD_URL` | `https://your-cloud-url` |
| `AUTOGRADER_CLOUD_TOKEN` | The token from Step 2 |

### Step 5: Add the workflow

Create `.github/workflows/autograder.yml` in each student repository with the workflow example above.

### Step 6: Verify

Push a submission and check:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://your-cloud-url/api/v1/submissions/config/42
```

---

## Migrating from repo mode

Existing repo-mode workflows **continue to work without changes**. External mode is opt-in.

### Migration strategy

1. Leave existing repo-mode workflows untouched.
2. For new assignments, use external mode with a Cloud config.
3. For existing assignments, migrate one at a time:
    - Create the equivalent Cloud config
    - Update the workflow to external mode
    - Remove `.github/autograder/` from the student repo template

### Config field mapping

| Repo-mode source | Cloud config field |
|------------------|--------------------|
| `criteria.json` | `criteria_config` |
| `feedback.json` | `feedback_config` |
| `setup.json` | `setup_config` |
| `template-preset` action input | `template_name` |
| `include-feedback` action input | `include_feedback` |

---

## Operational checklist

### Server side

- [ ] `AUTOGRADER_INTEGRATION_TOKEN` is set and non-empty
- [ ] API is reachable from GitHub Actions runners (`/api/v1/health` returns 200)
- [ ] Grading config created via `POST /api/v1/configs` — note the `id`
- [ ] Config includes at least one entry in `languages`

### Workflow side

- [ ] `AUTOGRADER_CLOUD_URL` secret set on repository/org
- [ ] `AUTOGRADER_CLOUD_TOKEN` secret set on repository/org
- [ ] `execution-mode: "external"` in the workflow
- [ ] `grading-config-id` matches the server config `id`
- [ ] `template-preset` set to any valid value (parser requirement)
- [ ] `permissions: write-all` removed (not needed)

---

## Smoke test

### 1. Verify Cloud connectivity

```bash
# Health check
curl https://your-cloud-url/api/v1/health

# Verify config exists and token works
curl -H "Authorization: Bearer $TOKEN" \
  https://your-cloud-url/api/v1/configs/id/42
```

### 2. Trigger a test run

Push a known-good submission. Verify:

- Action completes successfully
- Result appears: `GET /api/v1/submissions/config/42`

### 3. Verify failure recording

Push a broken submission. Verify:

- Action exits with code 1
- A `status: "failed"` record exists on the Cloud

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CloudClientError: HTTP 401` | Wrong token | Regenerate and sync `AUTOGRADER_INTEGRATION_TOKEN` ↔ `AUTOGRADER_CLOUD_TOKEN` |
| `CloudClientError: HTTP 404` | Wrong config ID | Verify with `GET /api/v1/configs` |
| `ValueError: Language 'X' not supported` | Language not in config's `languages` list | Add to cloud config or fix `submission-language` |
| `ValueError: Config has no languages defined` | Empty `languages` in cloud config | Add at least one language |
| Action exits 1 but no result on Cloud | Config fetch failed | Check logs for network/auth error |
| Server returns 503 | `AUTOGRADER_INTEGRATION_TOKEN` not set | Set env var and restart API |
| `CloudConnectionError` after retries | Server unreachable or persistent 5xx | Check server health and network |

### Retry behaviour

The Cloud client uses exponential backoff for transient errors:

- **4xx responses** → immediate failure (no retry)
- **5xx / network errors** → up to 3 retries with delays of 1s, 2s, 4s
- Timeouts: 10s connect, 30s read

---

## See also

- [Configuration Reference](configuration.md) — all inputs and validation rules
- [Overview](README.md) — general architecture
- [API Documentation](../API.md) — Cloud API endpoints
