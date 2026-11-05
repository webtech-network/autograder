#!/usr/bin/env python3
"""Grade fixture checkouts with this commit's packaged Action on a GitHub-hosted runner.

The ``action`` job of ``.github/workflows/verify.yml`` runs the real Action
(``uses: ./``) on ``ubuntu-latest`` once per fixture below, with nothing but the
quick-start inputs plus the fixture's ``definition-path`` and ``submission-root``.

``prepare`` (``make action-fixtures``) writes the fixture checkouts under
``.action-fixtures/`` and points ``action.yml`` at ``Dockerfile.actions``, so the
runner builds the Action image from this commit instead of pulling the released
one. A runtime image the registry does not serve anonymously yet (a pull request
that changes ``sandbox_manager/images``, or a package not yet made public) is
built from this checkout under its versioned reference; otherwise the Action
pulls it itself, as on a consumer's runner.

``check`` (``make test-action``, after each ``uses: ./`` step, fixture named by
``ACTION_FIXTURE``) asserts the retained outcome and the step outputs, that the
run created exactly the expected number of sandboxes on the runner's Docker and
that none survived, then moves ``.autograder/`` aside for the next fixture.
The ``probe`` fixture's submission reports what it can see from inside the
sandbox; no credential, runner variable, Docker socket or network may be among it.

Run as a module from the repository root: ``python -m scripts.action_fixtures prepare``.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Sequence

import yaml

from scripts.sandbox_images import build, catalog

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / ".action-fixtures"
MARK = FIXTURES_DIR / "since"
#: Label every sandbox container carries (sandbox_manager.ownership).
SANDBOX_LABEL = "autograder.sandbox.app=autograder-sandbox"
#: Values the probe step hands the Action; none may reach the submission.
SENTINELS = ("ENV03-SENTINEL-CLOUD-TOKEN", "ENV03-SENTINEL-OPENAI-KEY")
#: Variable prefixes of the runner and the Action container that must not reach the submission.
RUNNER_PREFIXES = ("GITHUB_", "RUNNER_", "ACTIONS_", "INPUT_", "AUTOGRADER_", "OPENAI_")

PROBE = r'''import json, os, socket
def attempt(action):
    try:
        return action()
    except OSError as error:
        return type(error).__name__
def connect():
    socket.create_connection(("1.1.1.1", 443), timeout=3).close()
    return "connected"
def read(path):
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8", "replace")
seen = {"pid1_environ": attempt(lambda: read("/proc/1/environ")), "variables": sorted(os.environ),
        "environment": "\n".join(f"{k}={v}" for k, v in os.environ.items()),
        "docker_socket": os.path.exists("/var/run/docker.sock") or os.path.exists("/run/docker.sock"),
        "network": attempt(connect), "files": sorted(os.listdir(".")), "cwd": os.getcwd()}
print(json.dumps(seen, sort_keys=True))
'''


@dataclass(frozen=True)
class Fixture:
    """One checkout to grade and what the Action must report for it."""
    definition: str
    files: Dict[str, str]
    status: str
    score: Optional[float]
    sandboxes: int
    probe: bool = False
    outputs: Dict[str, str] = field(default_factory=dict)


FIXTURES = {
    "static": Fixture("docs/contracts/v1/examples/static-conformance.json",
                      {"index.html": "<!doctype html><title>ok</title>\n"}, "completed", 100, sandboxes=0),
    "python-io": Fixture("docs/contracts/v1/examples/python-io.json",
                         {"main.py": "a = int(input())\nb = int(input())\nprint(a + b)\n"},
                         "completed", 100, sandboxes=1),
    "c-io": Fixture("docs/contracts/v1/examples/c-io.json",
                    {"main.c": '#include <stdio.h>\nint main(void) {\n  int a, b;\n'
                               '  if (scanf("%d %d", &a, &b) != 2) return 1;\n  printf("%d\\n", a + b);\n'
                               '  return 0;\n}\n'},
                    "completed", 100, sandboxes=1),
    # A wrong answer is an assessed zero: the Action succeeds and reports it.
    "python-io-wrong": Fixture("docs/contracts/v1/examples/python-io.json", {"main.py": "print(0)\n"},
                               "completed", 0, sandboxes=1),
    "probe": Fixture("examples/contracts/input_output.json", {"main.py": PROBE}, "completed", 0, sandboxes=1,
                     probe=True),
}


def _docker(*args: str) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout


def _languages(definition: Path) -> set:
    return set(json.loads(definition.read_text(encoding="utf-8"))["languages"])


def anonymously_pullable(reference: str) -> bool:
    """Whether a runner without credentials can pull ``reference`` (a private package cannot)."""
    with tempfile.TemporaryDirectory() as anonymous:
        found = subprocess.run(["docker", "manifest", "inspect", reference], capture_output=True, check=False,
                               env={**os.environ, "DOCKER_CONFIG": anonymous})
    return found.returncode == 0


def prepare() -> None:
    """Write the fixture checkouts, run this commit's Action image, provide unpublished runtimes."""
    shutil.rmtree(FIXTURES_DIR, ignore_errors=True)
    for name, fixture in FIXTURES.items():
        directory = FIXTURES_DIR / name
        (directory / "submission").mkdir(parents=True)
        shutil.copy(ROOT / fixture.definition, directory / "definition.json")
        for filename, content in fixture.files.items():
            (directory / "submission" / filename).write_text(content, encoding="utf-8")
    action = ROOT / "action.yml"
    text, count = re.subn(r"(?m)^  image: .*$", '  image: "Dockerfile.actions"', action.read_text(encoding="utf-8"))
    if count != 1:
        raise SystemExit("action.yml must have exactly one runs.image line")
    action.write_text(text, encoding="utf-8")
    runtimes = yaml.safe_load((ROOT / "sandbox_config.yml").read_text(encoding="utf-8"))["runtimes"]
    executed = {runtimes[language] for name, fixture in FIXTURES.items() if fixture.sandboxes
                for language in _languages(FIXTURES_DIR / name / "definition.json")}
    missing = [image for image in catalog() if image.ref in executed and not anonymously_pullable(image.ref)]
    for image in missing:
        print(f"::notice::{image.ref} is not anonymously pullable yet; building it from this checkout.", flush=True)
    build(missing)
    MARK.write_text(str(int(time.time())), encoding="utf-8")


