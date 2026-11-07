# Grading definition 2.0

The same normalized definition is accepted by Python, repository files, HTTP
configuration storage and external-result snapshots. [Decision record](DECISIONS.md)
and [terminal outcomes](OUTCOMES.md) describe the integration boundaries.

[JSON Schema](v1/grading-definition.schema.json) describes built-in authoring; the
generated [definition reference](../reference/definition.md) and
[evaluator reference](../reference/evaluators.md) render it field by field.
`compile_definition` adds registry, uniqueness, learning-reference and weighted-group
checks that JSON Schema cannot fully express, plus each evaluator's own semantic
checks (`validate_parameters`), such as built-in command coverage and AST-rule grammar.
Its normalized return value is the stored definition and the source of its hash.
Evaluator normalization is applied once, to raw authoring input. A stored canonical
snapshot is reloaded with `compile_snapshot`, which validates it (including every
evaluator contract and cross-field rule) without transforming its parameters, so a
snapshot's meaning and hash cannot drift when it is loaded again. Snapshot
parameters must list every contract field explicitly (`NON_CANONICAL_PARAMETERS`).

```json
{
  "schema_version": "2.0",
  "languages": ["python"],
  "criteria": {
    "base": {
      "tests": [{
        "id": "sum-small",
        "type": "expect_output",
        "name": "Add two numbers",
        "parameters": {
          "program_command": "python3 main.py",
          "inputs": ["10", "20"],
          "expected_output": "30"
        }
      }]
    }
  },
  "preparation": {
    "languages": {"python": {"required_files": ["main.py"]}}
  },
  "feedback": {"enabled": true, "mode": "default"}
}
```

## Normalization and validation

