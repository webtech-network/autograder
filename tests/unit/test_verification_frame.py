"""Verification commands, their CI wiring and the deploy gate (ENV-06, #427).

Contributors and CI run the same Makefile targets. CI runs on every pull
request, invokes only those targets, and deployment waits for every
verification job of the same commit.
"""
# pylint: disable=missing-function-docstring
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
VERIFY = WORKFLOWS / "verify.yml"
#: A third-party action reference fixed to one immutable commit.
PINNED = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}")
#: Status functions that would let a job run after a failed dependency.
STATUS_OVERRIDES = ("always()", "failure()", "cancelled()")


def makefile_targets() -> tuple[set[str], set[str]]:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    defined = set(re.findall(r"^([a-z][a-z0-9-]*):(?!=)", text, re.M))
    phony = set(" ".join(re.findall(r"^\.PHONY:(.*)$", text, re.M)).split())
    return defined, phony


def make(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["make", "--no-print-directory", "-C", str(ROOT), *arguments],
                          capture_output=True, text=True, check=False, timeout=60)


def workflow(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # YAML 1.1 reads the bare key `on` as True.
    return data


def steps(data: dict):
    for job in data["jobs"].values():
        yield from job.get("steps", [])


def test_make_help_lists_only_defined_targets():
    defined, phony = makefile_targets()
    result = make("help")
    assert result.returncode == 0, result.stderr
    listed = set(re.findall(r"^\s+make ([a-z][a-z0-9-]*)", result.stdout, re.M))
    assert {"verify", "test-postgres", "test-integration", "test-e2e"} <= listed
    assert listed <= defined
    assert phony == defined


def test_every_listed_target_resolves():
    _, phony = makefile_targets()
    for target in sorted(phony):
        result = make("-n", target)
        assert result.returncode == 0, f"make -n {target}: {result.stderr}"


def test_hermetic_path_needs_neither_docker_nor_postgres():
    plan = make("-n", "verify")
    assert plan.returncode == 0, plan.stderr
    for step in ("pylint", "generate_contract_schemas.py --check", "validate_docs.py",
                 "mkdocs build --strict", "tests/unit", "tests/web"):
        assert step in plan.stdout
    assert "docker" not in plan.stdout
    assert "not postgres" in plan.stdout


def test_documented_make_commands_exist():
    defined, _ = makefile_targets()
    sources = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "AGENTS.md",
               *(ROOT / "docs").rglob("*.md"), *(ROOT / "tests").rglob("*.py"),
               *(ROOT / "scripts").iterdir(), *WORKFLOWS.glob("*.yml")]
    mentioned = {(path.relative_to(ROOT).as_posix(), target)
                 for path in sources if path.is_file()
                 for target in re.findall(r"(?:^\s*|`|&& |\$ )make ([a-z][a-z0-9-]*)",
                                          path.read_text(encoding="utf-8"), re.M)}
    assert {item for item in mentioned if item[1] not in defined} == set()
    for guide in ("README.md", "CONTRIBUTING.md", "docs/guides/development.md"):
        assert "make verify" in (ROOT / guide).read_text(encoding="utf-8"), guide


def test_ci_runs_on_every_pull_request_and_on_main():
    triggers = workflow(VERIFY)["on"]
    assert triggers["pull_request"] in (None, {})  # no branch or path filter
    assert triggers["push"] == {"branches": ["main"]}


def test_ci_invokes_only_make_targets():
    defined, _ = makefile_targets()
    jobs = workflow(VERIFY)["jobs"]
    commands = {name: [line.strip() for step in job["steps"] if "run" in step
                       for line in step["run"].strip().splitlines()]
                for name, job in jobs.items() if name != "deploy"}
    for name, lines in commands.items():
        assert lines, name
        for line in lines:
            assert re.fullmatch(r"make( [a-z][a-z0-9-]*)+", line), f"{name}: {line}"
            assert set(line.split()[1:]) <= defined, f"{name}: {line}"
    assert "make verify" in commands["core"]
    assert "make test-postgres" in commands["postgres"]


def test_deploy_waits_for_every_verification_job():
    jobs = workflow(VERIFY)["jobs"]
    deploy = jobs["deploy"]
    assert set(deploy["needs"]) == set(jobs) - {"deploy"}
    condition = deploy["if"]
    assert "github.event_name == 'push'" in condition
    assert "github.ref == 'refs/heads/main'" in condition
    assert not any(override in condition for override in STATUS_OVERRIDES)


def test_only_the_gated_job_deploys_the_service():
    for path in WORKFLOWS.glob("*.yml"):
        for name, job in workflow(path)["jobs"].items():
            text = yaml.safe_dump(job)
            if "SSH_PRIVATE_KEY" in text or "push: true" in text:
                assert (path, name) == (VERIFY, "deploy")


def test_third_party_actions_are_pinned_to_commits():
    for path in WORKFLOWS.glob("*.yml"):
        data = workflow(path)
        uses = [step["uses"] for step in steps(data) if "uses" in step]
        uses += [job["uses"] for job in data["jobs"].values() if "uses" in job]
        for reference in uses:
            if not reference.startswith("./"):
                assert PINNED.fullmatch(reference), f"{path.name}: {reference}"


def test_postgres_tier_fails_loudly_without_a_database():
    environment = {key: value for key, value in os.environ.items() if key != "TEST_POSTGRES_URL"}
    environment["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-m", "postgres", "tests/web"],
        cwd=ROOT, env=environment, capture_output=True, text=True, check=False, timeout=300)
    summary = result.stdout.strip().splitlines()[-1]
    assert result.returncode == 1, result.stdout
    assert "TEST_POSTGRES_URL" in result.stdout
    assert re.search(r"\d+ errors?", summary), summary
    assert "passed" not in summary and "skipped" not in summary, summary
