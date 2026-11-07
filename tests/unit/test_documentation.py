"""The documentation is organized around tasks and every authoring snippet runs (ONB-05, #431).

A teacher follows the Author section from the tutorial to a graded assignment.
These checks keep that path executable and keep each fact in one place:

* every JSON block on an Author page either is a checked-in example, or is
  marked as a fragment of one (it must compile merged into it), as a rejected
  fragment (it must fail with exactly the error shown next), or as an excerpt of
  a real outcome (checked in Docker by ``tests/integration/test_tutorial_assignments.py``);
* every Python block on an Author page runs;
* the final-score arithmetic and the penalty polarity rule live on one page, and
  its worked examples are what grading computes;
* removed pages stay removed, every page is in the navigation and redirected
  old addresses land on existing pages;
* Author and Extend pages describe current behaviour only.
"""
# pylint: disable=missing-function-docstring
import json
import re
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from autograder import DefinitionValidationError, compile_definition, describe_templates
from autograder.models.dataclass.test_result import TestResult as Result
from autograder.services.grading import grade

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
AUTHOR = DOCS / "author"
EXAMPLES = ROOT / "examples"
TUTORIAL = EXAMPLES / "tutorial"
REPOSITORY_BLOB = "https://github.com/webtech-network/autograder/blob/main/"

#: Marker comment that may precede a fenced block: ``<!-- kind: argument -->``.
MARKER = re.compile(r"<!--\s*([\w-]+)(?::\s*(.*?))?\s*-->\s*$")
BLOCK = re.compile(r"^```(\w*)\n(.*?)^```", re.S | re.M)


def nav_pages():
    def walk(entries):
        for entry in entries:
            value = list(entry.values())[0] if isinstance(entry, dict) else entry
            if isinstance(value, list):
                yield from walk(value)
            else:
                yield value
    return list(walk(mkdocs_config()["nav"]))


def mkdocs_config():
    return yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))


def blocks(path):
    """``(language, body, marker kind, marker argument)`` for every fenced block of a page."""
    text = path.read_text(encoding="utf-8")
    for match in BLOCK.finditer(text):
        before = text[:match.start()].rstrip("\n").splitlines()
        marker = MARKER.match(before[-1].strip()) if before else None
        kind, argument = (marker.group(1), (marker.group(2) or "").strip()) if marker else (None, None)
        yield match.group(1), match.group(2), kind, argument


def author_pages():
    return sorted(AUTHOR.glob("*.md"))


def merged(base, fragment):
    """``fragment`` deep-merged into ``base``; a criterion fragment becomes the base's only criterion."""
    result = deepcopy(base)
    if "type" in fragment:
        result["criteria"] = {"base": {"tests": [fragment]}}
        return result

    def merge(target, source):
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = deepcopy(value)
    merge(result, fragment)
    return result


