import re
from typing import Optional, List

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer


class CountGlobalVars(TestFunction):
    """Counts variables in the global scope of JS."""
    @property
    def name(self):
        return "count_global_vars"
    @property
    def description(self):
        return t("web_dev.js.count_global_vars.description")
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("max_allowed", t("web_dev.js.count_global_vars.param.max_allowed"), "integer")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, max_allowed: int = 0, **kwargs) -> TestResult:
        """Executes the global variable count."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=kwargs.get("locale")))

        js_content = files[0].content
        found_count = len(re.findall(r"^\s*(var|let|const)\s+", js_content, re.MULTILINE))
        score = 100 if found_count <= max_allowed else 0
        locale = kwargs.get("locale")
        report = t("web_dev.js.count_global_vars.report.over", locale=locale, found_count=found_count, max_allowed=max_allowed) if score == 0 else t("web_dev.js.count_global_vars.report.ok", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"max_allowed": max_allowed}
        )

class HasNoJsFramework(TestFunction):
    """Checks if forbidden JS frameworks are present."""
    @property
    def name(self):
        return "has_no_js_framework"
    @property
    def description(self):
        return t("web_dev.js.has_no_js_framework.description")
    @property
    def required_file(self):
        return None
    @property
    def parameter_description(self):
        return [
            ParamDescription("submission_files", t("web_dev.js.has_no_js_framework.param.submission_files"), "dictionary"),
            ParamDescription("html_file", t("web_dev.js.has_no_js_framework.param.html_file"), "string"),
            ParamDescription("js_file", t("web_dev.js.has_no_js_framework.param.js_file"), "string")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, html_file: str = "", js_file: str = "", **kwargs) -> TestResult:
        """Executes the framework verification."""
        if not files:
            return TestResult(self.name, 0, t("web_dev.error.no_files", locale=kwargs.get("locale")))

        # Build a dictionary of files
        submission_files = {f.filename: f.content for f in files}

        # Combine content for a single search
        html_content = submission_files.get(html_file, "")
        js_content = submission_files.get(js_file, "")
        combined_content = html_content + js_content
        forbidden_patterns = [
            "react.js", "react.dom", "ReactDOM.render",  # React
            "vue.js", "new Vue",  # Vue
            "angular.js", "@angular/core",  # Angular
        ]
        found = any(pattern in combined_content for pattern in forbidden_patterns)
        score = 0 if found else 100  # Penalty test: score is 0 if found
        locale = kwargs.get("locale")
        report = t("web_dev.js.has_no_js_framework.report.found", locale=locale) if found else t("web_dev.js.has_no_js_framework.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class JsUsesQueryStringParsing(TestFunction):
    """Checks for query string reading in JS."""
    @property
    def name(self):
        return "js_uses_query_string_parsing"
    @property
    def description(self):
        return t("web_dev.js.js_uses_query_string_parsing.description")
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return []

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, **kwargs) -> TestResult:
        """Executes the query string pattern search."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=kwargs.get("locale")))

        js_content = files[0].content
        # Regex to find 'URLSearchParams' or 'window.location.search'
        pattern = re.compile(r"URLSearchParams|window\.location\.search")
        found = pattern.search(js_content) is not None
        score = 100 if found else 0
        locale = kwargs.get("locale")
        report = t("web_dev.js.js_uses_query_string_parsing.report.found", locale=locale) if found else t("web_dev.js.js_uses_query_string_parsing.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class UsesForbiddenMethod(TestFunction):
    """Checks and penalizes the use of forbidden methods."""
    @property
    def name(self):
        return "uses_forbidden_method"
    @property
    def description(self):
        return t("web_dev.js.uses_forbidden_method.description")
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("method", t("web_dev.js.uses_forbidden_method.param.method"), "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, method: str = "", **kwargs) -> TestResult:
        """Executes the search for forbidden methods."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=kwargs.get("locale")))

        js_content = files[0].content
        found = method in js_content
        score = 0 if found else 100
        locale = kwargs.get("locale")
        report = t("web_dev.js.uses_forbidden_method.report.found", locale=locale, method=method) if found else t("web_dev.js.uses_forbidden_method.report.not_found", locale=locale, method=method)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"method": method}
        )

class JsUsesFeature(TestFunction):
    """Checks if a specific JS feature is present."""
    @property
    def name(self): return "js_uses_feature"
    @property
    def description(self): return t("web_dev.js.js_uses_feature.description")
    @property
    def required_file(self): return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("feature", t("web_dev.js.js_uses_feature.param.feature"), "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, feature: str = "", **kwargs) -> TestResult:
        """Executes the search for features (literal string)."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=kwargs.get("locale")))

        js_content = files[0].content
        found = feature in js_content
        score = 100 if found else 0
        locale = kwargs.get("locale")
        report = t("web_dev.js.js_uses_feature.report.found", locale=locale, feature=feature) if found else t("web_dev.js.js_uses_feature.report.not_found", locale=locale, feature=feature)
        return TestResult(
            test_name=self.name,
            score=score, report=report,
            parameters={"feature": feature}
        )

class JsUsesDomManipulation(TestFunction):
    """Checks for the use of DOM manipulation methods."""
    @property
    def name(self):
        return "js_uses_dom_manipulation"
    @property
    def description(self):
        return t("web_dev.js.js_uses_dom_manipulation.description")
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("methods", t("web_dev.js.js_uses_dom_manipulation.param.methods"), "list of strings"),
            ParamDescription("required_count", t("web_dev.js.js_uses_dom_manipulation.param.required_count"), "integer")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, methods: list = None, required_count: int = 0, **kwargs) -> TestResult:
        """Executes the search for DOM manipulations."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=kwargs.get("locale")))

        js_content = files[0].content
        if methods is None:
            methods = []
        found_count = 0
        for method in methods:
            found_count += len(re.findall(r"\." + re.escape(method), js_content))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = t("web_dev.js.js_uses_dom_manipulation.report", locale=kwargs.get("locale"), found_count=found_count, required_count=required_count)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"methods": methods, "required_count": required_count}
        )

class JsHasJsonArrayWithId(TestFunction):
    """Checks for the existence of an array of objects with mandatory keys."""
    @property
    def name(self):
        return "js_has_json_array_with_id"
    @property
    def description(self):
        return t("web_dev.js.js_has_json_array_with_id.description")
    @property
    def required_file(self):
        return "JavaScript"
    @property
    def parameter_description(self):
        return [
            ParamDescription("required_key", t("web_dev.js.js_has_json_array_with_id.param.required_key"), "string"),
            ParamDescription("min_items", t("web_dev.js.js_has_json_array_with_id.param.min_items"), "integer")
        ]

    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, required_key: str = "", min_items: int = 0, **kwargs) -> TestResult:
        """Executes the JSON structure check in JS."""
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=kwargs.get("locale")))

        js_content = files[0].content
        # Regex to find an array assignment: var/let/const variable = [...]
        # It captures the content of the array
        match = re.search(r"(?:var|let|const)\s+\w+\s*=\s*(\[.*?\]);?", js_content, re.DOTALL)
        if not match:
            return TestResult(
                test_name=self.name,
                score=0,
                report=t("web_dev.js.js_has_json_array_with_id.report.no_data", locale=kwargs.get("locale")),
                parameters={"required_key": required_key, "min_items": min_items}
            )
        array_content = match.group(1)
        # A simple heuristic: count how many times the required key appears as a key
        key_pattern = rf'"{required_key}"\s*:'
        found_items = len(re.findall(key_pattern, array_content))
        score = min(100, int((found_items / min_items) * 100)) if min_items > 0 else 100
        report = t("web_dev.js.js_has_json_array_with_id.report.found", locale=kwargs.get("locale"), found_items=found_items, min_items=min_items, required_key=required_key)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"required_key": required_key, "min_items": min_items}
        )
