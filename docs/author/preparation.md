# Languages, files and setup

`languages` and `preparation` say what a submission must contain and what
happens before any criterion is checked. The
[definition reference](../reference/definition.md#preparation) lists every
field; this page explains how to use them.

## Languages

`languages` lists what a student may submit in: `python`, `java`, `node`,
`cpp` or `c`. With one language every submission uses it. With several, each
submission names its language (the HTTP API's `language` field, the GitHub
Action's `submission-language` input); a missing or unlisted language fails
the grading and the student is told the allowed languages.

`preparation.languages` holds what each language needs, and only the
submission's language is used:

* `required_files`: paths the submission must contain. When one is missing,
  the submission is not graded (no score, not even 0) and the student is told
  which files are missing, before any code runs.
* `setup_commands`: steps run once, in order, before the criteria, such as
  compiling.

## Commands

A `program_command` (in `expect_output`, `dont_fail` and
`expect_file_artifact`) and every setup `command` are split into a program
and its arguments with shell-style quoting and run **without a shell**, from
the folder holding the submission. Each process may run for 30 seconds and
reads only the input its criterion sends.

Because there is no shell, `&&`, `|`, `;` and `>` are not operators. A
definition that uses one standalone is rejected with `SHELL_OPERATOR` at the
exact field. Compile in a setup command, once, and run the result in
`program_command`, which runs again for every criterion. Write
`sh -c '...'` only for a real per-criterion pipeline.

A `program_command` takes three forms:

| Form | Example | Runs for a `java` submission |
| --- | --- | --- |
| One command for every language | `"python3 calculator.py"` | `python3 calculator.py` |
| A map naming every language in `languages` | `{"c": "./factorial", "java": "java Main"}` | `java Main` |
| `"CMD"`, the conventional default | `"CMD"` | `java Main` |

`CMD` runs `python3 main.py`, `java Main`, `node index.js`, or `./a.out` for C
and C++. It never guesses from the submitted file names, so prefer an explicit
command when your entry point differs.

## When setup fails

A setup command that exits with a nonzero status, or runs past 30 seconds,
stops the grading: the submission gets no score and the student sees the
step's `name`, its exit status and an excerpt of its output, typically the
compiler errors. When that output could reveal something private, such as a
hidden test harness you compile alongside the submission, set
`private_output` on the step; the student then sees only the name and status:

<!-- fragment: examples/tutorial/compiled/definition.json -->
```json
{
  "preparation": {
    "languages": {
      "c": {
        "required_files": ["main.c"],
        "setup_commands": [
          {"name": "Compile main.c", "command": "gcc main.c -o factorial"},
          {"name": "Compile the hidden tests", "command": "gcc -c tests.c", "private_output": true}
        ]
      }
    }
  }
}
```

A failing program during a criterion is different: a crash, a nonzero exit or
a timeout there scores 0 for that criterion and grading continues.

## Teacher-provided files

`preparation.fixtures` copies files you provide, such as input data or a test
harness, into the sandbox before the setup commands run. `reference` names the
file in your host's fixture store, `path` is where it appears, under
`/tmp/app/`, separately from the student's files:

<!-- fragment: examples/tutorial/python-io/definition.json -->
```json
{
  "preparation": {
    "fixtures": [{"reference": "fixture-io/numbers.txt", "path": "numbers.txt", "read_only": true}]
  }
}
```

A program reads that file as `/tmp/app/numbers.txt`. The
[fixture example](https://github.com/webtech-network/autograder/blob/main/examples/assets/fixture_io/definition.json)
is a complete assignment that does. Fixtures are read from the store on every
grading, so replacing a file takes effect for the next submission. A reference
the store does not have fails the grading with `PREPARATION_ERROR`. Where the
store is and who can write to it is host configuration: see
[configuration](../operate/configuration.md).

## Time limits

A definition must fit the time a host grants one grading. Each I/O criterion
and each setup command counts as 30 seconds plus 2, and every grading adds 60
seconds; the shipped default host grants 900 seconds, enough for 26 processes.
A definition that needs more is rejected when you validate or publish it, with
`EXECUTION_BUDGET_EXCEEDED`; split the assignment or ask the operator for a
longer `running_timeout`.

## Language-specific checks

Some evaluators understand only certain languages; the
[evaluator reference](../reference/evaluators.md) lists them per evaluator,
and a definition whose languages an evaluator cannot handle is rejected.
`forbidden_keyword` knows these constructs, and a construct must exist in
every language the definition allows:

| Language | Constructs |
| --- | --- |
| `python` | `for_loop`, `while_loop`, `eval_call`, `exec_call` |
| `java` | `for_loop`, `while_loop` |
| `node` | `for_loop`, `while_loop`, `eval_call` |
| `cpp` | `for_loop`, `while_loop`, `do_while_loop` |
| `c` | `for_loop`, `while_loop`, `do_while_loop` |
