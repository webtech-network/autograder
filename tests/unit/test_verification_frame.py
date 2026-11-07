"""Verification commands, their CI wiring, the publication gate and the release job (ENV-06 #427, ENV-07 #472, REL-01 #478).

Contributors and CI run the same Makefile targets. CI runs on every pull
request, invokes only those targets, and image publication waits for every
verification job of the same commit. Nothing deploys. Only the hand-run Release
workflow releases, and it re-tags what publication verified instead of building.
"""
# pylint: disable=missing-function-docstring
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from scripts import release

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
VERIFY = WORKFLOWS / "verify.yml"
RELEASE = WORKFLOWS / "release.yml"
#: A third-party action reference fixed to one immutable commit.
PINNED = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}")
#: Status functions that would let a job run after a failed dependency.
STATUS_OVERRIDES = ("always()", "failure()", "cancelled()")
#: The job that publishes the verified images of main; every other job verifies.
PUBLICATION = {"publish"}


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
    # Every test run points DOCKER_HOST nowhere, so CI (which has Docker) catches a daemon lookup.
    runs = [line for line in plan.stdout.splitlines() if "-m pytest" in line]
    assert runs and all(line.startswith("DOCKER_HOST=unix:///nonexistent/") for line in runs), runs


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
    # Nothing verifies or publishes by hand: only pull requests and main run, and publish.
    assert set(triggers) == {"pull_request", "push"}


def test_ci_invokes_only_make_targets():
    defined, _ = makefile_targets()
    jobs = {**workflow(VERIFY)["jobs"], **workflow(RELEASE)["jobs"]}
    commands = {name: [line.strip() for step in job["steps"] if "run" in step
                       for line in step["run"].strip().splitlines()]
                for name, job in jobs.items()}
    for name, lines in commands.items():
        assert lines, name
        for line in lines:
            assert re.fullmatch(r"make( [a-z][a-z0-9-]*)+", line), f"{name}: {line}"
            assert set(line.split()[1:]) <= defined, f"{name}: {line}"
    assert "make verify" in commands["core"]
    assert "make test-postgres" in commands["postgres"]


def test_jobs_that_run_the_shipped_sandbox_configuration_install_its_runtime_first():
    # `make test-http` starts the Compose stack with the images' own
    # sandbox_config.yml. Its control service refuses to start when Docker does not
    # offer that runtime (COR-04), and GitHub's runners ship without gVisor.
    shipped = yaml.safe_load((ROOT / "sandbox_config.yml").read_text(encoding="utf-8"))["general"]["runtime"]
    jobs = workflow(VERIFY)["jobs"]
    for name, job in jobs.items():
        runs = [step["run"].strip() for step in job.get("steps", []) if "run" in step]
        for target in ("make test-http", "make test-isolation"):
            if target in runs and shipped == "runsc":
                assert "make gvisor-install" in runs[:runs.index(target)], f"{name}: {target} without gVisor"


