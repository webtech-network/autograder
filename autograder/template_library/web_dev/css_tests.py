import re
from typing import Optional, List
from bs4 import BeautifulSoup

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer


class CountUnusedCssClasses(TestFunction):
    """Analyzes unused CSS classes in the HTML."""
    @property
    def name(self):
        return "count_unused_css_classes"
    @property
    def description(self):
        return t("web_dev.css.count_unused_css_classes.description")
    @property
    def required_file(self):
        return None
    @property
    def parameter_description(self):
        return [
            ParamDescription("submission_files", t("web_dev.css.count_unused_css_classes.param.submission_files"), "dictionary"),
            ParamDescription("html_file", t("web_dev.css.count_unused_css_classes.param.html_file"), "string"),
            ParamDescription("css_file", t("web_dev.css.count_unused_css_classes.param.css_file"), "string")
        ]

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

    def _extract_html_classes(self, html_content: str) -> set:
        """Extracts class names from the HTML content."""
        used_classes = set()
        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            for el in soup.find_all(class_=True):
                for cls in el.get("class", []):
                    used_classes.add(cls)
        return used_classes

    def execute(self, files, sandbox, *args, submission_files=None, html_file: str = "", css_file: str = "", **kwargs) -> TestResult:
        """Executes the unused CSS class verification."""
        submission_files = submission_files or {}
        html_content = submission_files.get(html_file, "")
        css_content = submission_files.get(css_file, "")
        
        if not html_content and not css_content:
            return TestResult(
                self.name, 
                0, 
                t("web_dev.css.count_unused_css_classes.report.no_files", locale=kwargs.get("locale")), 
                {
                    "html_file": html_file, 
                    "css_file": css_file, 
                    "unused_count": 0,
                    "category": "none"
                }
            )

        css_classes = self._extract_css_classes(css_content)
        used_classes = self._extract_html_classes(html_content)
        
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
        
        locale = kwargs.get("locale")
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
        
        return TestResult(self.name, score, report, {
            "html_file": html_file, 
            "css_file": css_file, 
            "unused_count": unused_count, 
            "category": category,
            "unused_classes_sample": unused_classes[:20]
        })

class CheckFlexboxUsage(TestFunction):
    """Checks for Flexbox usage in CSS."""
    @property
    def name(self):
        return "check_flexbox_usage"
    @property
    def description(self):
        return t("web_dev.css.check_flexbox_usage.description")
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, **kwargs) -> TestResult:
        """Executes the search for Flexbox properties."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"\b(display\s*:\s*flex|flex-)", css_content) is not None
        score = 100 if found else 0
        locale = kwargs.get("locale")
        report = t("web_dev.css.check_flexbox_usage.report.found", locale=locale) if found else t("web_dev.css.check_flexbox_usage.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CountOverUsage(TestFunction):
    """Penalizes over usage of a specific text."""
    @property
    def name(self):
        return "count_over_usage"
    @property
    def description(self):
        return t("web_dev.css.count_over_usage.description")
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return [
            ParamDescription("text", t("web_dev.css.count_over_usage.param.text"), "string"),
            ParamDescription("max_allowed", t("web_dev.css.count_over_usage.param.max_allowed"), "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, text: str = "", max_allowed: int = 0, **kwargs) -> TestResult:
        """Executes the excess count verification."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found_count = css_content.count(text)
        score = 100 if found_count <= max_allowed else 0
        locale = kwargs.get("locale")
        report = t("web_dev.css.count_over_usage.report.over", locale=locale, text=text, found_count=found_count, max_allowed=max_allowed) if score == 0 else t("web_dev.css.count_over_usage.report.ok", locale=locale, text=text)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"text": text, "max_allowed": max_allowed}
        )

class UsesRelativeUnits(TestFunction):
    """Checks for the use of relative units (em, rem, etc.)."""
    @property
    def name(self):
        return "uses_relative_units"
    @property
    def description(self):
        return t("web_dev.css.uses_relative_units.description")
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, **kwargs) -> TestResult:
        """Executes the search for relative units."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"\b(em|rem|%|vh|vw)\b", css_content) is not None
        score = 100 if found else 0
        locale = kwargs.get("locale")
        report = t("web_dev.css.uses_relative_units.report.found", locale=locale) if found else t("web_dev.css.uses_relative_units.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckIdSelectorOverUsage(TestFunction):
    """Counts ID selectors in the CSS to avoid over usage."""
    @property
    def name(self):
        return "Check ID Selector Over Usage"
    @property
    def description(self):
        return t("web_dev.css.check_id_selector_over_usage.description")
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return [
            ParamDescription("max_allowed", t("web_dev.css.check_id_selector_over_usage.param.max_allowed"), "integer")
        ]

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

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, max_allowed: int = 0, **kwargs) -> TestResult:
        """Executes the ID selector verification."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")
        selectors = self._get_id_selectors(files[0].content)
        found_count = len(selectors)
        score = 100 if found_count <= max_allowed else 0
        locale = kwargs.get("locale")
        report = t("web_dev.css.check_id_selector_over_usage.report.over", locale=locale, found_count=found_count, max_allowed=max_allowed) if score == 0 else t("web_dev.css.check_id_selector_over_usage.report.ok", locale=locale)
        return TestResult(self.name, score, report, {"max_allowed": max_allowed})

class HasStyle(TestFunction):
    """Checks if a specific CSS style rule appears."""
    @property
    def name(self):
        return "has_style"
    @property
    def description(self):
        return t("web_dev.css.has_style.description")
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return [
            ParamDescription("style", t("web_dev.css.has_style.param.style"), "string"),
            ParamDescription("count", t("web_dev.css.has_style.param.count"), "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, style: str = "", count: int = 0, **kwargs) -> TestResult:
        """Executes the search for style rules."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found_count = len(re.findall(rf"{re.escape(style)}\s*:\s*[^;]+;", css_content, re.IGNORECASE))
        score = min(100, int((found_count / count) * 100)) if count > 0 else 100
        report = t("web_dev.css.has_style.report", locale=kwargs.get("locale"), found_count=found_count, count=count, style=style)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"style": style, "required_count": count}
        )

class CheckMediaQueries(TestFunction):
    """Checks if media queries exist in the CSS."""
    @property
    def name(self):
        return "check_media_queries"
    @property
    def description(self):
        return t("web_dev.css.check_media_queries.description")
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return []
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, **kwargs) -> TestResult:
        """Executes the search for media queries."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        found = re.search(r"@media\s+[^{]+\{", css_content) is not None
        score = 100 if found else 0
        locale = kwargs.get("locale")
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
    @property
    def required_file(self):
        return "CSS"
    @property
    def parameter_description(self):
        return [
            ParamDescription("prop", t("web_dev.css.css_uses_property.param.prop"), "string"),
            ParamDescription("value", t("web_dev.css.css_uses_property.param.value"), "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, prop: str = "", value: str = "", **kwargs) -> TestResult:
        """Executes the search for a CSS property/value pair."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, "No CSS file provided.")

        css_content = files[0].content
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}", re.IGNORECASE)
        found = pattern.search(css_content) is not None
        score = 100 if found else 0
        locale = kwargs.get("locale")
        report = t("web_dev.css.css_uses_property.report.found", locale=locale, prop=prop, value=value) if found else t("web_dev.css.css_uses_property.report.not_found", locale=locale, prop=prop, value=value)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"prop": prop, "value": value}
        )
