"""Every environment variable a host reads is documented, and nothing else is (ENV-05, #426).

The operator reference ``docs/operate/configuration.md`` has one table per host.
This test reads the shipped code, finds every environment variable it reads and
compares the two in both directions: an undocumented read fails, and so does a
documented variable that no code of that host reads. Retired names are listed
once in code (the host refuses to start while one is set) and once in the docs.
"""
# pylint: disable=missing-function-docstring
import ast
import re
from pathlib import Path

import pytest

from sandbox_manager.api import RETIRED as SANDBOX_RETIRED
from web.core.config import RETIRED as API_RETIRED

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "docs" / "operate" / "configuration.md"
#: Which host a package's environment reads configure. The shared execution
#: providers (fixtures, AI, sandbox client) are composed by the API and the Action.
#: The engine is configured only through its Python arguments.
HOSTS_BY_PACKAGE = {
    "autograder": set(),
    "web": {"api"},
    "sandbox_manager": {"sandbox"},
    "execution_host": {"api", "action"},
    "github_action": {"action"},
}
SECTIONS = {"API service": "api", "Sandbox manager": "sandbox", "GitHub Action": "action",
            "Retired variables": "retired"}
#: Names conventionally bound to the process environment (``config = os.environ ...``).
ENVIRONMENT_NAMES = {"os.environ", "environ", "env", "config"}
VARIABLE = re.compile(r"[A-Z][A-Z0-9_]*")


def _is_environment(node) -> bool:
    return ast.unparse(node) in ENVIRONMENT_NAMES


def _read_name(call: ast.Call, helpers: set[str]):
    """The argument naming the variable when ``call`` reads the environment, else None."""
    function = call.func
    reads = ((isinstance(function, ast.Attribute) and function.attr == "getenv")
             or (isinstance(function, ast.Name) and function.id in helpers | {"getenv"})
             or (isinstance(function, ast.Attribute) and function.attr == "get"
                 and _is_environment(function.value)))
    return call.args[0] if reads and call.args else None


def environment_reads(source: str) -> tuple[set[str], list[str]]:
    """Variable names read by ``source`` and any reads whose name is not a literal.

    A module-level function that reads the environment with its first parameter
    (``def _flag(name, default): ... os.environ.get(name)``) is a reading helper:
    its calls read the literal they pass.
    """
    tree = ast.parse(source)
    helpers = set()
    for function in tree.body:
        if isinstance(function, ast.FunctionDef) and function.args.args:
            parameter = function.args.args[0].arg
            for node in ast.walk(function):
                argument = _read_name(node, set()) if isinstance(node, ast.Call) else None
                if isinstance(argument, ast.Name) and argument.id == parameter:
                    helpers.add(function.name)
    names, dynamic = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            argument = _read_name(node, helpers)
        elif isinstance(node, ast.Subscript) and _is_environment(node.value):
            argument = node.slice
        else:
            continue
        if argument is None:
            continue
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            if VARIABLE.fullmatch(argument.value):  # lower-case keys index parsed JSON, not the environment
                names.add(argument.value)
        elif not any(isinstance(helper, ast.FunctionDef) and helper.name in helpers
                     and argument in ast.walk(helper) for helper in tree.body):
            dynamic.append(f"line {node.lineno}: {ast.unparse(node)}")
    return names, dynamic


def code_reads() -> dict[str, dict[str, set[str]]]:
    """host -> variable -> files reading it."""
    reads: dict[str, dict[str, set[str]]] = {}
    for package, hosts in HOSTS_BY_PACKAGE.items():
        for path in sorted((ROOT / package).rglob("*.py")):
            names, dynamic = environment_reads(path.read_text(encoding="utf-8"))
            relative = path.relative_to(ROOT).as_posix()
            assert not dynamic, f"{relative} reads a variable whose name is not a literal: {dynamic}"
            assert not names or hosts, f"{relative} (the engine) reads the environment: {sorted(names)}"
            for host in hosts:
                for name in names:
                    reads.setdefault(host, {}).setdefault(name, set()).add(relative)
    return reads


def documented() -> dict[str, set[str]]:
    """section -> variables named in the first column of its tables."""
    tables: dict[str, set[str]] = {section: set() for section in SECTIONS.values()}
    section = None
    for line in REFERENCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = SECTIONS.get(line[3:].strip())
        elif section and (match := re.match(r"\|\s*`([A-Z][A-Z0-9_]*)`\s*\|", line)):
            tables[section].add(match.group(1))
    return tables


def test_the_reader_finds_every_supported_form_of_read():
    names, dynamic = environment_reads(
        "import os\n"
        "def _flag(name, default):\n    return os.environ.get(name, default)\n"
        "A = os.getenv('A')\nB = os.environ['B']\nC = os.environ.get('C')\nD = _flag('D', False)\n"
        "def f(environ=None):\n    config = os.environ if environ is None else environ\n"
        "    return config.get('E'), env.get('F')\n"
        "G = os.getenv(name)\n")
    assert names == {"A", "B", "C", "D", "E", "F"}
    assert dynamic == ["line 11: os.getenv(name)"]


def test_every_read_is_documented_for_its_host():
    tables = documented()
    for host, variables in code_reads().items():
        missing = {name: sorted(files) for name, files in variables.items() if name not in tables[host]}
        assert not missing, f"Undocumented {host} variables (add them to {REFERENCE.name}): {missing}"


def test_every_documented_variable_is_read_by_its_host():
    reads = code_reads()
    for host in ("api", "sandbox", "action"):
        unread = documented()[host] - set(reads.get(host, {}))
        assert not unread, f"{REFERENCE.name} documents {host} variables no code reads: {sorted(unread)}"


def test_retired_variables_are_documented_rejected_and_never_read():
    retired = set(API_RETIRED) | set(SANDBOX_RETIRED)
    assert documented()["retired"] == retired
    for host, variables in code_reads().items():
        assert not retired & set(variables), f"{host} still reads {sorted(retired & set(variables))}"
    for hint in (*API_RETIRED.values(), *SANDBOX_RETIRED.values()):
        assert hint.strip(), "every retired name carries a migration hint"


def test_reference_names_valid_variables_only():
    for section, names in documented().items():
        assert names, f"{section} table is empty or its heading changed"
        assert all(VARIABLE.fullmatch(name) for name in names)


@pytest.mark.parametrize("path", [".env.example"])
def test_no_orphaned_variable_files(path):
    # Nothing loads them; the reference above is the only list of settings.
    assert not (ROOT / path).exists()
