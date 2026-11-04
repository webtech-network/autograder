# Languages, runtimes, commands and parsers

A submission language is a domain identifier. It does not name a Docker image, a
command or a grammar. Each of those belongs to the component that uses it:

| Concern | Owner | Where |
| --- | --- | --- |
| Supported identifiers (`python`, `java`, `node`, `cpp`, `c`) | Domain | `autograder/models/language.py` (`Language`, `LANGUAGE_IDS`, `LanguageId`) |
| Definition schema, submission binding, outcome serialization | Domain contracts | derived from `LanguageId`/`LANGUAGE_IDS`; no other list exists |
| Language → sandbox image | Host | `runtimes:` in `sandbox_config.yml` (`SandboxPoolConfig.image`) |
| I/O command (`program_command` string, map or `CMD`) | I/O evaluators | `autograder/models/abstract/execution_test.py` (`DEFAULT_COMMANDS`) |
| Preparation commands | Definition | `preparation.languages.<language>.setup_commands`, selected once per run |
| File type → grammar, runtime → grammar | Analysis | `autograder/services/structural_analysis.py` (`SOURCE_GRAMMARS`, `RUNTIME_GRAMMARS`) |
| Which files an evaluator assesses | The evaluator | `TestFunction.accepts_file(filename, language)` |

Wire identifiers are unchanged. The checked-in outcome schema lists them in the
declaration order (`python, java, node, cpp, c`).

## Binding

`select_language(definition, supplied)` is called once per execution, before any
host call. A single-language definition infers its language. A definition with
several languages requires an explicit value (`LANGUAGE_REQUIRED`). A value outside
the definition's list, including an unknown identifier, is `LANGUAGE_NOT_ALLOWED`.
The HTTP submission adapter lower-cases its input before binding (`"Java"` is
stored as `java`); definitions, attestations and deliberate execution accept only
canonical identifiers.

The bound `Language` is the value used for preparation selection, host
acquisition, `EvaluationInput.language` and the outcome's `language`.

## Runtime support is a host capability

A language may be valid and allowed while the host cannot run it. The Docker
host creates a pool only for languages listed under `runtimes:`. Acquiring
another language raises `RuntimeUnavailableError`, and the control API returns
`501 RUNTIME_UNAVAILABLE`, which the remote client converts back into the same
error. Grading reports `CAPABILITY_UNAVAILABLE` (category `capability`), and
deliberate execution returns `503 EXECUTION_UNAVAILABLE`. Neither is reported as
an invalid language. Static-only definitions never touch runtimes.

```yaml
runtimes:   # `make sandbox-list` prints the current tags
    python: ghcr.io/webtech-network/autograder-sandbox-python:<tag>
    java: ghcr.io/webtech-network/autograder-sandbox-java:<tag>
    node: ghcr.io/webtech-network/autograder-sandbox-node:<tag>
    cpp: ghcr.io/webtech-network/autograder-sandbox-cpp:<tag>
    c: ghcr.io/webtech-network/autograder-sandbox-cpp:<tag>
```

Replacing an image changes only this map. Unknown keys and empty images are
rejected when the configuration is loaded.

## Runtime images

The shipped runtimes are built from `sandbox_manager/images/Dockerfile.<name>`
and are what students' code runs on:

| Language | Image | Runtime | Base |
| --- | --- | --- | --- |
| `python` | `autograder-sandbox-python` | CPython 3.13 | `python:3.13-alpine3.24` |
| `java` | `autograder-sandbox-java` | Eclipse Temurin JDK 21 (LTS) | `eclipse-temurin:21-jdk-alpine-3.24` |
| `node` | `autograder-sandbox-node` | Node.js 24 (LTS) | `node:24-alpine3.24` |
| `cpp`, `c` | `autograder-sandbox-cpp` | GCC 15 (`g++`, `gcc`, `make`, musl) | `alpine:3.24` |

Each base is pinned by digest. An image holds its runtime and nothing to fetch
or install more: no package manager (`apk`, `pip`, `npm`/`npx`/`yarn`/`corepack`),
no downloader (`curl`, `wget`, `nc`), no setuid binary, and the process runs as
the unprivileged `sandbox` user. `tests/integration/test_runtime_images.py`
checks the versions above and these absences on the built images.