def example_definitions():
    """Every valid definition checked in under examples/ (its path relative to the root)."""
    found = {}
    for path in sorted(EXAMPLES.rglob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and "schema_version" in value and "invalid" not in path.parts:
            found[path.relative_to(ROOT).as_posix()] = value
    return found


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


# --- The Author path ------------------------------------------------------------

def test_the_author_section_starts_with_the_tutorial_and_ends_with_the_generated_reference():
    nav = mkdocs_config()["nav"]
    sections = [next(iter(entry)) for entry in nav]
    assert sections[:5] == ["Home", "Author", "Integrate", "Extend", "Operate and Contribute"]
    author = [next(iter(entry.values())) for entry in nav[1]["Author"]]
    assert author[0] == "author/tutorial.md"
    assert author[-2:] == ["reference/evaluators.md", "reference/definition.md"]
    assert all(page.startswith(("author/", "reference/")) for page in author)


def test_every_author_json_block_is_an_example_or_an_exercised_fragment():
    examples = example_definitions()
    exercised = 0
    for page in author_pages():
        pending_rejection = None
        for language, body, kind, argument in blocks(page):
            if language != "json":
                continue
            where = f"{page.relative_to(ROOT)}: {body[:60]!r}"
            value = json.loads(body)
            if pending_rejection is not None:
                assert kind == "validate-response", f"{where}: a rejected fragment needs its response next"
                assert value == {"detail": pending_rejection}, where
                pending_rejection = None
            elif kind is None:
                assert value in examples.values(), f"{where}: not a checked-in example and not marked"
            elif kind == "fragment":
                compile_definition(merged(load(argument), value))
            elif kind == "rejected":
                with pytest.raises(DefinitionValidationError) as rejected:
                    compile_definition(merged(load(argument), value))
                pending_rejection = rejected.value.errors()
            elif kind == "outcome":
                # Graded in Docker by tests/integration/test_tutorial_assignments.py.
                assert (ROOT / argument).is_dir() and (ROOT / argument).parent.joinpath("definition.json").is_file()
            else:
                pytest.fail(f"{where}: unknown marker {kind!r}")
            exercised += 1
        assert pending_rejection is None, f"{page}: rejected fragment without its response"
    assert exercised >= 10


def test_the_tutorial_shows_each_assignment_definition_exactly_as_checked_in():
    tutorial = [json.loads(body) for language, body, kind, _ in blocks(AUTHOR / "tutorial.md")
                if language == "json" and kind is None]
    for assignment in ("python-io", "web-page", "compiled"):
        assert load(f"examples/tutorial/{assignment}/definition.json") in tutorial, assignment


def test_every_tutorial_assignment_has_a_good_and_a_bad_submission_that_the_tutorial_scores():
    rows = tutorial_score_rows()
    for assignment in sorted(path for path in TUTORIAL.iterdir() if path.is_dir()):
        for variant in ("good", "bad"):
            assert any((assignment / variant).iterdir()), (assignment, variant)
            assert any(row[0] == f"examples/tutorial/{assignment.name}/{variant}" for row in rows), (assignment, variant)


def tutorial_score_rows():
    """``(submission directory, language, score)`` rows of the tutorial's score table."""
    text = (AUTHOR / "tutorial.md").read_text(encoding="utf-8")
    return [(path, language, float(score)) for path, language, score in
            re.findall(r"^\| `(examples/tutorial/[\w-]+/(?:good|bad))` \| `(\w+)` \| \*\*([\d.]+)\*\* \|$", text, re.M)]


def test_every_author_python_block_runs(monkeypatch):
    monkeypatch.chdir(ROOT)
    ran = 0
    for page in author_pages():
        for language, body, kind, _ in blocks(page):
            if language == "python":
                assert kind == "runs", f"{page}: Python block without <!-- runs -->"
                exec(compile(body, str(page), "exec"), {"__name__": "__docs__"})  # pylint: disable=exec-used
                ran += 1
    assert ran >= 1


def test_every_marked_block_names_a_real_submission_or_example():
    for page in author_pages():
        for language, _, kind, argument in blocks(page):
            if kind in {"outcome", "report"}:
                assert language == ("json" if kind == "outcome" else "markdown"), (page, kind)
                assert (ROOT / argument).is_dir() and (ROOT / argument).parent.joinpath("definition.json").is_file()
            elif kind in {"fragment", "rejected"}:
                assert (ROOT / argument).is_file(), (page, argument)


def test_the_forbidden_keyword_table_lists_the_supported_constructs():
    from autograder.template_library.static_analysis import ForbiddenKeywordTest  # pylint: disable=import-outside-toplevel
    text = (AUTHOR / "preparation.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| `(\w+)` \| (`.*`) \|$", text, re.M))
    assert {language: re.findall(r"`(\w+)`", constructs) for language, constructs in rows.items()} == {
        language.value: list(rules) for language, rules in ForbiddenKeywordTest.PREDEFINED_RULES.items()}


def test_every_example_file_a_shell_block_names_exists():
    for page in author_pages():
        for language, body, _, _ in blocks(page):
            if language in {"bash", "sh", "shell"}:
                for name in re.findall(r"@?(examples/[\w./-]+)", body):
                    assert (ROOT / name).exists(), (page, name)


# --- Scores: one page, and it is right -----------------------------------------

#: The final-score formula and the polarity rule, in the words a page would use.
ARITHMETIC = re.compile(
    r"\(\s*100\s*[-−]\s*(score|penalty)[^)]*\)\s*/\s*100|bonus\s*/\s*100|score\s*/\s*100\s*[×*]"
    r"|scores? 100 when the student (complied|did what)", re.I)


def test_final_score_arithmetic_and_the_polarity_rule_have_exactly_one_page():
    pages = [*DOCS.rglob("*.md"), ROOT / "README.md", *EXAMPLES.rglob("*.md")]
    homes = sorted(path.relative_to(ROOT).as_posix() for path in pages
                   if ARITHMETIC.search(path.read_text(encoding="utf-8")))
    assert homes == ["docs/author/scoring.md"]
    text = (AUTHOR / "scoring.md").read_text(encoding="utf-8")
    assert re.search(r"scores 100 when the student complied", text)


def worked_examples():
    text = (AUTHOR / "scoring.md").read_text(encoding="utf-8")
    for match in re.finditer(r"<!-- worked-example: (\S+) -->\n(.*?)Final score: \*\*([\d.]+)\*\*", text, re.S):
        scores = {criterion: float(score) for criterion, score in
                  re.findall(r"^\| `([\w-]+)` \|[^|\n]*\| ([\d.]+) \|", match.group(2), re.M)}
        yield match.group(1), scores, float(match.group(3))


def test_the_worked_examples_are_what_grading_computes():
    checked = 0
    for definition, scores, final in worked_examples():
        compiled = compile_definition(load(definition))
        ids = {test.criterion_id for test in compiled.criteria_tree.get_all_tests()}
        assert set(scores) == ids, definition
        tree = grade(compiled.criteria_tree, {i: Result("doc", s, "") for i, s in scores.items()})
        assert tree.score == final, (definition, tree.score)
        checked += 1
    assert checked >= 2


