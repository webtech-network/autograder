# GitHub Action — Overview

The Prisma Autograder ships as a Docker-based GitHub Action that grades student submissions automatically inside CI workflows. It is designed for **GitHub Classroom** but works with any repository that follows the expected directory layout.

---

## How it works

```
Student pushes code  →  GitHub Action triggers  →  Autograder grades  →  Results exported
```

The Action:

1. Reads student files from the `submission/` directory.
2. Loads grading configuration (from repo files **or** from the Autograder Cloud).
3. Builds and executes the full grading pipeline (criteria tree → sandbox → grading → feedback).
4. Exports the result (to GitHub Classroom check run **or** to the Autograder Cloud API).

---

## Execution modes

The Action supports two mutually exclusive modes:

| Mode | Config source | Result destination | Use case |
|------|--------------|-------------------|----------|
| **`repo`** (default) | JSON files in `submission/.github/autograder/` | GitHub check run + `relatorio.md` | Config lives in the student repo |
| **`external`** | Autograder Cloud API | Autograder Cloud API | Centralised config managed by the instructor |

### Repo mode flow

```
submission/.github/autograder/criteria.json  ──┐
submission/.github/autograder/feedback.json  ──┤──► build_pipeline()  ──► run  ──► GitHub Check Run
submission/.github/autograder/setup.json     ──┘                                    └► relatorio.md
```

### External mode flow

```
Autograder Cloud  ──GET /api/v1/configs/id/{id}──► build_pipeline()  ──► run  ──► POST /api/v1/submissions/external-results
```

If grading fails in external mode, a `status: "failed"` payload is submitted before the Action exits non-zero.

---

## Repository contract

Your workflow **must** checkout the repository into a directory named `submission`:

```yaml
- uses: actions/checkout@v4
  with:
    path: submission
```

### Repo mode file requirements

```
submission/
├── .github/
│   └── autograder/
│       ├── criteria.json    # Required — grading rubric
│       ├── feedback.json    # Optional (can be {})
│       └── setup.json       # Optional (can be {})
├── index.html               # Student files (read recursively)
├── styles.css
└── app.js
```

### External mode file requirements

Only the student source files are needed. No `.github/autograder/` directory required — config comes from the cloud.

```
submission/
├── main.py                  # Student files (read recursively)
└── utils.py
```

!!! note
    The Action skips `.git/` and `.github/` directories when collecting student files.

---

## Internal architecture

| Component | Responsibility |
|-----------|---------------|
| `action.yml` | Declares Action inputs/outputs; maps inputs to container environment variables |
| `Dockerfile.actions` | Builds the runtime Docker image (Python 3.10 + Node.js 20) |
| `github_action/entrypoint.sh` | Validates required env vars; executes Python entrypoint with CLI flags |
| `github_action/main.py` | Parses arguments, validates options, reads submission files, starts grading |
| `github_action/github_action_service.py` | Builds pipeline from config; handles GitHub/Cloud export |
| `github_action/cloud_client.py` | HTTP client for Cloud API with retry + exponential backoff |
| `github_action/cloud_exporter.py` | Builds result payload and submits to Cloud API |
| `github_action/github_classroom_exporter.py` | Reports score to GitHub Classroom check run |

### Docker image

The Action runs inside a Docker container built from `Dockerfile.actions`:

- **Base:** `python:3.10-slim`
- **Includes:** Node.js 20 (for JavaScript template grading), `tree`, `curl`
- **Entry:** `/app/github_action/entrypoint.sh`

---

## Supported template presets

| Preset | Language | Description |
|--------|----------|-------------|
| `webdev` | HTML/CSS/JS | Web development assignments (DOM, CSS, structure) |
| `input_output` | Python, Java, C++ | Standard I/O programs with test cases |
| `api` | Any | REST API endpoint testing |

!!! warning
    `template-preset: custom` is currently **not supported** by the Action and will cause an immediate exit.

---

## Feedback modes

| Mode | Requires | Description |
|------|----------|-------------|
| `default` | Nothing extra | Rule-based feedback from the grading pipeline |
| `ai` | `openai-key` | AI-generated feedback using OpenAI API |

When `include-feedback: "true"` (repo mode), the Action commits feedback as `relatorio.md` to the repository.

---

## Quick reference

Minimal repo-mode workflow:

```yaml
- uses: webtech-network/autograder@main
  with:
    template-preset: "webdev"
    feedback-type: "default"
    include-feedback: "true"
```

Minimal external-mode workflow:

```yaml
- uses: webtech-network/autograder@main
  with:
    execution-mode: "external"
    grading-config-id: "42"
    autograder-cloud-url: ${{ secrets.AUTOGRADER_CLOUD_URL }}
    autograder-cloud-token: ${{ secrets.AUTOGRADER_CLOUD_TOKEN }}
    feedback-type: "default"
    template-preset: "input_output"
```

---

## Next steps

- [Configuration Reference](configuration.md) — all inputs, outputs, secrets, and permissions
- [Quick Start Guide](quick-start.md) — step-by-step setup for both modes
- [External Mode](external-mode.md) — deep dive into cloud-based grading
