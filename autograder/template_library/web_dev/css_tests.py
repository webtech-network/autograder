import re
from typing import Annotated, List, Optional

from pydantic import Field

from autograder.models.abstract.test_function import EvaluationInput, TestFunction
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.template_library.web_dev.documents import parsed_html
from autograder.translations import t


class CountUnusedCssClasses(TestFunction):
    """Analyzes unused CSS classes in the HTML."""
    absence_check = "Limit: passes while no CSS class is left unused."
    # Classes are defined and used across the whole project, whatever the scope.
    file_extensions = (".html", ".htm", ".css")
    uses_context_files = True
    @property
    def name(self):
        return "count_unused_css_classes"
    @property
    def description(self):
        return t("web_dev.css.count_unused_css_classes.description")
    def _extract_css_classes(self, css_content: str) -> set:
        """Extracts class names from the CSS content."""
        if not css_content:
            return set()
        css_classes = set()
        token_pattern = re.compile(
            r'(/\*.*?\*/)|'           # Comentaries (ignoring)
            r'(".*?")|'               # Double String (ignoring)
            r"('.*?')|"               # Simple String (ignoring)
            r'(\{)|'                  # Open brace
            r'(\})|'                  # Close brace
            r'(\.[a-zA-Z_-][\w-]*)',  # CSS class selector
            re.DOTALL
        )
        depth = 0
        for match in token_pattern.finditer(css_content):
            groups = match.groups()
            if groups[0] or groups[1] or groups[2]: # comment or strings
                continue
            if groups[3]: # {
                depth += 1
            elif groups[4]: # }
                depth = max(0, depth - 1)
            elif groups[5] and depth == 0: # .class
                css_classes.add(groups[5][1:])
        return css_classes

    def _extract_html_classes(self, html: Optional[SubmissionFile]) -> set:
        """Extracts class names from the HTML file."""
        used_classes = set()
        if html is not None and html.content:
            soup = parsed_html(html)
            for el in soup.find_all(class_=True):
                for cls in el.get("class", []):
                    used_classes.add(cls)
        return used_classes

    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Compares the classes the CSS files define with those the HTML files use."""
        pages = [file for file in evaluation.files if not file.filename.lower().endswith(".css")]
        css_content = "\n".join(file.content for file in evaluation.files if file.filename.lower().endswith(".css"))
        html_content = "".join(page.content for page in pages)

        if not html_content and not css_content:
            return TestResult(
                self.name, 
                0, 
                t("web_dev.css.count_unused_css_classes.report.no_files", locale=evaluation.locale)
            )

        css_classes = self._extract_css_classes(css_content)
        used_classes = set().union(*(self._extract_html_classes(page) for page in pages))
        
        html_found, css_found = bool(html_content), bool(css_content)
        if html_found and css_found:
            unused_classes = sorted(css_classes - used_classes)
            category = "css_only_unused"
        elif css_found:
            unused_classes = sorted(css_classes)
            category = "css_only_unused"
        elif html_found:
            unused_classes = sorted(used_classes - css_classes)
            category = "html_classes_without_css"
        else:
            unused_classes, category = [], "none"

        unused_count = len(unused_classes)
        score = 100 if unused_count == 0 else 0
        
        locale = evaluation.locale
        if category == "html_classes_without_css":
            report = (
                t("web_dev.css.count_unused_css_classes.report.html_no_css.none", locale=locale)
                if unused_count == 0
                else t("web_dev.css.count_unused_css_classes.report.html_no_css.unused", locale=locale, unused_count=unused_count, unused_classes=unused_classes)
            )
        else:
            report = (
                t("web_dev.css.count_unused_css_classes.report.css_unused.none", locale=locale)
                if unused_count == 0
                else t("web_dev.css.count_unused_css_classes.report.css_unused.unused", locale=locale, unused_count=unused_count, unused_classes=unused_classes)
            )
        
        return TestResult(self.name, score, report)

class CheckFlexboxUsage(TestFunction):
    """Checks for Flexbox usage in CSS."""
    @property
    def name(self):
        return "check_flexbox_usage"
    @property
    def description(self):
        return t("web_dev.css.check_flexbox_usage.description")
    file_extensions = (".css",)
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the search for Flexbox properties."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"\b(display\s*:\s*flex|flex-)", css_content) is not None
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.css.check_flexbox_usage.report.found", locale=locale) if found else t("web_dev.css.check_flexbox_usage.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CountOverUsage(TestFunction):
    """Penalizes over usage of a specific text."""
    absence_check = "Limit: passes while the text appears at most max_allowed times."
    @property
    def name(self):
        return "count_over_usage"
    @property
    def description(self):
        return t("web_dev.css.count_over_usage.description")
    file_extensions = (".css",)
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                text: Annotated[str, Field(min_length=1, description=t("web_dev.css.count_over_usage.param.text"))],
                max_allowed: Annotated[int, Field(ge=0, description=t("web_dev.css.count_over_usage.param.max_allowed"))] = 0,
                ) -> TestResult:
        """Executes the excess count verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found_count = css_content.count(text)
        score = 100 if found_count <= max_allowed else 0
        locale = evaluation.locale
        report = t("web_dev.css.count_over_usage.report.over", locale=locale, text=text, found_count=found_count, max_allowed=max_allowed) if score == 0 else t("web_dev.css.count_over_usage.report.ok", locale=locale, text=text)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class UsesRelativeUnits(TestFunction):
    """Checks for the use of relative units (em, rem, etc.)."""
    @property
    def name(self):
        return "uses_relative_units"
    @property
    def description(self):
        return t("web_dev.css.uses_relative_units.description")
    file_extensions = (".css",)
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the search for relative units."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"\b(em|rem|%|vh|vw)\b", css_content) is not None
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.css.uses_relative_units.report.found", locale=locale) if found else t("web_dev.css.uses_relative_units.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckIdSelectorOverUsage(TestFunction):
    """Counts ID selectors in the CSS to avoid over usage."""
    absence_check = "Limit: passes while ID selectors appear at most max_allowed times."
    @property
    def name(self):
        return "check_id_selector_over_usage"
    @property
    def description(self):
        return t("web_dev.css.check_id_selector_over_usage.description")
    file_extensions = (".css",)
    minimum_files = 1
    maximum_files = 1
    def _get_id_selectors(self, css_content: str) -> List[str]:
        """Helper to extract ID selectors from CSS."""
        token_pattern = re.compile(
            r'(/\*.*?\*/)|'          # Comentaries
            r'("[^"]*")|'            # Strings
            r"('[^']*')|"            # Strings
            r'(@media\b)|'           # @media block
            r'(\{)|'                 # Open brace
            r'(\})|'                 # Close brace
            r'(#[a-zA-Z_][\w-]*)',   # ID Selector
            re.DOTALL | re.IGNORECASE
        )
        selectors, context_stack, next_block = [], [True], False
        for match in token_pattern.finditer(css_content):
            groups = match.groups()
            if any(groups[0:3]): continue # comments/strings
            if groups[3]: # @media
                next_block = True
            elif groups[4]: # {
                context_stack.append(bool(next_block))
                next_block = False
            elif groups[5]: # {
                if len(context_stack) > 1: context_stack.pop()
            elif groups[6] and context_stack[-1]: # #id in selector area
                selectors.append(groups[6])
        return selectors

    def execute(self, evaluation: EvaluationInput, *,
                max_allowed: Annotated[int, Field(ge=0, description=t("web_dev.css.check_id_selector_over_usage.param.max_allowed"))] = 0,
                ) -> TestResult:
        """Executes the ID selector verification."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")
        selectors = self._get_id_selectors(files[0].content)
        found_count = len(selectors)
        score = 100 if found_count <= max_allowed else 0
        locale = evaluation.locale
        report = t("web_dev.css.check_id_selector_over_usage.report.over", locale=locale, found_count=found_count, max_allowed=max_allowed) if score == 0 else t("web_dev.css.check_id_selector_over_usage.report.ok", locale=locale)
        return TestResult(self.name, score, report)

class HasStyle(TestFunction):
    """Checks if a specific CSS style rule appears."""
    @property
    def name(self):
        return "has_style"
    @property
    def description(self):
        return t("web_dev.css.has_style.description")
    file_extensions = (".css",)
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                style: Annotated[str, Field(min_length=1, description=t("web_dev.css.has_style.param.style"))],
                required_count: Annotated[int, Field(ge=1, description=t("web_dev.css.has_style.param.required_count"))] = 1,
                ) -> TestResult:
        """Executes the search for style rules."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found_count = len(re.findall(rf"{re.escape(style)}\s*:\s*[^;]+;", css_content, re.IGNORECASE))
        score = min(100, int((found_count / required_count) * 100))
        report = t("web_dev.css.has_style.report", locale=evaluation.locale, found_count=found_count,
                   required_count=required_count, style=style)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckMediaQueries(TestFunction):
    """Checks if media queries exist in the CSS."""
    @property
    def name(self):
        return "check_media_queries"
    @property
    def description(self):
        return t("web_dev.css.check_media_queries.description")
    file_extensions = (".css",)
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the search for media queries."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"@media\s+[^{]+\{", css_content) is not None
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.css.check_media_queries.report.found", locale=locale) if found else t("web_dev.css.check_media_queries.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CssUsesProperty(TestFunction):
    """Checks if a CSS property-value pair exists."""
    @property
    def name(self):
        return "css_uses_property"
    @property
    def description(self):
        return t("web_dev.css.css_uses_property.description")
    file_extensions = (".css",)
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                prop: Annotated[str, Field(min_length=1, description=t("web_dev.css.css_uses_property.param.prop"))],
                value: Annotated[str, Field(min_length=1, description=t("web_dev.css.css_uses_property.param.value"))],
                ) -> TestResult:
        """Executes the search for a CSS property/value pair."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}", re.IGNORECASE)
        found = pattern.search(css_content) is not None
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.css.css_uses_property.report.found", locale=locale, prop=prop, value=value) if found else t("web_dev.css.css_uses_property.report.not_found", locale=locale, prop=prop, value=value)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )
