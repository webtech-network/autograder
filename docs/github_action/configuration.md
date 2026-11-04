# Action configuration reference

| Input | Default | Meaning |
|---|---|---|
| `execution-mode` | `repo` | `repo` loads a local definition; `external` fetches one |
| `definition-path` | `.github/autograder/definition.json` | Workspace-relative or absolute v1 JSON path; repo mode |
| `submission-root` | `.` | Workspace-relative or absolute readable directory of UTF-8 files |
| `submission-language` | omitted | Allowed canonical language; required with multiple choices |
| `locale` | `en` | `en` or `pt-br`; identical across modes |
| `submitter-id` | repository | Opaque owner of the graded work (e.g. Prisma student ID); never the workflow actor |
| `submitter-name` | ID / repository name | Display name of the submitter |
| `grading-config-id` | omitted | Positive configuration ID; required for external mode or cloud upload |
| `grading-config-revision` | omitted | Revision to attest in repo mode; lets a restricted attestation token publish without reading the configuration |
| `trusted-self-hosted-runner` | `false` | Allow publication from a reviewed self-hosted runner |
| `autograder-cloud-url` | omitted | Required for cloud fetch/upload/retry |
| `autograder-cloud-token` | omitted | Required cloud authentication secret; never grading identity |
| `upload-to-cloud` | `false` | Explicit post-grading cloud publication |
| `retry-delivery-path` | omitted | Saved `delivery.json`; skips configuration loading and evaluation |

The submission root defaults to ordinary `actions/checkout` output. `.git`,
`.github`, and `.autograder` directories are excluded. Empty roots, nonexistent
roots, and unreadable/non-UTF-8 files fail clearly. All other text files are
submission files; choose a narrower root for repositories containing binaries.
Configuration and preparation paths are relative to the selected submission root.

| Output | Meaning |
|---|---|
| `status` | `completed` or `failed`, written before cloud delivery |
| `score` | Finite authoritative score 0–100, only when completed |
| `result-path` | Workspace-relative `.autograder/outcome.json` |
| `submission-id` | Cloud submission ID after successful publication |
| `delivery-status` | `delivered`, `failed` or `uncertain` when publication was requested |

Identity, run provenance and the event/runner trust table are documented in
[identity and trust](trust.md). `student-name` was removed.

The canonical outcome includes the tree, definition provenance, UTC timestamps,
execution correlation ID, and separate feedback/comparison status. Public
pipeline internals are not a client contract. Keep scalar outputs small and
upload the result artifact with an explicit workflow step.

The old `result` base64 output, `total_score`, `template-preset`,
`custom-template`, `feedback-type`, `include-feedback`, `github-token`,
`app-token`, and `openai-key` inputs are removed. Templates and feedback policy
belong in the definition. Provider credentials belong in host environment
configuration (for example `OPENAI_API_KEY`), not grading identity.
