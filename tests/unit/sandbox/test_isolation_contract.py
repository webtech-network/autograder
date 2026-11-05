"""SANDBOX.md's isolation guarantees and the tests that pin them stay in step (COR-04)."""
# pylint: disable=missing-function-docstring
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs" / "contracts" / "SANDBOX.md"
SUITE = "tests/integration/test_hostile_submissions.py"


def guarantees() -> dict:
    """Each row of the "Isolation guarantees" table: guarantee -> referenced ``path::test`` ids."""
    text = CONTRACT.read_text(encoding="utf-8")
    section = text.split("### Isolation guarantees", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| ") and not line.startswith("| ---")][1:]
    return {row.split("|")[1].strip(): re.findall(r"`(tests/[\w/]+\.py::\w+)`", row.split("|")[2]) for row in rows}


def defined_tests(path: str) -> set:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}


def test_every_guarantee_names_an_existing_test():
    table = guarantees()
    assert len(table) >= 10
    for guarantee, references in table.items():
        assert references, f"{guarantee!r} names no test"
        for reference in references:
            path, name = reference.split("::")
            assert name in defined_tests(path), f"{guarantee!r}: {reference} does not exist"


def test_every_hostile_submission_test_is_a_stated_guarantee():
    referenced = {reference.split("::")[1] for references in guarantees().values() for reference in references
                  if reference.startswith(SUITE)}
    assert defined_tests(SUITE) == referenced
