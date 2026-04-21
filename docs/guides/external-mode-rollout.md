# External mode — rollout guide

This guide is aimed at instructors and platform operators who want to adopt external mode for the first time, or migrate existing repo-mode workflows to it.

---

## Who is this for

- You manage a multi-repository classroom and want a single place to configure grading criteria.
- You want grading results stored centrally (in the Autograder Cloud database) rather than scattered across individual check runs.
- You are already running repo mode and want to migrate without disrupting active submissions.

---

## Migration guidance

### From repo mode

Existing repo-mode workflows **continue to work without any changes**. External mode is opt-in: a workflow only enters external mode when `execution-mode: "external"` is set.

You can run both modes side by side during a transition:

1. Leave existing repo-mode workflows untouched.
2. For new assignments, create a grading config on the Cloud and use the external-mode workflow template.
3. For existing assignments, migrate one at a time: create the equivalent Cloud config, update the workflow, and remove the `.github/autograder/` files from the student repo template.

### Config parity checklist

When converting a repo-mode config to a Cloud config:

| Repo-mode file | Cloud config field |
|----------------|--------------------|
| `criteria.json` | `criteria_config` |
| `feedback.json` | `feedback_config` |
| `setup.json` | `setup_config` |
| `template-preset` action input | `template_name` |
| `include-feedback` action input | `include_feedback` |

---

## New secrets required

For each repository (or at organisation level):

| Secret name | Value |
|-------------|-------|
| `AUTOGRADER_CLOUD_URL` | Base URL of your Autograder Cloud, e.g. `https://autograder.myschool.edu` |
| `AUTOGRADER_CLOUD_TOKEN` | Token matching `AUTOGRADER_INTEGRATION_TOKEN` on the server |

Generate the token once on the server and reuse it across all repositories:

```bash
openssl rand -hex 32
```

Set it as the `AUTOGRADER_INTEGRATION_TOKEN` environment variable on the server **before** starting the API. The server will fail to start the integration auth configuration if the variable is absent or empty.

---

## Operational checklist

### Server side

- [ ] `AUTOGRADER_INTEGRATION_TOKEN` is set and non-empty.
- [ ] The API is reachable from GitHub Actions runners (`https://your-cloud-url/api/v1/health` returns 200).
- [ ] Grading configuration created via `POST /api/v1/configs` — note the returned `id`.
- [ ] Config includes at least one entry in `languages`.

### Workflow side

- [ ] `AUTOGRADER_CLOUD_URL` secret is set on the repository (or organisation).
- [ ] `AUTOGRADER_CLOUD_TOKEN` secret is set on the repository (or organisation).
- [ ] `execution-mode: "external"` in the workflow.
- [ ] `grading-config-id` matches the `id` from the server.
- [ ] `template-preset` is set to any valid value (required by the argument parser, not used in external mode).
- [ ] `permissions: write-all` removed (not needed in external mode).

---

## Smoke test

Run the following smoke test after setup to verify the full integration works end-to-end before deploying to students.

### 1 — Verify the Cloud is reachable and configured

```bash
# Health check
curl https://your-cloud-url/api/v1/health

# Verify the config exists and token is accepted
curl -H "Authorization: Bearer $AUTOGRADER_CLOUD_TOKEN" \
     https://your-cloud-url/api/v1/configs/id/42
```

### 2 — Trigger a test run

Push a known-good submission to a test repository that has the external-mode workflow. Observe:

- Action completes without non-zero exit.
- Result appears on the Cloud:

```bash
curl https://your-cloud-url/api/v1/submissions/config/42
```

### 3 — Verify a failure is recorded

Trigger a run with a deliberately broken submission (e.g. syntax error). Verify:

- Action exits with code 1.
- A `status: "failed"` record appears under `GET /api/v1/submissions/config/42`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Action exits 1 with `401` in log | Wrong token | Regenerate and sync `AUTOGRADER_INTEGRATION_TOKEN` and `AUTOGRADER_CLOUD_TOKEN` |
| Action exits 1 with `404` in log | Wrong config id | Check `grading-config-id` against `GET /api/v1/configs` |
| Action exits 1 with `ValueError: Language 'X' not supported` | Language not in config | Add the language to the Cloud config or fix `submission-language` |
| Action exits 1 with `ValueError: Config has no languages defined` | Config `languages` is `[]` | Update the config to include at least one language |
| No result on Cloud after successful run | Config fetch succeeded but result post failed | Check Action log for error on the POST step |
| Server returns 503 on protected endpoints | `AUTOGRADER_INTEGRATION_TOKEN` not set on server | Set the env var and restart the API |

---

## See also

- [External mode deep-dive](../github_action/external-mode.md)
- [Configuration reference](../github_action/configuration.md)
- [API documentation](../API.md)
