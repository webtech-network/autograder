# Autograder

<div align="center">
<img width="330" height="300" alt="image" src="https://github.com/user-attachments/assets/6e897346-9e0d-4311-a961-b460f920f87d" />


**An educational-standards-driven autograding tool that transforms assignment grading into an engaging learning experience.**

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)](https://www.docker.com/)
[![Verify](https://github.com/webtech-network/autograder/actions/workflows/verify.yml/badge.svg)](https://github.com/webtech-network/autograder/actions/workflows/verify.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

[Features](#features) • [Write an assignment](#write-an-assignment) • [Quick Start](#quick-start) • [Architecture](#architecture) • [API](#rest-api) • [GitHub Action](#github-action) • [Docs](https://webtech-network.github.io/autograder/) • [Community](#community-standards)

</div>

> [!IMPORTANT]
>
> The Autograder is in active development. New features are being added continuously, and we welcome contributions from the community. We would love to hear your suggestions or feature requests! Don't hesitate on opening an issue on GitHub.

---

## Overview

The **Autograder** grades student submissions against a rubric the teacher
writes once, a versioned *grading definition*, and explains every grade in a
report written for the student. It runs as an HTTP service that grades many
submissions, or as a GitHub Action that grades the repository it runs in.

## Features

### For educators

- **Tree-structured rubrics**: required criteria, extra credit and penalties,
  grouped into weighted subjects at any depth ([how scores work](docs/author/scoring.md)).
- **Programs and web pages**: run command-line programs in Python, Java,
  JavaScript (Node.js), C and C++ against expected output; check HTML, CSS and
  JavaScript files; forbid imports or language constructs.
- **Multi-language assignments**: one definition accepts several languages,
  each with its own files and build steps.
- **Validation before students see it**: a definition is checked completely
  when you validate or publish it, with the exact place of every mistake.
- **Configurations with revisions**: the HTTP service stores each assignment's
  definition and binds every submission to the exact revision it was graded with.

### For students

- **A report that explains the score**: every criterion, its points and the
  reason it failed, ordered by what cost the most, with linked learning resources.
- **English and Brazilian Portuguese** reports and messages.
- **Clear failures**: a missing file or a compilation error is explained,
  never turned into a silent zero.
- **Progress between attempts**: the HTTP service compares two graded
  submissions criterion by criterion.

### For developers

- **REST API** with durable, restart-safe acceptance of submissions.
- **GitHub Action** that grades one checkout and keeps a canonical outcome artifact.
- **Isolated execution**: student code runs in a disposable sandbox per grading,
  with no network, bounded memory and processes, and confirmed cleanup.
- **Extensible evaluators**: add one with its implementation, parameter
  contract and registration ([recipe](docs/architecture/extending.md)).

---

## Write an assignment

The [tutorial](docs/author/tutorial.md) builds three assignments, each with a
good and a bad submission that the test suite grades in real sandboxes. A
definition is one JSON document:

```json
{
  "schema_version": "1.0",
  "templates": ["input_output"],
  "languages": ["python"],
  "criteria": {
    "base": {
      "weight": 100,
      "tests": [
        {
          "id": "sum",
          "type": "expect_output",
          "name": "Adds two numbers",
          "parameters": {"program_command": "python3 main.py", "inputs": ["2", "3"], "expected_output": "5"}
        }
      ]
    }
  },
  "preparation": {"languages": {"python": {"required_files": ["main.py"]}}},
  "feedback": {"enabled": true}
}
```

Every check a criterion `type` can name, with its parameters, is in the
generated [evaluator reference](docs/reference/evaluators.md). Trusted Python
code can add its own evaluators ([recipe](docs/architecture/extending.md));
definitions sent over HTTP or used by the Action use the built-in ones.

## Try the demo

The browser demo creates configurations, submits example programs and shows
the results of a running API:

```bash
make start-autograder   # the API, see Quick Start
make examples-demo
```

Open **http://localhost:8080/demo/** and enter the API's address and its
integration token (`AUTOGRADER_INTEGRATION_TOKEN`) on the first page.

---

## Quick Start

Setup lives in one place, the [Development Guide](docs/guides/development.md).
In short, with [uv](https://docs.astral.sh/uv/) (it provides Python 3.13, the
only supported version) and GNU Make:

```bash
git clone https://github.com/webtech-network/autograder.git
cd autograder
make install           # .venv from the committed uv.lock
make verify            # hermetic core/library check: no Docker, no database
```

CI runs the same commands, plus the Docker and PostgreSQL tiers
(`make test-integration`, `make test-e2e`, `make test-http`, `make test-postgres`); `make help`
lists them all.

To run the system:

- **Sandbox images:** the runtime images named in `sandbox_config.yml`
  (`make sandbox-list`) must be present before a host starts: `docker pull` the
  published references, or `make sandbox-build-all` to build them from this checkout.
- **Web API:** export `SANDBOX_API_TOKEN` and `AUTOGRADER_INTEGRATION_TOKEN`
  (long random secrets), then `make start-autograder`, a development-only stack
  (Docker and Docker Compose; the host-wide sandbox budget
  `general.max_sandboxes` and the runtimes are configured in `sandbox_config.yml`;
  size the budget by CPU, about 8 on 12 CPUs, see [JOBS.md](docs/contracts/JOBS.md#sandbox-capacity)). See [Run your first grading workflow](docs/getting-started/first-grading-workflow.md);
  deployments follow [Deploying the HTTP service](docs/operate/deployment.md).
- **GitHub Action:** see the [GitHub Action](#github-action) section.

---

## Architecture

The core (`autograder/`) owns grading semantics: the versioned definition, the
evaluator contract, assessment, scoring and feedback. Hosts (`web/`,
`github_action/`) collect files, authenticate, persist and publish. They pass
execution, fixture and AI providers to the core as `HostCapabilities`, composed in
`execution_host/` on top of `sandbox_manager/`. The core imports none of them, and
a test enforces it. The full map is
[Responsibilities and Dependencies](docs/architecture/overview.md).

```python
from autograder import compile_definition, evaluate_submission

# One versioned grading definition, compiled before execution.
compiled = compile_definition(definition_json)
outcome = evaluate_submission(submission, definition=compiled).model_dump(mode="json")
```

Integrators start with the [definition](docs/contracts/DEFINITIONS.md) and
[terminal outcome](docs/contracts/OUTCOMES.md) contracts.

---

## REST API

The Autograder provides a FastAPI-based REST API for integration with learning management systems.


**📚 [Complete API Documentation →](https://webtech-network.github.io/autograder/API/)**

Includes endpoints for:
- Creating grading configurations
- Submitting assignments for grading
- Retrieving results

---

## GitHub Action

The Autograder GitHub Action grades one ordinary checkout and writes a versioned
outcome artifact and workflow summary. Cloud publication is optional and happens
after grading completes. Repository write permissions are unnecessary.

```yaml
jobs:
  assess:
    permissions:
      contents: read
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: webtech-network/autograder@main
        with:
          definition-path: .github/autograder/definition.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: grading-outcome
          path: .autograder/
```

### Learn more

- **Module overview and internals:** [docs/github_action/README.md](docs/github_action/README.md)
- **Configuration reference and troubleshooting:** [docs/github_action/configuration.md](docs/github_action/configuration.md)
- **Reference implementation:** [webtech-network/demo-autograder](https://github.com/webtech-network/demo-autograder)
- **How to adapt the demo to your course:** [docs/github_action/quick-start.md](docs/github_action/quick-start.md)

---

## Full Documentation

Full documentation is available at [GitHub Pages](https://webtech-network.github.io/autograder/),
organized by task: author an assignment, integrate, extend, operate.

---

## Performance

Capacity depends on hardware, configuration and assignments, so the project
publishes measurements rather than typical numbers. Run the
[capacity benchmark](docs/contracts/JOBS.md#capacity-benchmark) against your own
stack; JOBS.md holds the reference result with its hardware and workload.

---

## Community Standards

We are committed to building a welcoming and inclusive community.

- **Code of Conduct**: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Contributing Guide**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Security Policy**: [SECURITY.md](SECURITY.md)
- **Support**: [SUPPORT.md](SUPPORT.md)
- **Issue Templates**: [`.github/ISSUE_TEMPLATE`](.github/ISSUE_TEMPLATE)
- **PR Template**: [`.github/pull_request_template.md`](.github/pull_request_template.md)

---

## Contact

For questions, suggestions, or support:

- **Issues**: [GitHub Issues](https://github.com/webtech-network/autograder/issues)
- **Discussions**: [GitHub Discussions](https://github.com/webtech-network/autograder/discussions)
- **Email**: arthurcarvalhorodrigues2409@gmail.com

---

<div align="center">

**Star this repo if you find it useful!**

Made by educators, for educators

</div>
