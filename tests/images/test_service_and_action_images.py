"""ENV-04: the API, sandbox manager and Action images hold only what their process needs.

`make test-images` builds the three images from this checkout and runs these
checks against exactly those images (CI does the same from scratch). A missing
image or an unreachable Docker daemon is a failure here, never a skip.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PREFIX = os.environ.get("AUTOGRADER_IMAGE_PREFIX", "autograder")
TAG = os.environ.get("AUTOGRADER_IMAGE_TAG", "local")

#: image name -> (Dockerfile, the first-party paths its process imports or reads).
IMAGES = {
    "api": ("Dockerfile.api", {"autograder", "execution_host", "sandbox_manager", "web", "sandbox_config.yml"}),
    "sandbox-manager": ("Dockerfile.sandbox", {"autograder", "sandbox_manager", "sandbox_config.yml"}),
    "action": ("Dockerfile.actions", {"autograder", "execution_host", "sandbox_manager", "github_action",
                                      "sandbox_config.yml"}),
}
#: Development tools never ship (pip distribution names).
DEVELOPMENT = {"pytest", "pytest-asyncio", "pytest-cov", "coverage", "pylint", "astroid", "mkdocs",
               "mkdocs-material", "hatchling"}
#: The HTTP service's web and database stack.
DATABASE = {"sqlalchemy", "alembic", "asyncpg", "aiosqlite", "mako"}
WEB = {"fastapi", "starlette", "uvicorn"}
FORBIDDEN_DISTRIBUTIONS = {
    "api": DEVELOPMENT,
    "sandbox-manager": DEVELOPMENT | DATABASE,
    "action": DEVELOPMENT | DATABASE | WEB,
}
#: Executables no image needs: container daemons and CLIs, Node.js, downloaders.
FORBIDDEN_TOOLS = ("dockerd", "containerd", "containerd-shim-runc-v2", "runc", "docker", "node", "nodejs",
                   "npm", "npx", "curl", "wget", "tree", "pytest")
#: Printed by a Python one-liner inside an image: every installed distribution.
DISTRIBUTIONS = ("import importlib.metadata as m, json; "
                 "print(json.dumps(sorted({d.metadata['Name'].lower().replace('_', '-') for d in m.distributions()})))")


def image(name: str) -> str:
    return f"{PREFIX}-{name}:{TAG}"


def docker(*args: str, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, check=False, timeout=timeout)
    if check and result.returncode != 0:
        raise AssertionError(f"docker {' '.join(args)} failed ({result.returncode}):\n{result.stderr}")
    return result


def run(reference: str, *command: str, entrypoint: str = "") -> str:
    """Run `command` in a throwaway container without network; return its stdout."""
    return docker("run", "--rm", "--network", "none", "--entrypoint", entrypoint or command[0],
                  reference, *command[1:]).stdout


@pytest.fixture(scope="module", autouse=True)
def built_images():
    for name in IMAGES:
        assert docker("image", "inspect", image(name), check=False).returncode == 0, (
            f"{image(name)} is missing: run `make test-images` (it builds the images first)")


@pytest.mark.parametrize("name", IMAGES)
def test_image_holds_one_python_and_no_development_web_or_database_stack(name):
    assert run(image(name), "python", "--version").startswith("Python 3.13.")
    installed = set(json.loads(run(image(name), "python", "-c", DISTRIBUTIONS)))
    assert installed & FORBIDDEN_DISTRIBUTIONS[name] == set()
    if name == "action":
        assert "docker" in installed  # the engine's execution host, not the daemon


@pytest.mark.parametrize("name", IMAGES)
def test_image_ships_no_container_daemon_node_or_downloader(name):
    script = " ".join(["for tool in", *FORBIDDEN_TOOLS, "; do command -v $tool; done; true"])
    present = run(image(name), "sh", "-c", script).split()
    assert present == [], f"{image(name)} ships {present}"
    if name == "action":
        assert run(image(name), "git", "--version").startswith("git version")  # provenance reads the checkout


@pytest.mark.parametrize("name", IMAGES)
def test_image_application_directory_is_the_allow_list(name):
    _, expected = IMAGES[name]
    assert set(run(image(name), "ls", "-A", "/app").split()) == expected


def test_each_service_process_imports_with_its_image_dependencies():
    run(image("api"), "python", "-c", "import web.main, alembic.config")
    run(image("sandbox-manager"), "python", "-c", "import sandbox_manager.api")


# --- No file of the build context outside the allow-list reaches an image -----------

SENTINEL = f"ENV04-LEAK-SENTINEL-{uuid.uuid4().hex}"
#: Files a maintainer checkout really has (ignored by git, present on disk).
PLANTED = (".env", ".env.production", ".venv/lib/python3.13/site-packages/planted-secret.py",
           "data/receipts/planted-secret.json", "test.db", "secrets.json", "web/.env", "autograder/.env",
           "github_action/__pycache__/planted-secret.cpython-313.pyc", "sandbox_manager/.venv/planted-secret.py")


@pytest.fixture(scope="module")
def planted_checkout(tmp_path_factory):
    """A copy of this checkout (files git does not ignore) plus ignored secrets and caches."""
    checkout = tmp_path_factory.mktemp("checkout")
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                            capture_output=True, check=True)
    for relative in filter(None, listed.stdout.decode().split("\0")):
        source = ROOT / relative
        if source.is_file():
            (checkout / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, checkout / relative)
    for relative in PLANTED:
        (checkout / relative).parent.mkdir(parents=True, exist_ok=True)
        (checkout / relative).write_text(f"SECRET = '{SENTINEL}'\n", encoding="utf-8")
    return checkout


@pytest.mark.parametrize("name", IMAGES)
def test_image_built_from_a_checkout_with_secrets_contains_none_of_them(name, planted_checkout):
    dockerfile, expected = IMAGES[name]
    reference = f"{PREFIX}-leakcheck-{name}:{uuid.uuid4().hex[:12]}"
    docker("build", "--quiet", "--tag", reference, "--file", str(planted_checkout / dockerfile),
           str(planted_checkout))
    try:
        found = run(reference, "sh", "-c",
                    f"grep -rlsI --exclude-dir=proc --exclude-dir=sys --exclude-dir=dev {SENTINEL} / ; "
                    "find / -xdev \\( -name '.env*' -o -name '.venv' -o -name '*.db' -o -name 'planted-secret*' "
                    "-o -name 'secrets.json' -o -path '/app/tests' -o -path '/app/docs' -o -path '/app/data' \\) "
                    "-print; true")
        assert found.split() == [], f"{reference} contains {found.split()}"
        assert set(run(reference, "ls", "-A", "/app").split()) == expected
    finally:
        docker("image", "rm", "--force", reference, check=False)


# --- The Action pulls a prebuilt image and grades the static example with it --------

ACTION = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
INPUT = re.compile(r"\$\{\{\s*inputs\.([\w-]+)\s*\}\}")


def action_environment(**inputs: str) -> dict:
    """The variables GitHub derives from `runs.env` for these inputs and the declared defaults."""
    values = {name: spec.get("default", "") for name, spec in ACTION["inputs"].items()} | inputs
    return {variable: INPUT.sub(lambda match: values[match.group(1)], template)
            for variable, template in ACTION["runs"]["env"].items()}


def test_action_grades_the_static_example_in_its_image(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / ".github/autograder").mkdir(parents=True)
    shutil.copy(ROOT / "docs/contracts/v1/examples/static-conformance.json",
                workspace / ".github/autograder/definition.json")
    (workspace / "index.html").write_text("<!doctype html><title>ok</title>\n", encoding="utf-8")
    commands = tmp_path / "file_commands"
    commands.mkdir()
    environment = {**action_environment(), "GITHUB_WORKSPACE": "/github/workspace", "GITHUB_ACTIONS": "true",
                   "GITHUB_OUTPUT": "/github/file_commands/output",
                   "GITHUB_STEP_SUMMARY": "/github/file_commands/summary"}
    # As the runner invokes a container action: workspace mounted, workdir set, the image's entrypoint.
    arguments = ["run", "--rm", "--network", "none", "--workdir", "/github/workspace",
                 "--volume", f"{workspace}:/github/workspace", "--volume", f"{commands}:/github/file_commands"]
    for variable, value in environment.items():
        arguments += ["--env", f"{variable}={value}"]
    try:
        result = docker(*arguments, image("action"), check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        outcome = json.loads((workspace / ".autograder/outcome.json").read_text(encoding="utf-8"))
        outputs = (commands / "output").read_text(encoding="utf-8")
    finally:
        # The action runs as root, as on a hosted runner: hand the files back to this user.
        docker("run", "--rm", "--network", "none", "--entrypoint", "chown", "--volume", f"{tmp_path}:/work",
               image("action"), "-R", f"{os.getuid()}:{os.getgid()}", "/work", check=False)
    assert outcome["status"] == "completed" and outcome["score"] == 100
    assert "status=completed" in outputs and "score=100" in outputs
