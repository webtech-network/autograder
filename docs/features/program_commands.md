# Program commands and multi-language assignments

One grading definition can accept several languages. The definition lists them
in `languages`; each submission is bound to exactly one of them (see
[Languages, runtimes, commands and parsers](../contracts/LANGUAGES.md)). The I/O
evaluators (`expect_output`, `dont_fail`, `expect_file_artifact`) then choose the
command for that bound language from their own `program_command` parameter.
The generic grader never reads `program_command`.

## The three forms

| Form | Example | Executed for a `java` submission |
| --- | --- | --- |
| String | `"python3 calculator.py"` | `python3 calculator.py` (the same command for every language) |
| Language map | `{"python": "python3 calc.py", "java": "java Calc"}` | `java Calc` |
| `CMD` placeholder | `"CMD"` | `java Main` |

A language map must cover every language in `languages`; otherwise compilation
fails with `MISSING_LANGUAGE_COMMAND` at `parameters.program_command`. Keys are
the canonical identifiers only (`python`, `java`, `node`, `cpp`, `c`).

`CMD` uses the one documented default table (`DEFAULT_COMMANDS` in
`autograder/models/abstract/execution_test.py`, next to `BaseExecutionTest`):

| Language | `CMD` runs |
| --- | --- |
| `python` | `python3 main.py` |
| `java` | `java Main` |
| `node` | `node index.js` |
| `cpp`, `c` | `./a.out` |

Nothing is inferred from submitted file names. Use a map when entry points
differ from these conventions.

## Complete multi-language example

```json
{
  "schema_version": "1.0",
  "templates": ["input_output"],
  "languages": ["python", "java", "cpp"],
  "criteria": {"base": {"weight": 100, "tests": [
    {"id": "sum", "type": "expect_output", "name": "Adds two numbers", "parameters": {
      "inputs": ["5", "3"], "expected_output": "8",
      "program_command": {"python": "python3 calculator.py", "java": "java Calculator", "cpp": "./calculator"}}}
  ]}},
  "preparation": {"languages": {
    "python": {"required_files": ["calculator.py"]},
    "java": {"required_files": ["Calculator.java"],
             "setup_commands": [{"name": "compile", "command": "javac Calculator.java"}]},
    "cpp": {"required_files": ["calculator.cpp"],
            "setup_commands": [{"name": "compile", "command": "g++ calculator.cpp -o calculator"}]}
  }}
}
```

Submissions to this definition must name `language` because more than one is
allowed. A single-language definition infers it.

Only the selected language's preparation runs. A language that is allowed but
has no runtime on the host fails with `CAPABILITY_UNAVAILABLE`, not as an invalid
language.

## Migration from `CommandResolver`

`autograder/services/command_resolver.py` was removed. Its unused
`DEFAULT_COMMANDS` table, the upper-case map-key alias and the file-name fallback
were unreachable through validated definitions, so `CMD` and map commands run
exactly as before. Trusted Python code that called `CommandResolver` should call
`BaseExecutionTest.resolve_command(program_command, evaluation)` or read
`DEFAULT_COMMANDS`.
