# Quick Start Guide

This guide walks you through setting up the Prisma Autograder GitHub Action from scratch in both execution modes.

---

## Repo mode — step by step

### 1. Create the grading config directory

In your assignment repository template, create:

```
.github/
└── autograder/
    ├── criteria.json
    ├── feedback.json
    └── setup.json
```

### 2. Define your criteria

Create `.github/autograder/criteria.json` with your grading rubric:

```json
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "html_structure",
        "weight": 60,
        "tests": [
          {
            "file": "submission/index.html",
            "name": "has_tag",
            "parameters": [
              { "name": "tag", "value": "header" },
              { "name": "required_count", "value": 1 }
            ]
          }
        ]
      },
      {
        "subject_name": "css_styling",
        "weight": 40,
        "tests": [
          {
            "file": "submission/styles.css",
            "name": "check_flexbox_usage"
          }
        ]
      }
    ]
  }
}
```

### 3. Configure feedback (optional)

Create `.github/autograder/feedback.json`:

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

### 4. Add the workflow

Create `.github/workflows/classroom.yml`:

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
```

!!! important
    The `path: submission` in the checkout step is **required**. The Action expects all files under `submission/`.

### 5. Add secrets (if using AI feedback)

If you want AI-powered feedback:

```yaml
      - name: Run Autograder
        uses: webtech-network/autograder@main
        with:
          template-preset: "webdev"
          feedback-type: "ai"
          include-feedback: "true"
          openai-key: ${{ secrets.ENGINE }}
```

Add your OpenAI API key as the repository secret `ENGINE`.

### 6. Verify

Push a commit and check:

- ✅ The workflow runs successfully
- ✅ The check run shows "Autograding Result" with the score
- ✅ `relatorio.md` appears in the repo (if feedback enabled)

---

## External mode — step by step

### 1. Set up the Autograder Cloud

Ensure your Cloud instance is running and accessible. Verify:

```bash
curl https://your-cloud-url/api/v1/health
```

### 2. Create a grading configuration

```bash
curl -X POST https://your-cloud-url/api/v1/configs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "input_output",
    "languages": ["python"],
    "include_feedback": true,
    "criteria_config": {
      "test_library": "input_output",
      "base": {
        "weight": 100,
        "subjects": [...]
      }
    },
    "feedback_config": { "general": { "show_score": true } },
    "setup_config": {}
  }'
```

Note the returned `id` (e.g. `42`).

### 3. Add repository secrets

| Secret | Value |
|--------|-------|
| `AUTOGRADER_CLOUD_URL` | `https://your-cloud-url` |
| `AUTOGRADER_CLOUD_TOKEN` | Your integration token |

### 4. Add the workflow

Create `.github/workflows/autograder.yml`:

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

### 5. Verify

Push a submission and check:

- ✅ The workflow completes without errors
- ✅ A result appears on `GET /api/v1/submissions/config/42`

---

## Demo repository

The **[`webtech-network/demo-autograder`](https://github.com/webtech-network/demo-autograder)** repository is a complete working example of repo-mode grading.

### What it demonstrates

- A fully configured `classroom.yml` workflow
- Real `criteria.json` for a web development assignment
- Feedback configuration
- Student submission files that get graded
- Generated `relatorio.md` feedback artifact

### Demo repository structure

```
demo-autograder/
├── .github/
│   ├── workflows/
│   │   └── classroom.yml          # Workflow definition
│   └── autograder/
│       ├── criteria.json           # Web dev grading rubric
│       ├── feedback.json           # Feedback display settings
│       └── setup.json              # Setup configuration
├── submission/
│   ├── index.html                  # Student HTML
│   ├── styles.css                  # Student CSS
│   └── app.js                      # Student JavaScript
└── relatorio.md                    # Generated feedback report
```

### Demo workflow

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

### Adapting for your course

1. Fork/copy the demo structure into your assignment template
2. Replace `criteria.json` with your rubric
3. Adjust `template-preset` to match your assignment type:
    - `"webdev"` — HTML/CSS/JS assignments
    - `"input_output"` — stdin/stdout programs (Python, Java, C++)
    - `"api"` — REST API testing
4. Keep the job named `grading` (required for check run export)
5. Adjust triggers to match your workflow (push, PR, manual dispatch)

---

## Common patterns

### GitHub Classroom integration

For GitHub Classroom, the autograder integrates with the classroom bot:

```yaml
if: github.actor != 'github-classroom[bot]'
```

This prevents the Action from running on the initial bot commit when creating student repos.

### Multiple assignment types

You can have different workflows for different assignments in the same org by varying `template-preset` and `criteria.json`:

=== "Web Dev assignment"

    ```yaml
    template-preset: "webdev"
    ```

=== "Python I/O assignment"

    ```yaml
    template-preset: "input_output"
    ```

=== "API assignment"

    ```yaml
    template-preset: "api"
    ```

### Localization

Set the `locale` input to control feedback language:

```yaml
locale: "pt-br"   # Portuguese (Brazil)
locale: "en"      # English (default)
```

---

## See also

- [Configuration Reference](configuration.md) — all inputs and outputs
- [External Mode](external-mode.md) — cloud-based grading deep dive
- [Overview](README.md) — architecture and concepts
- [Criteria Configuration Examples](../guides/criteria_configuration_examples.md) — writing rubrics
