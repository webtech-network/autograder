"""The default report explains the authored rubric and the score (ARC-12, ONB-03).

Golden reports are rendered from real canonical outcomes (the pipeline grades a
fixed-score evaluator) in both locales; record them with
``AUTOGRADER_RECORD_GOLDEN=1``. A seeded property test reconciles the rendered
points with ``final_score`` over generated trees.
"""
import importlib
import os
import random
import re
from copy import deepcopy
from pathlib import Path

import pytest

from autograder import EvaluationInput, Submission, SubmissionFile, Template, TestFunction, TestResult, build_pipeline
from autograder.models.contracts.definition import FeedbackPreferences
from autograder.models.contracts.outcome import ResultOutcomeTree
from autograder.models.contracts.scoring import criterion_points, final_score, iter_tests
from autograder.services.feedback import render_feedback
from autograder.services.focus_service import find_focus
from tests.grading import leaf

GOLDEN = Path(__file__).with_name("feedback_golden")
LOCALES = ("en", "pt_br")
STATUS_ICONS = ("✅", "❌", "⚠️")


class Fixed(TestFunction):
    """Returns the configured score; ``secret`` is a parameter its report never shows."""
    name = "fixed"
    description = "Fixed score."

    def execute(self, evaluation: EvaluationInput, *, score: float, secret: str = "",
                report: str = "") -> TestResult:
        return TestResult(self.name, score, report)


def fixed(identity, score, weight=1, name=None, report="", **parameters):
    return {"id": identity, "type": "fixed", "name": name or identity, "weight": weight,
            "parameters": {"score": score, "report": report, **parameters}}


def subject(name, weight, *, tests=(), subjects=(), subjects_weight=None):
    value = {"subject_name": name, "weight": weight, "tests": list(tests), "subjects": list(subjects)}
    if subjects_weight is not None:
        value["subjects_weight"] = subjects_weight
    return {key: item for key, item in value.items() if item != []}


def outcome(criteria, feedback=None, locale="en"):
    definition = {"schema_version": "1.0", "templates": ["local"], "languages": ["python"], "criteria": criteria,
                  "feedback": {"enabled": True, **(feedback or {})}}
    pipeline = build_pipeline(definition=definition, templates={"local": Template("Local", "Fixed.", [Fixed()])})
    result = pipeline.run(Submission("u", "u", "a", {"main.py": SubmissionFile("main.py", "")}, locale=locale)).outcome
    assert result.status == "completed", result.error
    assert result.feedback.status == "completed", result.feedback.error
    return result


def headings(content):
    return [line for line in content.splitlines() if line.startswith("#")]


# --- Canonical rubrics ------------------------------------------------------------

def rubric():
    """Nested subjects, a mixed ``subjects_weight`` group, all-zero siblings, a zero-weight
    test, repeated slash labels, partial scores, bonus and penalty."""
    return {
        "base": {"weight": 100, "subjects": [
            subject("Program / IO", 3, tests=[
                fixed("sum", 0, 2, "Check / output", "Expected: 5\nActual: 4", secret="EXPECTED-5"),
                fixed("sum-large", 100, 1, "Check / output", "Output matches."),
                fixed("no-crash", 0, 0, "Does not crash", "Your program crashed.\n\n    Traceback: ValueError")]),
            subject("Quality", 1, subjects_weight=60, subjects=[
                subject("Imports", 0, tests=[fixed("imports", 0, name="Check / output",
                                                   report="Forbidden import: os")]),
                subject("Keywords", 0, tests=[fixed("loops", 100, name="No loops", report="No loops found.")]),
            ], tests=[fixed("artifact", 50, name="Writes result", report="out.txt differs on line 2")]),
        ]},
        "bonus": {"weight": 10, "tests": [fixed("bonus-sum", 50, name="Bonus / large", report="1 of 2 large sums")]},
        "penalty": {"weight": 20, "subjects": [subject("Style", 1, tests=[
            fixed("no-subprocess", 0, name="Avoid subprocess", report="Forbidden import: subprocess"),
            fixed("no-eval", 100, name="Avoid eval", report="No eval found.")])]},
    }


def perfect():
    """Every criterion passed and the bonus earned: the final score is capped at 100."""
    return {"base": {"weight": 100, "tests": [fixed("a", 100, name="Runs"), fixed("b", 100, name="Prints")]},
            "bonus": {"weight": 15, "tests": [fixed("extra", 100, name="Extra")]},
            "penalty": {"weight": 10, "tests": [fixed("style", 100, name="Style")]}}


def floored():
    """A penalty larger than the base score: the final score is floored at 0."""
    return {"base": {"weight": 100, "tests": [fixed("a", 10, name="Runs", report="Crashed.")]},
            "penalty": {"weight": 40, "tests": [fixed("copy", 0, name="Original work", report="Copied.")]}}