def test_publication_waits_for_every_verification_job():
    jobs = workflow(VERIFY)["jobs"]
    for name in PUBLICATION:
        assert set(jobs[name]["needs"]) == set(jobs) - PUBLICATION, name
        assert not any(override in jobs[name]["if"] for override in STATUS_OVERRIDES)
    # Only pushes to main publish: a pull request verifies and publishes nothing.
    assert jobs["publish"]["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    # A red step or job that is allowed to fail would still count as success.
    for name, job in jobs.items():
        assert "continue-on-error" not in job, name
        for step in job.get("steps", []):
            assert "continue-on-error" not in step, f"{name}: {step}"


def test_publication_pushes_exactly_the_images_it_has_just_built_and_checked():
    publish = workflow(VERIFY)["jobs"]["publish"]
    commands = [step["run"].strip() for step in publish["steps"] if "run" in step]
    # Rebuilt from this commit and checked (service, Action and runtime images), then
    # pushed by `make publish-images`, which publishes nothing unless this commit is
    # still the head of main (scripts/publish_images.py).
    assert commands[-3:] == ["make test-images", "make sandbox-build-all", "make publish-images"]
    # Publications run one at a time, and a queued one is never cancelled by a running one.
    assert publish["concurrency"] == {"group": "publish-main", "cancel-in-progress": False}
    assert publish["permissions"] == {"contents": "read", "packages": "write"}


def test_only_the_gated_jobs_can_push_images():
    # The publish job pushes what verification passed; the release job only re-tags it.
    for path in WORKFLOWS.glob("*.yml"):
        data = workflow(path)
        for name, job in data["jobs"].items():
            text = yaml.safe_dump(job)
            if ("packages" in job.get("permissions", {}) or "docker/login-action" in text
                    or "push: true" in text or "publish-images" in text):
                assert (path, name) in {(VERIFY, "publish"), (RELEASE, "release")}, f"{path.name}: {name}"
        assert "packages" not in data.get("permissions", {}), path.name


def test_nothing_deploys_and_only_the_release_job_can_write_the_repository():
    # ENV-07: the VPS deployment is retired. REL-01: tags and GitHub Releases come
    # only from the release job, and only through `make release` (scripts/release.py).
    for path in WORKFLOWS.glob("*.yml"):
        data = workflow(path)
        text = path.read_text(encoding="utf-8")
        assert "ssh-action" not in text and "SSH_PRIVATE_KEY" not in text, path.name
        assert not re.findall(r"secrets\.(?!GITHUB_TOKEN\b)\w+", text), path.name
        for forbidden in ("git tag", "git push", "gh release", "action-check", "action-publish", "make release"):
            if (path, forbidden) != (RELEASE, "make release"):
                assert forbidden not in text, f"{path.name}: {forbidden}"
        assert data.get("permissions", {}).get("contents", "read") == "read", path.name
        for name, job in data["jobs"].items():
            if job.get("permissions", {}).get("contents", "read") != "read":
                assert (path, name) == (RELEASE, "release"), f"{path.name}: {name}"
    assert set(workflow(VERIFY)["jobs"]) & {"deploy", "action-release"} == set()
    defined, _ = makefile_targets()
    assert defined & {"action-check", "action-publish"} == set()


def test_the_release_runs_only_by_hand_from_main():
    data = workflow(RELEASE)
    # Never triggered by a push, tag, schedule, pull request or another workflow.
    assert set(data["on"]) == {"workflow_dispatch"}
    inputs = data["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"commit", "version"}
    assert all(spec["required"] is True and spec["type"] == "string" for spec in inputs.values())
    [(name, job)] = data["jobs"].items()
    assert name == "release"
    # The scripts that run are main's, never those of the ref it is dispatched from.
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert data["concurrency"] == {"group": "release", "cancel-in-progress": False}
    assert job["permissions"] == {"actions": "read", "contents": "write", "packages": "write"}


def test_the_release_builds_nothing_and_needs_the_published_images_of_its_commit():
    job = workflow(RELEASE)["jobs"]["release"]
    # No `needs`: it depends on the `publish` job of the chosen commit's Verify run,
    # which scripts/release.py looks up by the job's name, and on the sha-<commit>
    # images that job published; it refuses a commit without both.
    assert "needs" not in job
    publish = workflow(VERIFY)["jobs"]["publish"]
    assert publish["name"] == release.PUBLISH_JOB
    commands = [step["run"].strip() for step in job["steps"] if "run" in step]
    assert commands == ["make install", "make release"]
    [checkout] = [step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")]
    assert checkout["with"] == {"fetch-depth": 0}  # the chosen commit and main's history
    # Inputs reach the script only as environment variables, never as shell text.
    [run] = [step for step in job["steps"] if step.get("run", "").strip() == "make release"]
    assert run["env"]["RELEASE_COMMIT"] == "${{ inputs.commit }}"
    assert run["env"]["RELEASE_VERSION"] == "${{ inputs.version }}"
    for step in job["steps"]:
        assert "inputs." not in step.get("run", ""), step
    recipe = make("-n", "release").stdout
    assert "scripts.release" in recipe and '"$RELEASE_COMMIT" "$RELEASE_VERSION"' in recipe


def test_the_documented_required_checks_are_exactly_the_verification_jobs():
    # A job blocks a merge into main only if the ruleset requires it by name; the
    # guide's list is what the ruleset is set to, so it must follow verify.yml.
    jobs = workflow(VERIFY)["jobs"]
    verification = {job["name"] for name, job in jobs.items() if name not in PUBLICATION}
    guide = (ROOT / "docs" / "guides" / "development.md").read_text(encoding="utf-8")
    section = guide.split("### Required checks", 1)[1].split("\n### ", 1)[0]
    required = set(re.findall(r"^- `([^`]+)`", section, re.M))
    assert required == verification


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


def test_lint_fails_on_any_error_whatever_the_repository_score(tmp_path):
    # `make lint` scores the whole tree, so one broken module barely moves the
    # average; the gate must fail on its error, not on the score.
    recipe = make("-n", "lint").stdout
    assert "pylint" in recipe
    assert not re.search(r"--(rcfile|fail-on|fail-under|exit-zero|errors-only|disable)", recipe), recipe
    clean = "".join(f"VALUE_{index} = {index}\n" for index in range(200))
    cases = {"undefined_name.py": clean + "print(missing_name)\n", "syntax_error.py": clean + "def f(:\n"}
    for filename, source in cases.items():
        module = tmp_path / filename
        module.write_text('"""Probe."""\n' + source, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "pylint", f"--rcfile={ROOT / '.pylintrc'}", str(module)],
            cwd=tmp_path, capture_output=True, text=True, check=False, timeout=120)
        assert re.search(r": E\d{4}: ", result.stdout), result.stdout
        assert result.returncode != 0, f"{filename} passed lint:\n{result.stdout}"


def test_lint_runs_in_one_process():
    # Parallel pylint splits modules across workers differently per CPU count,
    # and astroid's inference of SQLAlchemy `Mapped[...]` depends on what a
    # worker loaded first: spurious E1136 errors then fail the gate at random.
    recipe = make("-n", "lint").stdout
    assert not re.search(r"(^|\s)(-j|--jobs)", recipe), recipe
    settings = (ROOT / ".pylintrc").read_text(encoding="utf-8")
    assert re.findall(r"^jobs\s*=\s*(\S+)", settings, re.M) == ["1"]
