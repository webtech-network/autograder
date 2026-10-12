# Assessment files and context

Adapters collect and validate submission files. Every criterion uses the same
engine selection policy, including ordinary assessment and AI prompt construction.
No criterion disappears because its selected files are absent or out of scope.

A criterion's optional `file` names an exact relative submission path. That file
must exist, match the evaluator's supported source type, and belong to
`evaluation_scope.scoped_files` when scope is present. Conflicts produce
`FILE_TARGET_CONFLICT`; missing required inputs produce `REQUIRED_FILE_MISSING`.
Both fail the execution with null score/tree before that criterion is assessed.
An explicit target is never silently replaced with another file.

Without `file`, assessment selects scoped files, or all files when scope is
absent, then filters the evaluator's declared extensions. Selection is sorted
by relative filename, so upload/dictionary order cannot select a different file.
HTTP requires a nonempty scope naming submitted files. Trusted Python callers
may supply an empty scope; it selects no assessment files, so evaluators requiring
files fail explicitly. Scope does not remove context or execution dependencies.

| Evaluator contract | Inputs |
| --- | --- |
| Default trusted evaluator | Zero or more selected files of any type |
| HTML, CSS, single-file JavaScript checks | Exactly one matching file; use `file` when several match |
| `forbidden_import`, `forbidden_keyword` | One or more source files matching the submission language |
| Multi-file CSS/framework checks | Exact files named by their `html_file`, `css_file`, `js_file` parameters; missing files fail |
| I/O and project-structure checks | Whole submission when no explicit target is supplied; scope is available separately |
| HTTP/API checks | Zero files; assessment depends on the endpoint |

`AMBIGUOUS_FILE_TARGET` means a single-file check matched several files.
`UNSUPPORTED_FILE_TYPE` means an explicit target does not match its evaluator.
These are required assessment failures, never silent zero scores. All accepted
files remain in `context_files` for trusted evaluators and in sandbox input.
AI prompt builders receive selected `files` and complete `context_files`; providers
receive the complete submission as context. Each prompt identifies its assessed
files. Context files are not automatically additional assessment targets.

Static source declarations are positive extension lists: Python `.py`, Java
`.java`, Node `.js`/`.mjs`/`.cjs`, C `.c`/`.h`, and C++ `.cpp`/`.cc`/`.cxx`/`.hpp`/`.h`.
Headers use the selected C/C++ language. Documents and configuration are context,
never parsed with a code grammar. `forbidden_keyword` parses only when executing
an active structural rule. Its cache belongs to one grading traversal and is
keyed by actual source content and grammar. Other selected static, HTML, I/O and
AI checks do no AST work. Parsing/provider availability failures remain required
capability failures. No performance improvement is claimed without measurement.

`SubmissionFile.metadata` remains opaque. Selected file objects retain their
metadata and `changed_lines`; `file_metadata` contains selected files only.
`changed_lines=None` means no line information was supplied; an empty set means
line information was supplied with no changed lines. Built-in assessments inspect
whole selected files. They do not promise changed-line-only scoring.

## Mixed source/context example

The same definition works with HTTP and Actions:

```json
{
  "schema_version": "1.0",
  "templates": ["static_analysis"],
  "languages": ["python"],
  "criteria": {"base": {"weight": 100, "tests": [{
    "id": "no-loops", "type": "forbidden_keyword", "name": "No loops",
    "file": "main.py", "parameters": {"forbidden_keywords": ["for_loop"]}
  }]}}
}
```

For HTTP `POST /api/v1/submissions`, create/activate a configuration with that
definition and assignment alias `python-assignment`, then send:

```json
{
  "external_assignment_id": "python-assignment",
  "external_user_id": "student-42",
  "username": "student",
  "files": [
    {"filename": "main.py", "content": "x = 1\n"},
    {"filename": "README.md", "content": "Assignment instructions\n"},
    {"filename": "helper.py", "content": "y = 2\n"}
  ],
  "evaluation_scope": {"scoped_files": ["main.py"]}
}
```

For Actions, put `main.py`, `helper.py`, and `README.md` in `submission/` and save
the same definition as `.github/autograder/definition.json`:

```yaml
steps:
  - uses: actions/checkout@v4
  - uses: webtech-network/autograder@main
    with:
      definition-path: .github/autograder/definition.json
      submission-root: submission
```

Actions collects the root's accepted text files and does not expose an evaluation
scope input. The definition's explicit `file: "main.py"` limits assessment in both
hosts; `helper.py` and `README.md` remain context and execution input.

## Trusted Python migration

Remove the unused `required_file`/`required_file_type` properties. Optional
`TestFunction` declarations are `file_extensions`, `minimum_files`,
`maximum_files`, `source_files_only`, `uses_context_files`, and `file_parameters`.
Defaults allow zero or more scoped files without a type restriction. Set
`maximum_files = 0` for endpoint-only checks; set matching extensions and minimum
and maximum of one for single-file checks. Avoid implementing declarations that
an evaluator does not need. The former internal structural pipeline step,
result container and accessor have been removed; static evaluators use the local
lazy cache. The version 1 JSON shape is unchanged.