CASES = {
    "rubric": (rubric, {}),
    "rubric-all": (rubric, {"preferences": {"general": {"show_passed_tests": True}}}),
    "perfect": (perfect, {}),
    "floored": (floored, {}),
}


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("case", CASES)
def test_golden_reports(case, locale):
    build, feedback = CASES[case]
    result = outcome(build(), feedback, locale)
    path = GOLDEN / f"{case}-{locale}.md"
    if os.environ.get("AUTOGRADER_RECORD_GOLDEN"):
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(result.feedback.content, encoding="utf-8")
    assert result.feedback.content == path.read_text(encoding="utf-8")
    assert render_feedback(result.tree, FeedbackPreferences.model_validate(feedback.get("preferences", {})),
                           locale) == result.feedback.content


def test_report_follows_the_authored_tree_and_explains_every_lost_point():
    content = outcome(rubric()).feedback.content
    assert headings(content) == [
        "# Evaluation Report", "## Summary",
        "## Requirements · 37.50 / 100 · −62.50 points",
        "### Program / IO · 33.33 / 100 · −50.00 points",
        "### Quality · 50.00 / 100 · −12.50 points",
        "#### Imports · 0.00 / 100 · −7.50 points",
        "#### Keywords · 100.00 / 100",
        "## Penalties · −10.00 of 20.00 points",
        "### Style · 50.00 / 100 · −10.00 points",
        "## Bonus · +5.00 of 10.00 points",
    ]
    # 75% Program / IO (2:1:0 tests); 25% Quality: 60 split equally by zero-weight subjects, 40 its own test.
    assert "**Final score: 32.50 / 100**" in content
    assert "100 − 62.50 − 10.00 + 5.00 = **32.50 / 100**" in content
    # A mixed group lists its own tests before its subjects, so they stay under its heading.
    quality = content.split("### Quality")[1]
    assert quality.index("Writes result") < quality.index("#### Imports")
    assert "- ⚠️ **Writes result** · 50.00 / 100 · −5.00 points" in content
    assert "- ❌ **Does not crash** · 0.00 / 100 · −0.00 points" in content
    assert "- ⚠️ **Bonus / large** · 50.00 / 100 · +5.00 of 10.00 points" in content


def test_headings_are_neutral_and_never_contradict_status():
    content = outcome(perfect()).feedback.content
    assert headings(content) == ["# Evaluation Report", "## Summary", "## Requirements · 100.00 / 100",
                                 "## Penalties · no penalty applied", "## Bonus · +15.00 of 15.00 points"]
    assert "100 − 0.00 − 0.00 + 15.00 = 115.00 → **100.00 / 100** (the final score is limited to 0–100)" in content
    assert content.count("✅ All tests passed") == 3 and "❌" not in content
    low = outcome(floored()).feedback.content
    assert "100 − 90.00 − 40.00 = -30.00 → **0.00 / 100**" in low


def test_no_parameter_value_appears_unless_the_evaluator_report_includes_it():
    criteria = {"base": {"weight": 100, "tests": [
        fixed("hidden", 0, secret="HIDDEN-EXPECTED-OUTPUT", report="Wrong answer."),
        fixed("shown", 0, secret="SHOWN-VALUE", report="Expected SHOWN-VALUE.")]}}
    for show_passed in (False, True):
        content = outcome(criteria, {"preferences": {"general": {"show_passed_tests": show_passed}}}).feedback.content
        assert "HIDDEN-EXPECTED-OUTPUT" not in content and "secret" not in content
        assert content.count("SHOWN-VALUE") == 1


def test_visibility_preferences():
    hidden = outcome(rubric(), {"preferences": {"general": {
        "show_score": False, "add_report_summary": False, "report_title": "Custom"},
        "default": {"category_headers": {"penalty": "Style | deductions"}}}}).feedback.content
    assert headings(hidden) == ["# Custom", "## Requirements", "### Program / IO", "### Quality", "#### Imports",
                                "#### Keywords", "## Style | deductions", "### Style", "## Bonus"]
    assert not re.search(r"\d+\.\d\d", hidden) and "points" not in hidden and "Summary" not in hidden
    assert "- ❌ **Check / output**" in hidden and "  Expected: 5" in hidden
    summary = outcome(rubric(), {"preferences": {"general": {"show_score": False},
                                                 "default": {"category_headers": {"penalty": "A | B"}}}}).feedback.content
    assert "| Category | Passed |\n| --- | --- |\n| Requirements | 2 / 6 |\n| A \\| B | 1 / 2 |\n| Bonus | 0 / 1 |" \
        in summary


