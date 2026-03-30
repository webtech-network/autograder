# Step 8: Export

## Purpose

The Export step sends the final grading score to an external system. This is used in contexts where the autograder needs to report results outside of its own database — for example, updating a student's score in a Redis-backed leaderboard or quota system.

## How It Works

1. **Extract data** — The step reads the `external_user_id` from the submission and the `final_score` from the Grade step result.
2. **Send to external system** — The `exporter_service.set_score(user_id, score)` call pushes the score to the configured backend.

Currently, the only implemented exporter is `UpstashDriver`, which stores scores in an Upstash Redis instance using the hash key `user:{username}` with a `score` field.

## Dependencies

| Step | What It Needs |
|------|---------------|
| **Grade** | The `final_score` from `GradeStepResult` |

## Input

| Source | Data |
|--------|------|
| Constructor | `exporter_service` — the service that handles external communication |
| Pipeline | `StepName.GRADE` → `GradeStepResult.final_score` |
| Pipeline | `pipeline_exec.submission.user_id` |

## Output

| Field | Type | Description |
|-------|------|-------------|
| `data` | `None` | No data is stored — the export is a side effect |
| `status` | `StepStatus.SUCCESS` | On successful export |

## Conditional Inclusion

This step is only added to the pipeline when `export_results=True` is passed to `build_pipeline()`. It is typically used in the GitHub Action workflow where scores need to be reported to GitHub Classroom via an intermediary store.

## Failure Scenarios

- External service unavailable (Redis connection error) → `StepStatus.FAIL` with error message.
- Missing environment variables for Upstash (`UPSTASH_REDIS_URL`, `UPSTASH_REDIS_TOKEN`) → connection failure.

Export failures do not affect the grading result — the score and feedback are already computed. However, the pipeline status will reflect the failure.

---

## Source

`autograder/steps/export_step.py` → `ExporterStep`

`autograder/services/upstash_driver.py` → `UpstashDriver`
