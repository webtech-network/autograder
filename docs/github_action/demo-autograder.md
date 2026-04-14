# Demo walkthrough: webtech-network/demo-autograder

The repository **[`webtech-network/demo-autograder`](https://github.com/webtech-network/demo-autograder)** is the best reference for a working GitHub Classroom-style setup using this Action.

## Why this repo matters

It shows, in one place:

- a complete `classroom.yml` workflow;
- grading criteria and feedback config files;
- a realistic `submission/` codebase to grade;
- generated feedback artifact (`relatorio.md`).

## Key files in the demo

| File | Purpose |
|---|---|
| `.github/workflows/classroom.yml` | Defines workflow triggers and runs `webtech-network/autograder@main`. |
| `.github/autograder/criteria.json` | Defines rubric structure and test cases. |
| `.github/autograder/feedback.json` | Controls feedback display settings. |
| `.github/autograder/setup.json` | Optional setup file (can be empty). |
| `submission/` | Student files that the rubric evaluates. |

## How demo layout works with this Action

In the demo workflow, repository checkout uses:

```yaml
with:
  path: submission
```

That makes the config files available exactly where this Action expects them:

- `submission/.github/autograder/criteria.json`
- `submission/.github/autograder/feedback.json`
- `submission/.github/autograder/setup.json`

## Adapting the demo for your own course

1. Start from the demo workflow file and keep the checkout path as `submission`.
2. Replace `.github/autograder/criteria.json` with your assignment rubric.
3. Tune `.github/autograder/feedback.json` for your feedback strategy.
4. Keep the job named `grading` to match current check-run export behavior.
5. Add the `openai-key` secret only if you use `feedback-type: ai`.

## Common adaptations

- Change triggers (`push`, `pull_request`, `workflow_dispatch`) to match your class workflow.
- Switch `template-preset` between `webdev`, `api`, or `input_output` depending on assignment type.
- Keep feedback enabled during development (`include-feedback: "true"`) to inspect `relatorio.md`.

## Related documentation

- GitHub Action module overview: [README.md](README.md)
- Full input/output and runtime contract: [configuration.md](configuration.md)
