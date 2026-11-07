# Grading definition v1

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
  "schema_version": "1.0",
  "templates": ["input_output"],
  "languages": ["python"],
  "criteria": {
    "base": {
      "weight": 100,
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

* Version is exactly `"1.0"`. Templates are distinct registered identifiers, never
  comma-separated strings. Cross-template evaluator collisions are errors.
* Languages are distinct canonical `python`, `java`, `node`, `cpp`, `c`. Definition
  aliases/case variations are rejected. Submission transports may normalize case;
  a sole allowed language is inferred, multiple languages require selection.
* Every criterion has globally unique stable `id`, explicit evaluator `type`,
  display `name`, and required parameter object (empty `{}` for parameterless
  evaluators). Display labels may repeat; IDs stay stable across label edits.
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
* Weights are finite nonnegative numbers, never booleans/strings. Group/category
  weights lie in 0–100, relative test weights can exceed 100. Base weight is 100;
  optional bonus/penalty weights cap their contribution. All-zero sibling weights
  normalize equally. A group needs tests or subjects; mixed groups require a
  finite `subjects_weight` in 0–100. A split on a homogeneous group is rejected.
  Both groups are assessed even when one contributes zero.
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
  `dont_fail` uses `user_input`;
  `input` is rejected. Artifact paths are normalized relative submission paths;
  modes are `exact`, `contains`, `regex`; invalid regex is rejected before execution.
* A definition is rejected with `DEFINITION_TOO_LARGE` when its snapshot plus
  its worst-case outcome exceeds 24 MiB (about 465 criteria with short
  parameters). This keeps every attestation within the hosts' request limit.
  See [OUTCOMES.md](OUTCOMES.md#size-bounds).
* AST keywords must be supported in every allowed language. Custom ast-grep rules
  must compile for each language before acceptance. AI algorithm names are stripped
  and must remain nonempty. Repeated AI evaluator uses have independent IDs.
* No criterion's result may be independent of the submission because a parameter
  was omitted. Presence thresholds (`required_count`, `min_items`, `has_style.count`)
  default to 1 and reject 0; lists of things to find (`has_class.class_names`,
  `js_uses_dom_manipulation.methods`) and `forbidden_import.forbidden_imports` name
  at least one nonempty item; `forbidden_keyword` needs a keyword or a custom rule
  (`EMPTY_FORBIDDEN_LIST`). Prohibition and limit checks, which pass when what they
  look for is absent, publish the reason as `absence_check` in the
  [catalog](CATALOG.md). A contract test runs every catalog evaluator with only its
  required parameters on an irrelevant project and fails if a presence check passes.

Defaults are explicit in compiled JSON: preparation has empty language/fixture
collections; feedback is disabled with default mode/preferences; test weight is
100; metadata is empty. Optional `file`, bonus/penalty, tests/subjects and split
values normalize to null where omitted. Required fields and preparation/feedback
cannot be null. Optional criterion `file: null` means use all relevant files.

The hash is SHA-256 over normalized JSON, sorted keys, compact separators,
UTF-8, no ASCII escaping and no NaN. Object key order and omitted defaults do not
change the hash; criterion order, parameters, labels and metadata do. Criterion
IDs give comparison identity; hash equality gives complete definition equality.

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
| Python I/O | [python-io](v1/examples/python-io.json) | [unknown input option](v1/examples/invalid/io-input-alias.json) |
| Multilanguage I/O | [multi-language](v1/examples/multi-language-io.json) | [missing command](v1/examples/invalid/missing-command-language.json), [shell operator](v1/examples/invalid/shell-operator-command.json) |
| Artifact | [file artifact](v1/examples/file-artifact.json) | Absolute/traversal artifact paths are invalid |
| API | [API](v1/examples/api.json) | [endpoint type](v1/examples/invalid/api-invalid-endpoint.json) |
| Web/static | [webdev](v1/examples/webdev.json), [import penalty](v1/examples/io-with-import-penalty.json) | [parameter typo](v1/examples/invalid/web-parameter-typo.json), [zero threshold](v1/examples/invalid/zero-presence-threshold.json), [misspelled template](v1/examples/invalid/misspelled-template.json) |
| Structure | [python-io](v1/examples/python-io.json) | [base weight](v1/examples/invalid/base-weight-not-100.json), [unused preparation language](v1/examples/invalid/preparation-language-not-allowed.json) |
| AI/static | [AI algorithm](v1/examples/static-ai.json) | [empty algorithm](v1/examples/invalid/ai-empty-algorithm.json) |
| Nested feedback | [weighted groups](v1/examples/nested-with-feedback.json) | [duplicate ID](v1/examples/invalid/duplicate-criterion-id.json) |

[Invalid-example manifest](v1/examples/invalid/manifest.json) records exact errors.
For example: ``{"code":"INVALID_DEFINITION","path":["criteria","base","tests",0,"parameters","input"],"message":"`expect_output` has no parameter `input`; did you mean `inputs`?"}``.
Each error's path names the offending field, cross-field rules included (base
weight: `["criteria","base","weight"]`; an unused preparation language:
`["preparation","languages","java"]`), and messages carry no Pydantic prefix.
Unknown templates, evaluators and parameters name the closest identifier, or the
template that provides an evaluator the definition does not list. HTTP adds
envelope/body components to paths for Pydantic request errors and reports their
Pydantic type as `code`. Errors never echo input files/provider credentials.
`python -m execution_host.check` prints the same errors offline
([Action quick start](../github_action/quick-start.md#check-the-definition-first)).

## Legacy definition migration

Convert one legacy definition envelope offline:

```sh
python -m autograder.services.definition_migration old-definition.json definition.json
```

Supply `template_name`, `grading_criteria`, `languages` and optional legacy
setup/feedback fields. Multi-file repository configurations must first be
assembled into that envelope. The converter assigns deterministic path-based IDs
once, preserves weights/labels, moves the known `display_name` parameter to the
label, removes the runtime language placeholder and converts the old file-target `all`
  sentinel to null, and resolves only unambiguous
learning-resource labels. Persist these new IDs; do not regenerate them on edits.
Duplicate pairs, competing encodings, unsupported options and unsafe asset
relocation require explicit instructor correction. There is no runtime converter.

Migration 005 converts database rows, records rejection evidence, quarantines
invalid rows inactive, and drops old configuration columns. Future submissions
retain exact snapshots/hash/revision. Old submissions remain `unverified_legacy`;
old failed numeric zeros become null grades. The migration is intentionally
irreversible: back up first, drain old background executions, deploy the matching
engine/API/Action consumers together, run Alembic upgrade, inspect quarantined rows,
then reactivate only corrected definitions. Rollback restores the pre-upgrade DB
backup with the previous code. Automatic schema creation does not migrate a DB.

### Definitions that compile no longer (ONB-01)

Definitions that compiled before may now be rejected, intentionally: an explicit
presence threshold of `0`, an empty forbid/find list, or a standalone shell
operator in a command. Nothing else changes: a stored snapshot lists every
parameter explicitly, so a valid snapshot keeps its meaning and hash, and a
raw definition that omitted a threshold now gets 1 instead of an always-passing 0.
There is no runtime fallback. A stored configuration that became invalid is
rejected with the exact path (`422` on submission, a failed outcome for a job
already bound to it) until it is corrected; nothing rewrites it silently.

Before deploying, check every stored definition with the offline converter,
which compiles v1 input unchanged and prints the precise errors:

```sh
python -m autograder.services.definition_migration stored.json checked.json
```

Then correct each rejected definition through the configuration API (`PATCH`
creates a new revision): set the intended threshold, name the forbidden items or
delete the criterion, and move compile steps such as `javac A.java && java A`
into `setup_commands` (`javac A.java`) with `program_command: "java A"`. A
legacy envelope carrying these values is rejected by the converter in the same
way, so migration 005 would quarantine such a row.

The old `test_library` envelope is unsupported. Multiple templates use an
explicit list with collision-checked registry resolution. Evaluator parameters
have typed contracts and stable criterion IDs. Provider mapping, resource limits,
and infrastructure scheduling belong to the hosting environment rather than
the definition schema.

Assessment file targets, scope, context and trusted Python migration are defined
in [the file-selection contract](FILES.md).
