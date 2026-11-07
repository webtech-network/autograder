# Versions and stability

The repository has one version, `MAJOR.MINOR.PATCH` under
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). `pyproject.toml`
declares it, `autograder.__version__`, the HTTP API (`GET /api/v1/health` and
its OpenAPI document) and the sandbox control API report it. A release tags
the source, the API, sandbox manager and Action images and the Action with that
one number ([releases](../github_action/README.md#releases)). Each release is listed in
[`CHANGELOG.md`](https://github.com/webtech-network/autograder/blob/main/CHANGELOG.md).

## What a version promises

These surfaces are public. Within one major version, a release never changes
them incompatibly:

| Surface | Defined by |
| --- | --- |
| Grading definition: its JSON shape, `schema_version`, evaluator identifiers and their parameters | [Definitions](DEFINITIONS.md), the checked-in JSON Schema, the [evaluator reference](../reference/evaluators.md) |
| Terminal outcome: its JSON shape, `schema_version`, statuses and error codes and categories | [Outcomes](OUTCOMES.md), the checked-in JSON Schema |
| Python API: the names `autograder` exports in `__all__`, and the evaluator authoring contract | [Catalog and Python API](CATALOG.md), [Adding an evaluator](../architecture/extending.md) |
| HTTP API: the routes under `/api/v1`, their bodies, status codes and authentication | [REST API](../API.md), the checked-in [OpenAPI document](v1/openapi.json), [HTTP trust boundary](AUTH.md) |
| GitHub Action: inputs, outputs and the files it writes under `.autograder/` | [Action configuration](../github_action/configuration.md), `action.yml` |
| Host configuration: documented environment variables and `sandbox_config.yml` keys | [Configuration reference](../operate/configuration.md) |

A change is **major** when an input these surfaces accepted is rejected, a
documented field, route, input, output, setting or code is removed or renamed,
or an unchanged definition grades an unchanged submission to a different score,
unless the old score contradicted the documented contract (a bug fix, which
the changelog lists under *Fixed*).

A change is **minor** when it adds to these surfaces: an evaluator, an optional
definition field or parameter, a route, an optional request field, a response
field, an Action input or output, a setting with a default, or an error code.
Clients ignore response fields they do not know and treat an unknown error code
by its `category` and `retryable` flag. A **patch** fixes a bug without adding
to them.

## What is internal

Everything else can change in any release, including: modules and names that
`autograder` does not export; the `web`, `execution_host`, `sandbox_manager` and
`github_action` packages as Python code; the private sandbox control API, which
always runs the version of its own image; the database schema, which only
migrations change; image contents and layout; the wording of feedback reports,
messages and logs; `scripts/`, Makefile targets and tests.

## Deprecation

A public surface is removed only in a major release. Before that, at least one
minor release deprecates it: its documentation and the changelog (*Deprecated*)
name the replacement, and where the code can tell, using it logs a warning.
A security fix may remove or restrict a surface in any release; the changelog
says so.

## Supported versions

The latest release of the latest major version receives fixes, as a new patch
or minor release; earlier releases are not patched. `main` is the development
channel: its images change with every verified commit, so pin a release for
reproducible grading. The supported platforms are Python 3.13, Linux Docker
hosts and Linux GitHub-hosted runners.