* Version is exactly `"2.0"`; a `"1.0"` definition fails with
  `UNSUPPORTED_SCHEMA_VERSION`, naming the [converter](#definitions-in-an-earlier-format).
* A criterion's `type` alone names its evaluator: built-in evaluator identifiers
  are unique across the built-in templates, and a definition lists no templates.
  Trusted Python templates passed as `templates={identifier: Template}` join the
  same resolution (an identifier equal to a built-in template's replaces it); a
  `type` that two templates provide fails with `AMBIGUOUS_EVALUATOR`, an unknown
  one with `UNKNOWN_EVALUATOR` and the closest identifier.
* Languages are distinct canonical `python`, `java`, `node`, `cpp`, `c`. Definition
  aliases/case variations are rejected. Submission transports may normalize case;
  a sole allowed language is inferred, multiple languages require selection.
* Every criterion has globally unique stable `id`, explicit evaluator `type`,
  display `name`, and required parameter object (empty `{}` for parameterless
  evaluators). Subjects are labelled with `name` too. Display labels may repeat;
  IDs stay stable across label edits.
* Structural unknown fields are rejected recursively. Metadata is the explicit
  JSON-valued extension area at definition, criteria, group and test levels.
  There is no `test_library`, positional parameter list, extra-key parameter
  encoding or type fallback to a display name.
* Evaluator contracts validate strict types, required values and defaults. The
  annotated keyword-only parameters of the evaluator's `execute` (or an explicit
  `config_schema`) generate discovery and parameter validation. Constraints come
  only from the evaluator (`Annotated[..., Field(...)]`); a plain `int` accepts
  negatives and a plain `str` accepts empty strings. The generic compiler never
  interprets a parameter name: equal names in different evaluators are unrelated.
  Known runtime names (`files`, `sandbox`, `session`, `evaluation`, language,
  locale, AI precomputed results, structural analysis, evaluation scope, file
  metadata, criterion ID) are rejected as authored parameters and as contract fields.
* `weight` is a ratio among siblings with one rule at every level: a finite
  nonnegative number (never a boolean or string), unbounded, default 100, on
  tests and subjects alike. All-zero sibling weights normalize equally. The base
  category has no weight: it is the 0–100 score. The optional bonus and penalty
  categories set `max_points` (0–100), the most points they add or subtract. A
  group needs tests or subjects; mixed groups require a finite `subjects_weight`
  in 0–100. A split on a homogeneous group is rejected. Both groups are assessed
  even when one contributes zero.
* Fields of format 1.0 (`templates`, a base `weight`, a bonus or penalty
  `weight`, `subject_name`) are rejected at their path with what replaces them,
  never ignored.
* A command is a nonempty string or a canonical language-keyed string map covering
  every allowed language. Existing `CMD` explicitly means conventional defaults:
  `python3 main.py`, `java Main`, `node index.js`, `./a.out` for C/C++; it does not
  infer filenames. Prefer explicit commands. Commands run without a shell, so a
  standalone unquoted shell operator (`&&`, `||`, `|`, `;`, `&`, `>`, `>>`, `<`,
  `2>`, `2>&1`, ...) in a `program_command` (or any of its language entries) or
  in a setup command fails with `SHELL_OPERATOR` at that exact path. Compile in
  `preparation.languages.<language>.setup_commands`, one step per command, never
  in `program_command`, which runs once per test (in gVisor, `javac` costs
  roughly three times a `java` run). Quoted or escaped operators (`'>'`, `\|`)
  are literal arguments; use `sh -c '...'` only for a real per-test pipeline.
  Every I/O evaluator takes its standard input as `inputs`, a list of lines each
  sent with a trailing newline (`[]` sends nothing); `input` is rejected. Artifact paths are normalized relative submission paths;
  modes are `exact`, `contains`, `regex`; invalid regex is rejected before execution.
* A definition is rejected with `DEFINITION_TOO_LARGE` when its snapshot plus
  its worst-case outcome exceeds 24 MiB (about 465 criteria with short
  parameters). This keeps every attestation within the hosts' request limit.
  See [OUTCOMES.md](OUTCOMES.md#size-bounds).
* AST keywords must be supported in every allowed language. Custom ast-grep rules
  must compile for each language before acceptance. AI algorithm names are stripped
  and must remain nonempty. Repeated AI evaluator uses have independent IDs.
* No criterion's result may be independent of the submission because a parameter
  was omitted. Presence thresholds (`required_count`, and `min_items` for array items)
  default to 1 and reject 0; lists of things to find (`has_class.class_names`,
  `js_uses_dom_manipulation.methods`) and `forbidden_import.forbidden_imports` name
  at least one nonempty item; `forbidden_keyword` needs a keyword or a custom rule
  (`EMPTY_FORBIDDEN_LIST`). Prohibition and limit checks, which pass when what they
  look for is absent, publish the reason as `absence_check` in the
  [catalog](CATALOG.md). A contract test runs every catalog evaluator with only its
  required parameters on an irrelevant project and fails if a presence check passes.

Defaults are explicit in compiled JSON: preparation has empty language/fixture
collections; feedback is disabled with default mode/preferences; test and subject
weights are 100; metadata is empty. Optional `file`, bonus/penalty, tests/subjects and split
values normalize to null where omitted. Required fields and preparation/feedback
cannot be null. Optional criterion `file: null` means use all relevant files.

The hash is SHA-256 over normalized JSON, sorted keys, compact separators,
UTF-8, no ASCII escaping and no NaN. Object key order and omitted defaults do not
change the hash; criterion order, parameters, labels and metadata do. Criterion
IDs give comparison identity; hash equality gives complete definition equality.
A stored snapshot keeps the hash of the format it was written in: a 1.0 snapshot
bound to an outcome before format 2.0 is verified by hashing it as stored
(`snapshot_hash`), and its outcome's `provenance.schema_version` says `"1.0"`.

## Preparation and feedback

Preparation contains `languages` keyed by allowed language. Each language has
unique relative `required_files` and `setup_commands` with nonempty `name` and
`command`, and an optional strict boolean `private_output` (default `false`, and
omitted from the canonical snapshot while `false`). When a step fails, the
student sees its `name`, its exit code and an excerpt of its output; set
`private_output: true` on a step whose output could reveal private content, such
as compiling a hidden test harness, to show only the name and exit code
([OUTCOMES.md](OUTCOMES.md#explained-submission-failures)). Fixtures have logical `reference`, relative fixture-root `path`, and
`read_only` (default true); targets are unique. Paths disallow traversal, absolute
paths, backslashes and NUL. The current S3 host maps a safe relative reference to
an object key and mounts fixtures at `/tmp/app/<path>`, separately from student
files at `/app`. Commands reading fixtures must use this documented mount root.
Credentials, bucket, provider endpoint and sandbox pool limits are host settings,
never definition fields. The host controls provider mapping.

Feedback is one `enabled`, `mode`, `preferences` policy. Only implemented mode
`default` is accepted. Preferences include general title/score/passed-test/summary
options, online learning resources and default category headers. Learning-resource
`linked_tests` reference criterion IDs. AI evaluator use is independent of
feedback policy; disabling feedback does not disable required AI assessments.
The unimplemented AI reporter and unknown preferences are rejected.

## Examples and errors

| Assignment | Valid example | Invalid example |
|---|---|---|
| Python I/O | [python-io](https://github.com/webtech-network/autograder/blob/main/examples/definitions/python-io.json) | [unknown input option](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/io-input-alias.json) |
| Multilanguage I/O | [multi-language](https://github.com/webtech-network/autograder/blob/main/examples/definitions/multi-language-io.json) | [missing command](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/missing-command-language.json), [shell operator](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/shell-operator-command.json) |
| Artifact | [file artifact](https://github.com/webtech-network/autograder/blob/main/examples/definitions/file-artifact.json) | Absolute/traversal artifact paths are invalid |
| API | [API](https://github.com/webtech-network/autograder/blob/main/examples/definitions/api.json) | [endpoint type](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/api-invalid-endpoint.json) |
| Web/static | [webdev](https://github.com/webtech-network/autograder/blob/main/examples/definitions/webdev.json), [import penalty](https://github.com/webtech-network/autograder/blob/main/examples/definitions/io-with-import-penalty.json) | [parameter typo](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/web-parameter-typo.json), [zero threshold](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/zero-presence-threshold.json), [misspelled evaluator](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/misspelled-evaluator.json) |
| Structure | [python-io](https://github.com/webtech-network/autograder/blob/main/examples/definitions/python-io.json) | [base weight written](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/removed-base-weight.json), [unused preparation language](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/preparation-language-not-allowed.json) |
| AI/static | [AI algorithm](https://github.com/webtech-network/autograder/blob/main/examples/definitions/static-ai.json) | [empty algorithm](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/ai-empty-algorithm.json) |
| Nested feedback | [weighted groups](https://github.com/webtech-network/autograder/blob/main/examples/definitions/nested-with-feedback.json) | [duplicate ID](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/duplicate-criterion-id.json) |

[Invalid-example manifest](https://github.com/webtech-network/autograder/blob/main/examples/definitions/invalid/manifest.json) records exact errors.
For example: ``{"code":"INVALID_DEFINITION","path":["criteria","base","tests",0,"parameters","input"],"message":"`expect_output` has no parameter `input`; did you mean `inputs`?"}``.
Each error's path names the offending field, cross-field rules included (an
unused preparation language: `["preparation","languages","java"]`), and messages
carry no Pydantic prefix. Unknown evaluators and parameters name the closest
identifier. HTTP adds
envelope/body components to paths for Pydantic request errors and reports their
Pydantic type as `code`. Errors never echo input files/provider credentials.
`python -m execution_host.check` prints the same errors offline
([Test your rubric](../author/testing.md)).

## Definitions in an earlier format

The offline converter turns a 1.0 or pre-1.0 definition into a 2.0 one, or
prints the exact errors that stop it; nothing converts at runtime:

```sh
python -m autograder.services.definition_migration old-definition.json definition.json
```

It also prints, as notes, what it converted but assesses differently. What it
maps, what it rejects and what happens to stored definitions is in the
[migration notes](DECISIONS.md#definitions).

Assessment file targets, scope, context and trusted Python file declarations are defined
in [the file-selection contract](FILES.md).