def test_multiline_reports_stay_inside_their_criterion():
    content = outcome(rubric()).feedback.content
    block = content.split("- ❌ **Does not crash**")[1].split("\n### ")[0]
    assert block.splitlines()[1:] == ["", "  Your program crashed.", "", "      Traceback: ValueError"]


# --- Property: reported points reconcile with the final score ------------------------

def random_holder(rng, depth, counter):
    holder = {}
    if depth < 3 and rng.random() < 0.5:
        holder["subjects"] = [{"subject_name": f"S{next(counter)}", "weight": rng.choice([0, 0, 1, 2, 3.5]),
                               **random_holder(rng, depth + 1, counter)} for _ in range(rng.randint(1, 3))]
    if "subjects" not in holder or rng.random() < 0.4:
        holder["tests"] = [fixed(f"t{next(counter)}", rng.choice([0, 100, round(rng.uniform(0, 100), 2)]),
                                 rng.choice([0, 0, 1, 2, 5])) for _ in range(rng.randint(1, 3))]
    if "subjects" in holder and "tests" in holder:
        holder["subjects_weight"] = rng.choice([0, 25, 60, 100, round(rng.uniform(0, 100), 1)])
    return holder


def random_criteria(rng):
    counter = iter(range(10_000))
    criteria = {"base": {"weight": 100, **random_holder(rng, 1, counter)}}
    for name in ("bonus", "penalty"):
        if rng.random() < 0.6:
            criteria[name] = {"weight": rng.choice([5, 10, 30, 100]), **random_holder(rng, 1, counter)}
    return criteria


SECTION = re.compile(r"^## (Requirements|Penalties|Bonus) ·", re.M)
TEST_LINE = re.compile(r"^- (?:✅|❌|⚠️) \*\*(t\d+)\*\* · ([\d.]+) / 100(?: · ([−+])([\d.]+)(?: of [\d.]+)? points)?$",
                       re.M)
ROW = re.compile(r"^\| (Requirements|Penalties|Bonus) \| \d+ / \d+ \| ([−+])([\d.]+)(?: of [\d.]+)? points \|$", re.M)


def signed(sign, value):
    return float(value) * (-1 if sign == "−" else 1)


def test_reported_points_reconcile_with_the_final_score_for_generated_trees():
    rng = random.Random(117)
    preferences = {"preferences": {"general": {"show_passed_tests": True}}}
    for _ in range(150):
        result = outcome(random_criteria(rng), preferences)
        tree, content = result.tree, result.feedback.content
        categories = {name: signed(sign, value) for name, sign, value in ROW.findall(content)}
        # The category points are the shared values and add up to the final score.
        assert len(categories) == sum(1 for name in ("base", "bonus", "penalty") if getattr(tree, name))
        assert final_score(100 + sum(categories.values())) == pytest.approx(tree.score, abs=0.02)
        equation = next(line for line in content.splitlines() if line.startswith("100 "))
        assert f"= **{tree.score:.2f} / 100**" in equation or f"→ **{tree.score:.2f} / 100** (" in equation
        # Every test is listed once, and each category's test points add up to its points.
        sections = dict(zip(SECTION.findall(content), SECTION.split(content)[2::2]))
        listed = {}
        for name, body in sections.items():
            lines = TEST_LINE.findall(body)
            listed.update({identity: float(score) for identity, score, _, _ in lines})
            total = sum(signed(sign, value) for _, _, sign, value in lines if sign)
            assert total == pytest.approx(categories[name], abs=0.005 * (len(lines) + 1) + 0.011)
        assert listed == {test.id: test.score for _, test in iter_tests(tree)}
        # Headings carry numbers, never a status icon that could contradict them.
        assert not any(icon in heading for heading in headings(content) for icon in STATUS_ICONS)
        penalty = "## Penalties · no penalty applied" in content
        assert penalty == (tree.penalty is not None and tree.penalty.score == 100)


def test_category_points_are_the_final_score_arithmetic():
    rng = random.Random(363)
    for _ in range(500):
        base, bonus, penalty = (round(rng.uniform(0, 100), 2) for _ in range(3))
        bonus_cap, penalty_cap = rng.choice([5, 10, 40]), rng.choice([5, 20, 100])
        points = (criterion_points("base", base, 1) + criterion_points("bonus", bonus, bonus_cap / 100)
                  + criterion_points("penalty", penalty, penalty_cap / 100))
        assert max(0, min(100, 100 + points)) == pytest.approx(
            final_score(base, (bonus, bonus_cap), (penalty, penalty_cap)), abs=1e-9)


# --- Ordering, purity, links and removed paths --------------------------------------

