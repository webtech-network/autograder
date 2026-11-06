"""The ``default`` feedback mode: a Markdown report of a completed grade.

The report follows the authored tree (category, nested subjects, tests) under
the authored names and explains the score with the shared scoring values: each
test's signed ``points`` from focus, each category's ``criterion_points`` and
the final score from the tree; nothing is recomputed. Parameters are never
rendered: a test shows its status, file target, score, points and the
evaluator's own report.
"""
from autograder.models.contracts.definition import FeedbackPreferences
from autograder.models.contracts.outcome import ResultOutcomeTree
from autograder.models.contracts.scoring import criterion_points, iter_holder_tests, iter_tests
from autograder.models.dataclass.focus import Focus
from autograder.translations import t

#: Category order of the report: what cost points first, then what earned them.
_ORDER = ("base", "penalty", "bonus")


def render_default_report(focus: Focus, tree: ResultOutcomeTree, preferences: FeedbackPreferences,
                          locale: str) -> str:
    """Render the report from canonical preferences without modifying them.

    A pure function of the tree, the preferences and the locale: localized
    defaults are resolved at render time and the inputs are only read.
    """
    return "\n".join(_Report(focus, preferences, locale).render(tree)) + "\n"


class _Report:
    """One rendering: the inputs it reads and the Markdown fragments it builds."""

    def __init__(self, focus: Focus, preferences: FeedbackPreferences, locale: str):
        self.focused = {item.test_result.id: item for name in _ORDER for item in (getattr(focus, name) or ())}
        self.general = preferences.general
        self.headers = preferences.default.category_headers
        self.locale = locale

    def render(self, tree):
        """Title, final score, summary, one section per category and learning resources."""
        locale = self.locale
        lines = [f"# {self.general.report_title or t('feedback.report_title', locale=locale)}"]
        if self.general.show_score:
            lines += ["", f"**{t('feedback.report.final_score', locale=locale)}: {tree.score:.2f} / 100**"]
        holders = [(name, getattr(tree, name)) for name in _ORDER if getattr(tree, name) is not None]
        if self.general.add_report_summary:
            lines += self.summary(tree, holders)
        for name, holder in holders:
            heading = self.category_name(name)
            if self.general.show_score:
                heading += f" · {self.category_status(name, holder)}"
            lines += ["", "---", "", f"## {heading}", *self.holder_body(name, holder, 3)]
        if self.general.online_content:
            lines += self.online_resources(tree)
        return lines

    # -- summary -------------------------------------------------------------

    def summary(self, tree, holders):
        """Per category: tests passed and, with scores shown, its points and the equation."""
        locale = self.locale
        columns = [t("feedback.report.category_column", locale=locale), t("feedback.report.passed_column", locale=locale)]
        if self.general.show_score:
            columns.append(t("feedback.report.points_column", locale=locale))
        rows = []
        for name, holder in holders:
            tests = list(iter_holder_tests(holder))
            row = [self.category_name(name).replace("|", "\\|"),
                   f"{sum(1 for test in tests if test.score >= 100)} / {len(tests)}"]
            if self.general.show_score:
                row.append(self.category_points(name, holder))
            rows.append(row)
        lines = ["", "---", "", f"## {t('feedback.report.summary_header', locale=locale)}", "",
                 _row(columns), _row(["---"] * len(columns)), *(_row(row) for row in rows)]
        if self.general.show_score:
            lines += ["", self.equation(tree, holders)]
        return lines

    def equation(self, tree, holders):
        """``100 − base − penalty + bonus = final``, stating the 0-100 limit when it applied."""
        points = [criterion_points(name, holder.score, holder.weight / 100) for name, holder in holders]
        terms = " ".join(f"{_sign(name)} {abs(value):.2f}" for (name, _), value in zip(holders, points))
        unclamped = 100 + sum(points)
        final = f"**{tree.score:.2f} / 100**"
        if abs(unclamped - tree.score) > 0.02:
            return f"100 {terms} = {unclamped:.2f} → {final} ({t('feedback.report.clamped', locale=self.locale)})"
        return f"100 {terms} = {final}"

    # -- categories, subjects and tests --------------------------------------

    def category_name(self, name):
        """The authored ``category_headers`` entry, else the localized neutral name."""
        return self.headers.get(name) or t(f"feedback.category.{name}", locale=self.locale)

    def category_points(self, name, holder):
        """Points a category moved the final score; bonus and penalty state their cap."""
        points = f"{_sign(name)}{abs(criterion_points(name, holder.score, holder.weight / 100)):.2f}"
        if name == "base":
            return t("feedback.report.points", locale=self.locale, points=points)
        return t("feedback.report.points_of", locale=self.locale, points=points, cap=f"{holder.weight:.2f}")

    def category_status(self, name, holder):
        """Heading numbers: base score and points lost, penalty deducted, bonus earned."""
        if name == "base":
            status = f"{holder.score:.2f} / 100"
            return status if holder.score >= 100 else f"{status} · {self.category_points(name, holder)}"
        if name == "penalty" and holder.score >= 100:
            return t("feedback.report.no_penalty", locale=self.locale)
        return self.category_points(name, holder)

    def holder_body(self, category, holder, level):
        """Direct tests first (they belong to the current heading), then one section per subject.

        Siblings are ordered by points missed; ties keep the authored order.
        """
        tests = list(iter_holder_tests(holder))
        if not self.general.show_passed_tests and all(test.score >= 100 for test in tests):
            return ["", t("feedback.report.all_passed", locale=self.locale, count=len(tests))]
        lines = []
        for test in sorted(holder.tests, key=lambda test: -self.focused[test.id].diff_score):
            if self.general.show_passed_tests or test.score < 100:
                lines += ["", *self.test(category, test)]
        for subject in sorted(holder.subjects, key=lambda subject: -self.missed(subject)):
            heading = subject.name
            if self.general.show_score:
                heading += f" · {self.subject_status(category, subject)}"
            lines += ["", f"{'#' * min(level, 6)} {heading}", *self.holder_body(category, subject, level + 1)]
        return lines

    def missed(self, holder):
        """Points the holder's tests missed: the sibling order."""
        return sum(self.focused[test.id].diff_score for test in iter_holder_tests(holder))

    def subject_status(self, category, subject):
        """Subject score plus the points its tests lost (or, for bonus, earned)."""
        status = f"{subject.score:.2f} / 100"
        if category == "bonus" or subject.score < 100:
            points = sum(self.focused[test.id].points for test in iter_holder_tests(subject))
            status += f" · {self.points(category, points)}"
        return status

    def points(self, category, value):
        """``−x points`` for base and penalty, ``+x points`` for bonus."""
        return t("feedback.report.points", locale=self.locale, points=f"{_sign(category)}{abs(value):.2f}")

    def test(self, category, test):
        """One list item: status, label, file target, score, points; the report indented below."""
        icon = "✅" if test.score >= 100 else "❌" if test.score <= 0 else "⚠️"
        parts = [f"{icon} **{test.name}**"]
        if test.file_target:
            parts.append(", ".join(f"`{target}`" for target in test.file_target))
        if self.general.show_score:
            parts.append(f"{test.score:.2f} / 100")
            focused = self.focused[test.id]
            if category == "bonus":
                # Earned plus missed is the most this bonus criterion can add.
                parts.append(t("feedback.report.points_of", locale=self.locale, points=f"+{focused.points:.2f}",
                               cap=f"{focused.points + focused.diff_score:.2f}"))
            elif test.score < 100:
                parts.append(self.points(category, focused.points))
        lines = [f"- {' · '.join(parts)}"]
        if test.report:
            lines += ["", *(f"  {line}" if line.strip() else "" for line in test.report.splitlines())]
        return lines

    # -- resources -----------------------------------------------------------

    def online_resources(self, tree):
        """Resources without linked criteria always show; linked ones show when one failed."""
        failed = {test.id for _, test in iter_tests(tree) if test.score < 100}
        visible = [resource for resource in self.general.online_content
                   if not resource.linked_tests or set(resource.linked_tests) & failed]
        if not visible:
            return []
        return ["", "---", "", f"## {t('feedback.report.learning_resources_label', locale=self.locale)}", "",
                *(f"- 📘 [{resource.description}]({resource.url})" for resource in visible)]


def _sign(category):
    return "+" if category == "bonus" else "−"


def _row(cells):
    return f"| {' | '.join(cells)} |"
