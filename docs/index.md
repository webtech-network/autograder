# Autograder documentation

The Autograder grades student submissions against a rubric you write once, a
*grading definition*, and explains each grade to the student. It runs as an
HTTP service for many submissions or as a GitHub Action in the student's
repository. Start from what you want to do.

## Author: write and test an assignment

For teachers and teaching assistants.

1. [Tutorial: your first assignments](author/tutorial.md) builds a Python
   program, a web page and a compiled exercise in two languages, each with a
   good and a bad submission.
2. [Scores, bonus and penalty](author/scoring.md) explains how the score is
   computed and how to write penalty criteria.
3. [Languages, files and setup](author/preparation.md),
   [student feedback](author/feedback.md),
   [testing your rubric](author/testing.md) and
   [reading a result](author/results.md) cover the rest of the work.
4. The [evaluator reference](reference/evaluators.md) and
   [definition reference](reference/definition.md) list every check and field.

## Integrate: run grading from another system

For developers connecting an LMS, a course platform or a CI workflow.
[Run the HTTP service](getting-started/first-grading-workflow.md) for a first
submission, then read the [REST API](API.md) and the contracts it is built on,
starting with [definitions](contracts/DEFINITIONS.md),
[outcomes](contracts/OUTCOMES.md) and [authentication](contracts/AUTH.md).
The [GitHub Action](github_action/README.md) grades one repository per run.

## Extend: add an evaluator

For developers adding checks in Python.
[Adding an evaluator](architecture/extending.md) is the recipe with runnable
examples; [responsibilities and dependencies](architecture/overview.md) maps
who owns what in the code.

## Operate and contribute

For whoever runs the service or changes the code:
[deployment](operate/deployment.md), [configuration](operate/configuration.md),
[sandbox ownership and isolation](contracts/SANDBOX.md) and the
[development guide](guides/development.md).
