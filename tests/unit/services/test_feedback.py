"""Requested feedback renders a completed tree with canonical preferences (ARC-12)."""
import importlib
from copy import deepcopy

import pytest

from autograder.models.contracts.definition import FeedbackPreferences
from autograder.models.contracts.outcome import ResultOutcomeTree
from autograder.services.feedback import render_feedback
from autograder.services.focus_service import find_focus
from tests.grading import leaf


def tree():
    """Base: two failing criteria with repeated slash labels (different impact) and a pass.

    Penalty and bonus categories each hold one criterion.
    """
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


def headings(content):
    return [line for line in content.splitlines() if line.startswith("#")]


def test_default_report_layout_order_and_visibility():
    content = render_feedback(tree(), preferences(), "en")
    assert headings(content) == [
        "# Evaluation Report", "## GRADING SUMMARY",
        "## ✅ Essential Requirements", "### 🧪 Check / same ❌",
        "## ❌ Points to Improve", "### 🧪 Check / same ❌",
        "## ⭐ Extra Points", "### 🧪 Extra ❌",
        "## Final Score",
    ]
    assert "- 📊 **Tests:** 5 total  \n  - ✅ 2 passed  \n  - ❌ 3 failed" in content
    assert "- 📁 **File:** `main.py`" in content and "- ⚙️ **Parameters:** `limit=1`" in content
    assert "- 💬 **Error:** small miss" in content
    assert content.endswith("> **52.50 / 100**")
    assert "Passing check" not in content and "Learning Resources" not in content


def test_failed_criteria_are_ordered_by_impact():
    value = ResultOutcomeTree.model_validate({"score": 35, "base": {"name": "base", "weight": 100, "score": 35, "tests": [
        leaf("low", 80, "Low impact", weight=25), leaf("high", 0, "High impact", weight=50),
        leaf("mid", 60, "Mid impact", weight=25)]}})
    assert [focused.test_result.id for focused in find_focus(value).base] == ["high", "mid", "low"]
    content = render_feedback(value, preferences(), "en")
    assert [line for line in headings(content) if line.startswith("### ")] == [
        "### 🧪 High impact ❌", "### 🧪 Mid impact ❌", "### 🧪 Low impact ❌"]


def test_visibility_preferences():
    content = render_feedback(tree(), preferences(show_passed_tests=True, show_score=False, add_report_summary=False,
                                                  report_title="Custom"), "en")
    assert headings(content)[:4] == ["# Custom", "## ✅ Essential Requirements", "### 🧪 Check / same ❌",
                                     "### 🧪 Passing check ✅"]
    assert "- 💬 **Feedback:** all good" in content
    assert "Final Score" not in content and "SUMMARY" not in content and "52.50" not in content


def test_localization_and_category_headings():
    custom = FeedbackPreferences.model_validate({"default": {"category_headers": {"penalty": "Penalidades"}}})
    content = render_feedback(tree(), custom, "pt_br")
    assert headings(content) == [
        "# Relatório de Avaliação", "## RESUMO DA AVALIAÇÃO",
        "## ✅ Requisitos Essenciais", "### 🧪 Check / same ❌",
        "## Penalidades", "### 🧪 Check / same ❌",
        "## ⭐ Pontos Extras", "### 🧪 Extra ❌",
        "## Nota Final",
    ]
    assert "- 🔴 **Nota:** 0.0/100" in content and "- 💬 **Erro:** small miss" in content


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
    assert "## Nota Final" in localized.feedback.content