# --- Structure: removed stays removed, everything reachable --------------------

REMOVED = ["docs/pipeline", "docs/core", "docs/template-library", "docs/features",
           "docs/guides/github_module.md", "docs/guides/criteria_configuration_examples.md",
           "docs/guides/criteria-tree-educational-standards.md", "docs/architecture/core_structures.md",
           "docs/architecture/pipeline_execution_tracking.md", "docs/criteria_example.json",
           "docs/contracts/v1/examples"]


@pytest.mark.parametrize("path", REMOVED)
def test_internal_historical_and_duplicate_pages_stay_removed(path):
    assert not (ROOT / path).exists()


def test_every_page_is_in_the_navigation_and_every_navigation_entry_exists():
    pages = sorted(path.relative_to(DOCS).as_posix() for path in DOCS.rglob("*.md"))
    nav = nav_pages()
    assert len(nav) == len(set(nav))
    assert sorted(nav) == pages


def test_old_addresses_redirect_to_existing_pages():
    plugins = mkdocs_config()["plugins"]
    [redirects] = [entry["redirects"] for entry in plugins if isinstance(entry, dict) and "redirects" in entry]
    targets = redirects["redirect_maps"]
    for removed in REMOVED:
        page = removed.removeprefix("docs/")
        if page.endswith(".md"):
            assert page in targets, removed
        elif "/" not in page and "." not in page:
            assert any(old.startswith(page + "/") for old in targets), removed
    for old, new in targets.items():
        assert not (DOCS / old).exists(), old
        assert (DOCS / new.split("#")[0]).is_file(), new


def test_examples_live_only_under_examples():
    stray = [path.relative_to(ROOT).as_posix() for path in DOCS.rglob("*.json")
             if path.parent != DOCS / "contracts" / "v1"]
    assert stray == []


#: Words that narrate history instead of describing what the code does now.
HISTORY = re.compile(r"\b(former(ly)?|no longer|(was|were|has been|have been) (removed|retired|renamed|replaced)"
                     r"|legacy|deprecated|used to|migrat\w*)\b", re.I)


def extend_pages():
    nav = mkdocs_config()["nav"]
    [extend] = [entry["Extend"] for entry in nav if "Extend" in entry]
    return [DOCS / next(iter(entry.values())) for entry in extend]


def test_author_and_extend_pages_describe_current_behaviour_only():
    pages = [*author_pages(), *extend_pages()]
    assert len(pages) >= 8
    offenders = [f"{page.relative_to(ROOT)}:{number}: {line.strip()}"
                 for page in pages for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1)
                 if HISTORY.search(line)]
    assert offenders == []


def test_repository_links_from_docs_point_at_existing_files():
    for page in [*DOCS.rglob("*.md"), ROOT / "README.md"]:
        for target in re.findall(re.escape(REPOSITORY_BLOB) + r"([^)#\s]+)", page.read_text(encoding="utf-8")):
            assert (ROOT / target).exists(), (page, target)


# --- README and demo claims -----------------------------------------------------

def test_readme_claims_only_what_the_shipped_hosts_run():
    from tests.unit.test_generated_reference import shipped_unavailable  # pylint: disable=import-outside-toplevel
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    unavailable = set(shipped_unavailable())
    for template in describe_templates().templates:
        for evaluator in template.evaluators:
            if set(evaluator.required_capabilities) & unavailable:
                assert f"`{evaluator.identifier}`" not in readme, evaluator.identifier
        if all(set(e.required_capabilities) & unavailable for e in template.evaluators):
            assert template.name not in readme and f"`{template.identifier}`" not in readme, template.identifier
    assert not re.search(r"\bAPIs\b|API testing", readme, re.I)


def test_demo_instructions_name_the_address_the_demo_serves():
    served = re.search(r"http://localhost:\{PORT\}(/\w+/)", (EXAMPLES / "demo/serve_demo.py").read_text()).group(1)
    for page in (ROOT / "README.md", EXAMPLES / "README.md", EXAMPLES / "demo/README.md"):
        addresses = re.findall(r"http://localhost:8080[^\s)`*]*", page.read_text(encoding="utf-8"))
        assert addresses and set(addresses) == {f"http://localhost:8080{served}"}, page


def test_demo_instructions_require_the_token_for_every_protected_read():
    # AUTH.md: polling, history and details all need the integration token.
    for page in (EXAMPLES / "README.md", EXAMPLES / "demo/README.md"):
        text = page.read_text(encoding="utf-8")
        assert "token" in text, page
        for sentence in re.split(r"(?<=\.)\s", " ".join(text.split())):
            if "poll" in sentence.lower() and "token" in sentence.lower():
                assert not re.search(r"\bnot\b|n't\b|\bwithout\b", sentence), (page, sentence)
