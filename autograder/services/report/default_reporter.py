"""The ``default`` feedback mode: a Markdown report of a completed grade."""
from autograder.models.contracts.definition import FeedbackPreferences
from autograder.models.contracts.outcome import ResultOutcomeTree
from autograder.models.contracts.scoring import iter_tests
from autograder.models.dataclass.focus import Focus
from autograder.translations import t
from autograder.utils.formatters.result_tree import ResultTreeFormatter

_FORMATTER = ResultTreeFormatter()
_CATEGORY_FALLBACKS = {"base": "✅ Essential Requirements", "penalty": "❌ Points to Improve",
                       "bonus": "⭐ Extra Points"}


def render_default_report(focus: Focus, tree: ResultOutcomeTree, preferences: FeedbackPreferences,
                          locale: str) -> str:
    """Render the report from canonical preferences without modifying them.

    Defaults (title, category headers) are resolved for ``locale`` at render
    time; the preferences and the tree are only read.
    """
    general = preferences.general
    lines = [f"# {general.report_title or t('feedback.report_title', locale=locale) or 'Evaluation Report'}", ""]
    if general.add_report_summary:
        lines.extend(_summary(tree, locale))
    lines.extend(_categorized_results(focus, preferences, locale))
    if general.show_score:
        lines.extend(_final_score(tree.score, locale))
    if general.online_content:
        failed = {test.id for _, test in iter_tests(tree) if test.score < 100}
        lines.extend(_online_resources(general.online_content, failed, locale))
    return "\n".join(lines)


def _summary(tree, locale):
    header = t("feedback.report.summary_header", locale=locale) or "📊 SUMMARY"
    return [_FORMATTER.main_divisor(), f"## {header}", _FORMATTER.resume(tree, locale=locale)]


def _categorized_results(focus, preferences, locale):
    lines = []
    show_passed = preferences.general.show_passed_tests
    headers = preferences.default.category_headers
    for name in ("base", "penalty", "bonus"):
        tests = getattr(focus, name)
        if not tests:
            continue
        visible = [focused.test_result for focused in tests if show_passed or focused.test_result.score < 100]
        if not visible:
            continue
        header = headers.get(name) or t(f"feedback.category.{name}", locale=locale) or _CATEGORY_FALLBACKS[name]
        lines.extend(["", _FORMATTER.main_divisor(), f"## {header}"])
        for test in visible:
            lines.extend(["", _FORMATTER.format_test(test), *_FORMATTER.format_test_details(test, locale=locale)])
    return lines


def _final_score(score, locale):
    label = t("feedback.report.final_score_label", locale=locale) or "🏆 Final Score"
    return ["", _FORMATTER.main_divisor(), f"## {label}", "", _FORMATTER.final_score(score)]


def _online_resources(resources, failed_ids, locale):
    """Resources without linked criteria always show; linked ones show when one failed."""
    visible = [resource for resource in resources
               if not resource.linked_tests or set(resource.linked_tests) & failed_ids]
    if not visible:
        return []
    label = t("feedback.report.learning_resources_label", locale=locale) or "📚 Learning Resources"
    return ["", _FORMATTER.main_divisor(), f"## {label}", "",
            *(f"- 📘 [{resource.description}]({resource.url})" for resource in visible)]
