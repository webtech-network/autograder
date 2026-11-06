"""The project ships as one installable distribution with exact dependencies (ENV-01, #422).

These checks build the real wheel and import it outside the checkout, so a module
that works only because the repository root is on ``sys.path`` fails here, and
they compare the declared runtime dependencies with what the code imports.
"""
# pylint: disable=missing-function-docstring
import ast
import importlib.metadata
import json
import re
import subprocess
import sys
import sysconfig
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
PACKAGES = ("autograder", "execution_host", "github_action", "sandbox_manager", "web")
#: Declared but never imported by name: SQLAlchemy loads the driver named in DATABASE_URL.
DATABASE_DRIVERS = {"asyncpg", "aiosqlite"}
#: Imported directly but installed and versioned by the declared SDK.
PROVIDED_BY = {"botocore": "boto3"}


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_names(requirements):
    return {canonical(re.match(r"[A-Za-z0-9._-]+", value).group()) for value in requirements}


def first_party_files(package):
    return sorted((ROOT / package).rglob("*.py"))


def imported_names(path):
    """Absolute imports anywhere in a file, including lazy imports inside functions."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


def third_party_distributions(names):
    distributions = importlib.metadata.packages_distributions()
    found = set()
    for name in names:
        root = name.split(".")[0]
        if root in PACKAGES or root in sys.stdlib_module_names:
            continue
        found.add(canonical(PROVIDED_BY.get(root) or distributions.get(root, [root])[0]))
    return found


def test_runtime_dependencies_are_exactly_what_the_shipped_packages_import():
    declared = requirement_names(PROJECT["dependencies"]) | requirement_names(
        PROJECT["optional-dependencies"]["server"])
    imported = third_party_distributions(
        name for package in PACKAGES for path in first_party_files(package) for name in imported_names(path))
    assert imported | DATABASE_DRIVERS == declared
    assert not declared & {"pytest", "pytest-asyncio", "pytest-cov", "httpx", "pylint", "mkdocs"}


def test_action_host_needs_no_server_dependency():
    """Everything the Action can reach, lazy imports included, installs without the server extra."""
    pending = first_party_files("github_action")
    seen, names = set(), set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        for name in imported_names(path):
            names.add(name)
            if name.split(".")[0] in PACKAGES:
                module = ROOT / name.replace(".", "/")
                pending += [candidate for candidate in (module.with_suffix(".py"), module / "__init__.py")
                            if candidate.is_file()]
    assert third_party_distributions(names) <= requirement_names(PROJECT["dependencies"])


def test_non_editable_wheel_imports_every_first_party_module_outside_the_checkout(tmp_path):
    wheel = subprocess.run(
        [sys.executable, "-c", f"from hatchling.build import build_wheel; print(build_wheel({str(tmp_path)!r}))"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    installed = tmp_path / "site"
    with zipfile.ZipFile(tmp_path / wheel) as archive:
        archive.extractall(installed)
        names = archive.namelist()
    assert {name.split("/")[0] for name in names} == {*PACKAGES, wheel.rsplit("-", 3)[0] + ".dist-info"}
    assert {"autograder/translations/en.json", "web/alembic.ini", "web/migrations/env.py"} <= set(names)
    assert not [name for name in names if "__pycache__" in name or name.endswith(".pyc")]

    # -I -S: no checkout, no PYTHONPATH and no .pth files (the editable install's
    # root path); only the extracted wheel and the third-party site-packages.
    script = (
        "import importlib, json, pkgutil, sys\n"
        f"sys.path[:0] = [{str(installed)!r}, {sysconfig.get_path('purelib')!r}, {sysconfig.get_path('platlib')!r}]\n"
        f"packages = {PACKAGES!r}\n"
        "modules = {}\n"
        "for package in packages:\n"
        "    root = importlib.import_module(package)\n"
        "    modules[package] = root.__file__\n"
        "    for info in pkgutil.walk_packages(root.__path__, package + '.'):\n"
        "        if not info.name.endswith('.__main__'):\n"
        "            modules[info.name] = importlib.import_module(info.name).__file__\n"
        "from autograder.translations import t\n"
        "absent = [name for name in ('tests', 'examples', 'submission_contract')\n"
        "          if importlib.util.find_spec(name) is not None]\n"
        "print(json.dumps({'modules': modules, 'absent': absent, 'message': t('preflight.error.required_file_missing', locale='en', files='x')}))\n"
    )
    run = subprocess.run([sys.executable, "-I", "-S", "-c", script], cwd=tmp_path, capture_output=True, text=True,
                         check=False)
    assert run.returncode == 0, run.stderr
    report = json.loads(run.stdout)
    outside = {name: path for name, path in report["modules"].items() if not path.startswith(str(installed))}
    assert outside == {}
    assert len(report["modules"]) > 100
    assert report["absent"] == []
    assert report["message"].startswith("Required file not found: x.")  # package data is shipped
