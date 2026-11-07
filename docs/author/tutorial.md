# Tutorial: your first three assignments

This tutorial builds three complete assignments, from an empty file to a rubric
that grades real submissions:

1. [a Python program that reads input](#1-a-python-program-that-reads-input),
2. [a web page with HTML, CSS and JavaScript](#2-a-web-page), and
3. [one exercise solved in two compiled languages](#3-one-exercise-two-compiled-languages).

Each assignment is checked in under
[`examples/tutorial/`](https://github.com/webtech-network/autograder/blob/main/examples/tutorial/python-io/definition.json)
with a good and a bad student submission. The test suite grades every one of
them in real sandboxes on each change, so the scores on this page are the scores
the autograder gives.

## What you write

An assignment is one JSON document, the *grading definition*. You write it once
and every submission is graded against it:

| Field | What it says |
| --- | --- |
| `schema_version` | Always `"2.0"`. |
| `languages` | The languages a student may submit in. |
| `criteria` | What is checked and how much each check is worth: the rubric. |
| `preparation` | Files the submission must contain and commands that build it. |
| `feedback` | Whether students get a written report. |

Every check in `criteria` is a *criterion*:

| Field | Meaning |
| --- | --- |
| `id` | A stable name for the criterion, unique in the definition. Results, feedback links and comparisons use it, so keep it when you reword the rest. |
| `type` | The evaluator that runs the check. The [evaluator reference](../reference/evaluators.md) lists them all with their parameters. |
| `name` | What the student reads in the report. |
| `parameters` | The evaluator's settings (`{}` when it has none). |
| `weight` | Optional; how much it counts relative to its siblings (default 100). |

You never need to write a field you are happy to leave at its default. The
[definition reference](../reference/definition.md) lists every field.

## 1. A Python program that reads input

> **Assignment.** Write `main.py`. It reads two whole numbers, one per line, and
> prints their sum. If an input is not a whole number, it prints a message
> instead of crashing. Do not use `eval`.

### Check the output

The `input_output` template runs the student's program in a sandbox. Its
`expect_output` evaluator sends `inputs` to standard input, one per line, and
compares what the program prints with `expected_output`. Trailing spaces and
line-ending differences are ignored; anything else must match exactly.

<!-- fragment: examples/tutorial/python-io/definition.json -->
```json
{
  "id": "sum-positive",
  "type": "expect_output",
  "name": "Adds two positive numbers",
  "parameters": {
    "program_command": "python3 main.py",
    "inputs": ["2", "3"],
    "expected_output": "5"
  }
}
```

`program_command` is how the program starts. It runs without a shell, once
for every criterion that uses it, from the folder that holds the submission.
Each run may take 30 seconds; a crash, a nonzero exit status or a timeout
scores 0 for that criterion, and the student sees why.

### Group the checks the way you would grade by hand

A rubric reads better in groups. A *subject* holds criteria (and further
subjects) under a heading the student sees: its `name`, as for a criterion. Its
`weight` works like a criterion's too. Here two output checks make up
the "Adds two numbers" subject, and a `dont_fail` check, which only requires
the program to finish without crashing, makes up "Handles bad input". The
subject weights, 80 and 20, say that adding correctly is worth four times as
much as surviving bad input.

<!-- fragment: examples/tutorial/python-io/definition.json -->
```json
{
  "criteria": {
    "base": {
      "subjects": [
        {
          "name": "Adds two numbers",
          "weight": 80,
          "tests": [
            {
              "id": "sum-positive",
              "type": "expect_output",
              "name": "Adds two positive numbers",
              "parameters": {
                "program_command": "python3 main.py",
                "inputs": ["2", "3"],
                "expected_output": "5"
              }
            }
          ]
        },
        {
          "name": "Handles bad input",
          "weight": 20,
          "tests": [
            {
              "id": "text-input",
              "type": "dont_fail",
              "name": "Does not crash on text input",
              "parameters": {"program_command": "python3 main.py", "inputs": ["abc"]}
            }
          ]
        }
      ]
    }
  }
}
```

### Deduct points for a forbidden construct

"Do not use `eval`" is a rule, not a skill, so it belongs in the `penalty`
category. A penalty criterion is written as the behaviour you *want*: the
`forbidden_keyword` check scores 100 when the student did not call `eval`, and
the penalty deducts only what is missing from 100, at most the category's
`max_points`. [Scores](scoring.md#penalty) explains the rule and the
arithmetic. Any evaluator in the reference can be used: its `type` is all the
definition names.

### The complete definition

`preparation` names `main.py` as a required file: a submission without it is
not graded at all (no score, not even 0) and the student is told which file is
missing. `feedback` turns on the student report.

```json
{
  "schema_version": "2.0",
  "languages": ["python"],
  "criteria": {
    "base": {
      "subjects": [
        {
          "name": "Adds two numbers",
          "weight": 80,
          "tests": [
            {
              "id": "sum-positive",
              "type": "expect_output",
              "name": "Adds two positive numbers",
              "parameters": {
                "program_command": "python3 main.py",
                "inputs": ["2", "3"],
                "expected_output": "5"
              }
            },
            {
              "id": "sum-negative",
              "type": "expect_output",
              "name": "Adds a negative number",
              "parameters": {
                "program_command": "python3 main.py",
                "inputs": ["-7", "4"],
                "expected_output": "-3"
              }
            }
          ]
        },
        {
          "name": "Handles bad input",
          "weight": 20,
          "tests": [
            {
              "id": "text-input",
              "type": "dont_fail",
              "name": "Does not crash on text input",
              "parameters": {"program_command": "python3 main.py", "inputs": ["abc"]}
            }
          ]
        }
      ]
    },
    "penalty": {
      "max_points": 20,
      "tests": [
        {
          "id": "no-eval",
          "type": "forbidden_keyword",
          "name": "Does not call eval",
          "parameters": {"forbidden_keywords": ["eval_call"]}
        }
      ]
    }
  },
  "preparation": {"languages": {"python": {"required_files": ["main.py"]}}},
  "feedback": {"enabled": true}
}
```

The [good submission](https://github.com/webtech-network/autograder/blob/main/examples/tutorial/python-io/good/main.py)
scores 100. The [bad one](https://github.com/webtech-network/autograder/blob/main/examples/tutorial/python-io/bad/main.py)
adds correctly with `eval`, so it keeps the 80 points of "Adds two numbers",
loses the 20 of "Handles bad input" because text input crashes it, and the
penalty takes 20 more: it scores 60. [Read a result](results.md) shows its
outcome and report.

## 2. A web page

> **Assignment.** Build a page listing your favourite books: `index.html`,
> `style.css` and `script.js`. Use semantic HTML, give every image alt text,
> lay the books out with flexbox and add a book from JavaScript. Extra credit
> for a layout that adapts to small screens. Keep styles out of the HTML.

The `webdev` template reads the files; nothing is executed, so no sandbox is
needed and grading is fast. Each HTML, CSS or JavaScript check reads the one
file of its type in the submission. When a submission has several, name the
one to check in the criterion's `file`.

Every definition declares at least one language; for a web page use `node`.
Listing all three files in `required_files` reports every missing file in one
message before any check runs.

This rubric adds the two optional categories:

* `bonus` criteria add extra credit. Its `max_points` is the most it can add: 10
  points here.
* `penalty` criteria take points away. Its `max_points` is the most it can take.

```json
{
  "schema_version": "2.0",
  "languages": ["node"],
  "criteria": {
    "base": {
      "subjects": [
        {
          "name": "HTML structure",
          "weight": 40,
          "tests": [
            {
              "id": "main-heading",
              "type": "has_tag",
              "name": "Has a main heading",
              "parameters": {"tag": "h1"}
            },
            {
              "id": "semantic-tags",
              "type": "uses_semantic_tags",
              "name": "Uses semantic tags",
              "parameters": {}
            },
            {
              "id": "image-alt",
              "type": "check_all_images_have_alt",
              "name": "Every image has alt text",
              "parameters": {}
            }
          ]
        },
        {
          "name": "Styling",
          "weight": 30,
          "tests": [
            {
              "id": "stylesheet",
              "type": "check_css_linked",
              "name": "Links a stylesheet",
              "parameters": {}
            },
            {
              "id": "flexbox",
              "type": "check_flexbox_usage",
              "name": "Lays out with flexbox",
              "parameters": {}
            }
          ]
        },
        {
          "name": "Interactivity",
          "weight": 30,
          "tests": [
            {
              "id": "dom-updates",
              "type": "js_uses_dom_manipulation",
              "name": "Adds elements from JavaScript",
              "parameters": {
                "methods": ["createElement", "appendChild"],
                "required_count": 2
              }
            }
          ]
        }
      ]
    },
    "bonus": {
      "max_points": 10,
      "tests": [
        {
          "id": "responsive",
          "type": "check_media_queries",
          "name": "Adapts to small screens",
          "parameters": {}
        }
      ]
    },
    "penalty": {
      "max_points": 10,
      "tests": [
        {
          "id": "no-inline-styles",
          "type": "check_no_inline_styles",
          "name": "Keeps styles out of the HTML",
          "parameters": {}
        }
      ]
    }
  },
  "preparation": {
    "languages": {"node": {"required_files": ["index.html", "style.css", "script.js"]}}
  },
  "feedback": {"enabled": true}
}
```

The [good page](https://github.com/webtech-network/autograder/blob/main/examples/tutorial/web-page/good/index.html)
earns 100 and the bonus, but a score never exceeds 100. The
[bad page](https://github.com/webtech-network/autograder/blob/main/examples/tutorial/web-page/bad/index.html)
scores 23.67; [Scores](scoring.md#a-worked-example) works the number out
criterion by criterion.

## 3. One exercise, two compiled languages

> **Assignment.** Read a whole number *n* (0 ≤ *n* ≤ 20) and print *n*!. Submit
> `main.c` or `Main.java`. Extra credit if 20! is right.

When `languages` lists more than one language, each submission names the one
it uses (the HTTP API's `language` field, the GitHub Action's
`submission-language` input). The definition gives each language what it
needs:

* `preparation.languages` holds the required files and the *setup commands*
  of each language. Setup commands run once, in order, before any criterion:
  this is where code is compiled. If one fails, the submission is not graded
  and the student sees the step's name, its exit status and an excerpt of the
  compiler's output.
* `program_command` maps each language to the command that runs the compiled
  program. A map must name every language in `languages`.

Only the selected language's preparation and command are used.

```json
{
  "schema_version": "2.0",
  "languages": ["c", "java"],
  "criteria": {
    "base": {
      "tests": [
        {
          "id": "zero",
          "type": "expect_output",
          "name": "0! is 1",
          "parameters": {
            "program_command": {"c": "./factorial", "java": "java Main"},
            "inputs": ["0"],
            "expected_output": "1"
          }
        },
        {
          "id": "five",
          "type": "expect_output",
          "name": "5! is 120",
          "parameters": {
            "program_command": {"c": "./factorial", "java": "java Main"},
            "inputs": ["5"],
            "expected_output": "120"
          }
        },
        {
          "id": "ten",
          "type": "expect_output",
          "name": "10! is 3628800",
          "parameters": {
            "program_command": {"c": "./factorial", "java": "java Main"},
            "inputs": ["10"],
            "expected_output": "3628800"
          }
        }
      ]
    },
    "bonus": {
      "max_points": 10,
      "tests": [
        {
          "id": "twenty",
          "type": "expect_output",
          "name": "20! does not overflow",
          "parameters": {
            "program_command": {"c": "./factorial", "java": "java Main"},
            "inputs": ["20"],
            "expected_output": "2432902008176640000"
          }
        }
      ]
    }
  },
  "preparation": {
    "languages": {
      "c": {
        "required_files": ["main.c"],
        "setup_commands": [
          {"name": "Compile main.c", "command": "gcc main.c -o factorial"}
        ]
      },
      "java": {
        "required_files": ["Main.java"],
        "setup_commands": [{"name": "Compile Main.java", "command": "javac Main.java"}]
      }
    }
  },
  "feedback": {"enabled": true}
}
```

The [good C](https://github.com/webtech-network/autograder/blob/main/examples/tutorial/compiled/good/main.c)
and [good Java](https://github.com/webtech-network/autograder/blob/main/examples/tutorial/compiled/good/Main.java)
solutions score 100. The [bad ones](https://github.com/webtech-network/autograder/blob/main/examples/tutorial/compiled/bad/main.c)
print 0 for 0! and overflow on 20!, so they pass two of the three required
criteria and earn no bonus: 66.67.

## What the examples score

| Submission | Language | Score |
| --- | --- | --- |
| `examples/tutorial/python-io/good` | `python` | **100** |
| `examples/tutorial/python-io/bad` | `python` | **60** |
| `examples/tutorial/web-page/good` | `node` | **100** |
| `examples/tutorial/web-page/bad` | `node` | **23.67** |
| `examples/tutorial/compiled/good` | `c` | **100** |
| `examples/tutorial/compiled/bad` | `c` | **66.67** |
| `examples/tutorial/compiled/good` | `java` | **100** |
| `examples/tutorial/compiled/bad` | `java` | **66.67** |

## Next steps

* [Test your rubric](testing.md) against your own good and bad submissions
  before students see it.
* [Scores](scoring.md) explains weights, bonus and penalty precisely.
* [Languages, files and setup](preparation.md) covers fixtures and commands.
* [Student feedback](feedback.md) shapes the report.
* Publish the definition through the [HTTP API](../getting-started/first-grading-workflow.md)
  or a repository's [GitHub Action](../github_action/quick-start.md).
