# Grading definition v1

The same normalized definition is accepted by Python, repository files, HTTP
configuration storage and external-result snapshots. [Decision record](DECISIONS.md)
and [terminal outcomes](OUTCOMES.md) describe the integration boundaries.

[JSON Schema](v1/grading-definition.schema.json) describes built-in authoring.
`compile_definition` adds registry, uniqueness, command-coverage, AST-rule grammar,
learning-reference and weighted-group checks that JSON Schema cannot fully express.
Its normalized return value is the stored definition and the source of its hash.

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
  implementation's signature or `config_schema` generates discovery and parameter
  validation. Known runtime context (`files`, `sandbox`, language, locale, AI
  precomputed results, structural analysis, evaluation scope and file metadata)
  is forbidden in authored parameters, including trusted custom schemas.
* Weights are finite nonnegative numbers, never booleans/strings. Group/category
  weights lie in 0–100, relative test weights can exceed 100. Base weight is 100;
  optional bonus/penalty weights cap their contribution. All-zero sibling weights
  normalize equally. A group needs tests or subjects; mixed groups require a
  finite `subjects_weight` in 0–100. A split on a homogeneous group is rejected.
  Both groups are assessed even when one contributes zero.
* A command is a nonempty string or a canonical language-keyed string map covering
  every allowed language. Existing `CMD` explicitly means conventional defaults:
  `python3 main.py`, `java Main`, `node index.js`, `./a.out` for C/C++; it does not
  infer filenames. Prefer explicit commands. `dont_fail` uses `user_input`;
  `input` is rejected. Artifact paths are normalized relative submission paths;
  modes are `exact`, `contains`, `regex`; invalid regex is rejected before execution.
* AST keywords must be supported in every allowed language. Custom ast-grep rules
  must compile for each language before acceptance. AI algorithm names are stripped
  and must remain nonempty. Repeated AI evaluator uses have independent IDs.

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
`command`. Fixtures have logical `reference`, relative fixture-root `path`, and
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
| Multilanguage I/O | [multi-language](v1/examples/multi-language-io.json) | [missing command](v1/examples/invalid/missing-command-language.json) |
| Artifact | [file artifact](v1/examples/file-artifact.json) | Absolute/traversal artifact paths are invalid |
| API | [API](v1/examples/api.json) | [endpoint type](v1/examples/invalid/api-invalid-endpoint.json) |
| Web/static | [webdev](v1/examples/webdev.json), [import penalty](v1/examples/io-with-import-penalty.json) | [parameter typo](v1/examples/invalid/web-parameter-typo.json) |
| AI/static | [AI algorithm](v1/examples/static-ai.json) | [empty algorithm](v1/examples/invalid/ai-empty-algorithm.json) |
| Nested feedback | [weighted groups](v1/examples/nested-with-feedback.json) | [duplicate ID](v1/examples/invalid/duplicate-criterion-id.json) |

[Invalid-example manifest](v1/examples/invalid/manifest.json) records exact errors.
For example: `{"code":"INVALID_DEFINITION","path":["criteria","base","tests",0,"parameters","input"],"message":"Extra inputs are not permitted"}`.
HTTP adds envelope/body components to paths for Pydantic request errors. Errors
never echo input files/provider credentials.

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

The old `test_library` envelope is unsupported. Multiple templates use an
explicit list with collision-checked registry resolution. Evaluator parameters
have typed contracts and stable criterion IDs. Provider mapping, resource limits,
and infrastructure scheduling belong to the hosting environment rather than
the definition schema.