**References are versioned by content.** An image's reference is
`ghcr.io/webtech-network/autograder-sandbox-<name>:<tag>`, where `<tag>` is the
first 12 hex digits of its Dockerfile's SHA-256 (`scripts/sandbox_images.py`).
Editing a Dockerfile therefore produces a new reference, and a unit test fails
until `sandbox_config.yml` names it. Images are built without a build context
(the Dockerfile is sent on stdin), so nothing from a checkout can enter them.
The `Sandbox runtime images` workflow builds every image from scratch, runs the
image checks and the Docker integration suite (golden outcomes included)
against those images, and on `main` pushes each reference the registry does not
have yet. A published reference is never overwritten, so rebuilding cannot
change the runtime a host already uses.

**A host verifies its images at startup.** `SandboxManager` (the control API
at startup, a local-mode host at its first acquisition) requires every
configured image to be present on the Docker host and to list the language in
its `autograder.runtime.languages` label (`cpp,c` for the C/C++ image). It never
pulls: a missing image raises `RuntimeImageError` naming the image and the
`docker pull` command, and an image whose label does not declare the language
(for example an old unlabelled `sandbox-py:latest`, or the Java image mapped to
`python`) raises `RuntimeImageError` before any container is created. A custom
image only needs that label.

Changing a student runtime (for example Node.js 24 to 26) is a release-noted
change: edit the Dockerfile, update this table and the documented versions in
`tests/integration/test_runtime_images.py`, put the new reference in
`sandbox_config.yml`, and pass the golden outcomes.

## Program commands

`program_command` is resolved by the I/O evaluator for the bound language:

* a plain string is used as written for every language;
* a language map selects the bound language's entry; compilation rejects a map
  that does not cover every allowed language (`MISSING_LANGUAGE_COMMAND`);
* `"CMD"` selects the documented default: `python3 main.py`, `java Main`,
  `node index.js`, and `./a.out` for C and C++. Compilation rejects `CMD` for an
  allowed language without a default.

There is no other default table, no upper-case (`PYTHON`) alias for map keys and
no file-name inference. The removed `CommandResolver` documented inference from a
"fallback filename" that no caller ever supplied, so the executed `CMD` commands
are unchanged and no definition needs to migrate.

## Grammar selection

Analysis chooses a grammar from each selected file's type, never from the
runtime alone. `forbidden_keyword` and `forbidden_import` accept only source files
of the runtime's own grammar (`is_runtime_source`); `.h` follows a `cpp` runtime.
In a `node` web submission, `app.js` is parsed as JavaScript, while `index.html`
(including an inline `<script>`), `styles.css` and Markdown never reach the
JavaScript grammar. HTML and CSS evaluators select their files by extension and
parse them with their own parsers. Naming a document as the explicit target of a
source analyser fails with `UNSUPPORTED_FILE_TYPE`.

## Change surface

**Add a runtime language** (for example `go`):

1. `autograder/models/language.py`: add `GO = "go"`. The schemas, submission and
   execution validators, outcome model and catalog follow automatically. Then run
   `scripts/generate_contract_schemas.py`.
2. `sandbox_config.yml`: add `go: sandbox-go:<version>` and build that image.
3. Its consumers, only if the language should support them:
   `DEFAULT_COMMANDS` for `CMD` (otherwise authors use explicit commands; the
   test `test_default_table_covers_every_domain_language` reminds you),
   `SOURCE_GRAMMARS`/`RUNTIME_GRAMMARS` for structural analysis, and the
   per-language tables of `forbidden_import`/`forbidden_keyword`. A missing
   entry is reported at compilation for definitions that need it.

The generic compiler, grader, pipeline and outcome finalizer do not change.

**Change a runtime image:** edit `runtimes:` only.

**Add a parser rule** (for example `.ts` as TypeScript): add the suffix to
`SOURCE_GRAMMARS` in `structural_analysis.py`. To add a predefined
`forbidden_keyword` rule, add it to that evaluator's `PREDEFINED_RULES`. Nothing
outside the analysis module and the evaluator changes.

No plugin framework or registry is involved; each table is read only by the
component that owns it.