def _created_sandboxes(since: str, until: str) -> list:
    events = _docker("events", "--since", since, "--until", until, "--filter", "type=container",
                     "--filter", "event=create", "--filter", f"label={SANDBOX_LABEL}",
                     "--format", "{{.Actor.Attributes.image}}")
    return events.split()


def _check_probe(outcome: dict) -> None:
    report = outcome["tree"]["base"]["tests"][0]["report"]
    seen = json.loads(report.split("Actual: '", 1)[1].rsplit("'", 1)[0])
    print(f"Probe saw: {json.dumps(seen, sort_keys=True)}", flush=True)
    assert seen["cwd"] == "/app", seen["cwd"]  # it really ran inside the sandbox
    assert seen["files"] == ["main.py"], seen["files"]  # only submission files are staged
    leaked = [name for name in seen["variables"] if name.startswith(RUNNER_PREFIXES)]
    assert not leaked, f"runner variables reached the submission: {leaked}"
    secrets = [*SENTINELS, os.environ.get("REAL_GITHUB_TOKEN", "")]
    serialized = json.dumps(outcome)
    for secret in filter(None, secrets):
        assert secret not in seen["environment"] and secret not in seen["pid1_environ"], "a credential leaked"
        assert secret not in serialized, "a credential reached the outcome"
    assert seen["docker_socket"] is False, "the Docker socket is visible to the submission"
    assert seen["network"] != "connected", "the submission reached the network"


def check(name: str) -> None:
    """Assert the outcome of the fixture just graded and the runner's sandboxes; keep its artifact aside."""
    fixture = FIXTURES[name]
    until = str(int(time.time()) + 1)
    created = _created_sandboxes(MARK.read_text(encoding="utf-8").strip(), until)
    left = _docker("ps", "--all", "--quiet", "--filter", f"label={SANDBOX_LABEL}").split()
    outcome_path = ROOT / ".autograder" / "outcome.json"
    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    print(f"{name}: status={outcome['status']} score={outcome.get('score')} sandboxes={created} "
          f"step outputs: status={os.environ.get('ACTION_STATUS')} score={os.environ.get('ACTION_SCORE')}",
          flush=True)
    assert outcome["status"] == fixture.status, outcome.get("error")
    assert outcome.get("score") == fixture.score, outcome.get("score")
    assert os.environ.get("ACTION_STATUS") == fixture.status
    assert os.environ.get("ACTION_SCORE", "") == ("" if fixture.score is None else str(float(fixture.score)))
    assert os.environ.get("ACTION_RESULT_PATH") == ".autograder/outcome.json"
    assert len(created) == fixture.sandboxes, f"expected {fixture.sandboxes} sandbox(es), the run created {created}"
    assert left == [], f"sandboxes survived the run: {left}"
    if fixture.probe:
        _check_probe(outcome)
    shutil.move(str(ROOT / ".autograder"), str(FIXTURES_DIR / name / "result"))
    MARK.write_text(until, encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Command line: ``prepare``, or ``check`` for the fixture named by ``ACTION_FIXTURE``."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["prepare", "check"])
    args = parser.parse_args(argv)
    if args.command == "prepare":
        prepare()
    else:
        fixture = os.environ.get("ACTION_FIXTURE", "")
        if fixture not in FIXTURES:
            raise SystemExit(f"ACTION_FIXTURE must name one of {', '.join(FIXTURES)}; got {fixture!r}")
        check(fixture)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"::error::{exc}", file=sys.stderr, flush=True)
        sys.exit(1)