def tree():
    """Base: two failing criteria with repeated slash labels (different impact) and a pass."""
    return ResultOutcomeTree.model_validate({
        "score": 52.5,
        "base": {"name": "base", "weight": 100, "score": 62.5, "subjects": [
            {"name": "Group / A", "weight": 75, "score": 50, "tests": [
                leaf("small", 0, "Check / same", weight=50, report="small miss", file_target=["main.py"],
                     parameters={"limit": 1}),
                leaf("passed", 100, "Passing check", weight=50, report="all good"),
            ]},
            {"name": "Group / B", "weight": 25, "score": 100, "tests": [leaf("other", 100, "Other", weight=100)]},
        ], "tests": []},
        "penalty": {"name": "penalty", "weight": 20, "score": 50, "tests": [
            leaf("style", 50, "Check / same", weight=100, report="half")]},
        "bonus": {"name": "bonus", "weight": 10, "score": 0, "tests": [leaf("extra", 0, "Extra", weight=100)]},
    })


def preferences(**general):
    return FeedbackPreferences.model_validate({"general": general})


def test_failed_criteria_are_ordered_by_impact_within_their_holder():
    value = ResultOutcomeTree.model_validate({"score": 35, "base": {"name": "base", "weight": 100, "score": 35, "tests": [
        leaf("low", 80, "Low impact", weight=25), leaf("high", 0, "High impact", weight=50),
        leaf("mid", 60, "Mid impact", weight=25)]}})
    assert [focused.test_result.id for focused in find_focus(value).base] == ["high", "mid", "low"]
    content = render_feedback(value, preferences(), "en")
    assert re.findall(r"^- \S+ \*\*(.+?)\*\*", content, re.M) == ["High impact", "Mid impact", "Low impact"]


def test_file_target_and_parameters():
    content = render_feedback(tree(), preferences(), "en")
    assert "- ❌ **Check / same** · `main.py` · 0.00 / 100 · −37.50 points\n\n  small miss" in content
    assert "limit" not in content and "Passing check" not in content


def test_learning_resources_are_keyed_by_criterion_id():
    links = [
        {"url": "https://example.com/small", "description": "Small", "linked_tests": ["small"]},
        {"url": "https://example.com/passed", "description": "Passed", "linked_tests": ["passed"]},
        {"url": "https://example.com/any", "description": "Any", "linked_tests": ["passed", "style"]},
        {"url": "https://example.com/always", "description": "Always", "linked_tests": []},
    ]
    content = render_feedback(tree(), preferences(online_content=links), "en")
    resources = content.split("## Learning Resources\n\n", 1)[1].splitlines()
    assert resources == ["- 📘 [Small](https://example.com/small)", "- 📘 [Any](https://example.com/any)",
                         "- 📘 [Always](https://example.com/always)"]
    only_passing = render_feedback(tree(), preferences(online_content=links[1:2]), "en")
    assert "Learning Resources" not in only_passing


def test_rendering_twice_mutates_neither_preferences_nor_results():
    value, prefs = tree(), FeedbackPreferences.model_validate({
        "general": {"online_content": [{"url": "https://example.com", "description": "Docs", "linked_tests": ["small"]}]},
        "default": {"category_headers": {"base": "Base"}}})
    before_prefs, before_tree = deepcopy(prefs.model_dump()), value.model_dump()
    first = render_feedback(value, prefs, "en")
    second = render_feedback(value, prefs, "pt_br")
    third = render_feedback(value, prefs, "en")
    assert first == third and first != second
    assert prefs.model_dump() == before_prefs and value.model_dump() == before_tree
    assert prefs.general.report_title is None and prefs.default.category_headers == {"base": "Base"}
    assert all(type(resource).__name__ == "LearningResource" for resource in prefs.general.online_content)


@pytest.mark.parametrize("module", ["autograder.services.report.ai_reporter", "autograder.services.report.reporter_service",
                                    "autograder.models.dataclass.feedback_preferences",
                                    "autograder.models.dataclass.preflight_error",
                                    "autograder.utils.feedback_generator",
                                    "autograder.utils.formatters.result_tree",
                                    "autograder.serializers.pipeline_execution_serializer"])
def test_obsolete_reporting_paths_are_removed(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


def test_shipped_requested_feedback_example():
    from examples.contracts.requested_feedback import grade  # pylint: disable=import-outside-toplevel
    disabled, enabled, localized = grade(False), grade(True), grade(True, "pt_br")
    assert (disabled.status, disabled.score, disabled.feedback.status) == ("completed", 25, "disabled")
    assert disabled.feedback.content is None
    assert (enabled.status, enabled.score, enabled.feedback.status) == ("completed", 25, "completed")
    assert enabled.tree == disabled.tree
    assert enabled.feedback.content.startswith("# Import review") and "The os module" in enabled.feedback.content
    assert "**Nota final: 25.00 / 100**" in localized.feedback.content
