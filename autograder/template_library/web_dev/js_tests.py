import re
from typing import Annotated, List

from pydantic import Field

from autograder.models.abstract.test_function import EvaluationInput, TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t


class CountGlobalVars(TestFunction):
    """Counts variables in the global scope of JS."""
    absence_check = "Limit: passes while global variables number at most max_allowed."
    @property
    def name(self):
        return "count_global_vars"
    @property
    def description(self):
        return t("web_dev.js.count_global_vars.description")
    file_extensions = (".js", ".mjs", ".cjs")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                max_allowed: Annotated[int, Field(ge=0, description=t("web_dev.js.count_global_vars.param.max_allowed"))] = 0,
                ) -> TestResult:
        """Executes the global variable count."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=evaluation.locale))

        js_content = files[0].content
        found_count = len(re.findall(r"^\s*(var|let|const)\s+", js_content, re.MULTILINE))
        score = 100 if found_count <= max_allowed else 0
        locale = evaluation.locale
        report = t("web_dev.js.count_global_vars.report.over", locale=locale, found_count=found_count, max_allowed=max_allowed) if score == 0 else t("web_dev.js.count_global_vars.report.ok", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class HasNoJsFramework(TestFunction):
    """Checks if forbidden JS frameworks are present."""
    absence_check = "Prohibition: passes while no JavaScript framework is referenced."

    file_parameters = ("html_file", "js_file")
    @property
    def name(self):
        return "has_no_js_framework"
    @property
    def description(self):
        return t("web_dev.js.has_no_js_framework.description")
    def execute(self, evaluation: EvaluationInput, *,
                html_file: Annotated[str, Field(min_length=1, description=t("web_dev.js.has_no_js_framework.param.html_file"))],
                js_file: Annotated[str, Field(min_length=1, description=t("web_dev.js.has_no_js_framework.param.js_file"))],
                ) -> TestResult:
        """Executes the framework verification."""
        files = evaluation.files
        if not files:
            return TestResult(self.name, 0, t("web_dev.error.no_files", locale=evaluation.locale))

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
        locale = evaluation.locale
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
    file_extensions = (".js", ".mjs", ".cjs")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput) -> TestResult:
        """Executes the query string pattern search."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=evaluation.locale))

        js_content = files[0].content
        # Regex to find 'URLSearchParams' or 'window.location.search'
        pattern = re.compile(r"URLSearchParams|window\.location\.search")
        found = pattern.search(js_content) is not None
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.js.js_uses_query_string_parsing.report.found", locale=locale) if found else t("web_dev.js.js_uses_query_string_parsing.report.not_found", locale=locale)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class UsesForbiddenMethod(TestFunction):
    """Checks and penalizes the use of forbidden methods."""
    absence_check = "Prohibition: passes while the forbidden method is not called."
    @property
    def name(self):
        return "uses_forbidden_method"
    @property
    def description(self):
        return t("web_dev.js.uses_forbidden_method.description")
    file_extensions = (".js", ".mjs", ".cjs")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                method: Annotated[str, Field(min_length=1, description=t("web_dev.js.uses_forbidden_method.param.method"))],
                ) -> TestResult:
        """Executes the search for forbidden methods."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=evaluation.locale))

        js_content = files[0].content
        found = method in js_content
        score = 0 if found else 100
        locale = evaluation.locale
        report = t("web_dev.js.uses_forbidden_method.report.found", locale=locale, method=method) if found else t("web_dev.js.uses_forbidden_method.report.not_found", locale=locale, method=method)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class JsUsesFeature(TestFunction):
    """Checks if a specific JS feature is present."""
    @property
    def name(self): return "js_uses_feature"
    @property
    def description(self): return t("web_dev.js.js_uses_feature.description")
    file_extensions = (".js", ".mjs", ".cjs")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                feature: Annotated[str, Field(min_length=1, description=t("web_dev.js.js_uses_feature.param.feature"))],
                ) -> TestResult:
        """Executes the search for features (literal string)."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=evaluation.locale))

        js_content = files[0].content
        found = feature in js_content
        score = 100 if found else 0
        locale = evaluation.locale
        report = t("web_dev.js.js_uses_feature.report.found", locale=locale, feature=feature) if found else t("web_dev.js.js_uses_feature.report.not_found", locale=locale, feature=feature)
        return TestResult(
            test_name=self.name,
            score=score, report=report
        )

class JsUsesDomManipulation(TestFunction):
    """Checks for the use of DOM manipulation methods."""
    @property
    def name(self):
        return "js_uses_dom_manipulation"
    @property
    def description(self):
        return t("web_dev.js.js_uses_dom_manipulation.description")
    file_extensions = (".js", ".mjs", ".cjs")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                methods: Annotated[List[Annotated[str, Field(min_length=1)]], Field(min_length=1, description=t("web_dev.js.js_uses_dom_manipulation.param.methods"))],
                required_count: Annotated[int, Field(ge=1, description=t("web_dev.js.js_uses_dom_manipulation.param.required_count"))] = 1,
                ) -> TestResult:
        """Executes the search for DOM manipulations."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=evaluation.locale))

        js_content = files[0].content
        if methods is None:
            methods = []
        found_count = 0
        for method in methods:
            found_count += len(re.findall(r"\." + re.escape(method), js_content))
        score = min(100, int((found_count / required_count) * 100)) if required_count > 0 else 100
        report = t("web_dev.js.js_uses_dom_manipulation.report", locale=evaluation.locale, found_count=found_count, required_count=required_count)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class JsHasJsonArrayWithId(TestFunction):
    """Checks for the existence of an array of objects with mandatory keys."""
    @property
    def name(self):
        return "js_has_json_array_with_id"
    @property
    def description(self):
        return t("web_dev.js.js_has_json_array_with_id.description")
    file_extensions = (".js", ".mjs", ".cjs")
    minimum_files = 1
    maximum_files = 1
    def execute(self, evaluation: EvaluationInput, *,
                required_key: Annotated[str, Field(min_length=1, description=t("web_dev.js.js_has_json_array_with_id.param.required_key"))],
                min_items: Annotated[int, Field(ge=1, description=t("web_dev.js.js_has_json_array_with_id.param.min_items"))] = 1,
                ) -> TestResult:
        """Executes the JSON structure check in JS."""
        files = evaluation.files
        if not files or len(files) == 0:
            return TestResult(self.name, 0, t("web_dev.error.no_js", locale=evaluation.locale))

        js_content = files[0].content
        # Regex to find an array assignment: var/let/const variable = [...]
        # It captures the content of the array
        match = re.search(r"(?:var|let|const)\s+\w+\s*=\s*(\[.*?\]);?", js_content, re.DOTALL)
        if not match:
            return TestResult(
                test_name=self.name,
                score=0,
                report=t("web_dev.js.js_has_json_array_with_id.report.no_data", locale=evaluation.locale)
            )
        array_content = match.group(1)
        # A simple heuristic: count how many times the required key appears as a key
        key_pattern = rf'"{required_key}"\s*:'
        found_items = len(re.findall(key_pattern, array_content))
        score = min(100, int((found_items / min_items) * 100)) if min_items > 0 else 100
        report = t("web_dev.js.js_has_json_array_with_id.report.found", locale=evaluation.locale, found_items=found_items, min_items=min_items, required_key=required_key)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )
