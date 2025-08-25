# /autograder/core/test_engine/adapters/html_css_js_preset_adapter.py
import json
import os
from autograder.core.test_engine.engine_port import EnginePort
from autograder.core.test_generation.test_library import html_tests, css_tests, js_tests


class HtmlCssJsPresetAdapter(EnginePort):
    """
    An adapter for running dynamic, configuration-based tests for HTML, CSS, and JS projects.
    """

    def __init__(self, preset_config):
        super().__init__()
        self.preset_config = preset_config
        self.results = {"base": [], "bonus": [], "penalty": []}
        self.submission_path = os.path.join(self.REQUEST_BUCKET_DIR, 'submission')

        # Load and parse all necessary files once
        self.soup = html_tests.parse_html(self.submission_path)
        self.css_content = css_tests.parse_css(self.submission_path)
        self.js_content = js_tests.parse_js(self.submission_path)

    def run_tests(self):
        """
        Orchestrates the test execution based on the preset_config.
        """
        for category in ["base", "bonus", "penalty"]:
            category_config = self.preset_config.get(category, {})
            self._run_html_checks(category, category_config.get("html", {}))
            self._run_css_checks(category, category_config.get("css", {}))
            self._run_js_checks(category, category_config.get("js", {}))

        self.normalize_output()

    def _run_html_checks(self, category, config):
        """Runs all configured HTML checks."""
        if not self.soup:
            self._add_result(category, "html_parsing", "failed", "Could not find or parse index.html.")
            return

        # Example for a flag-based check
        if config.get("accessibility", {}).get("images_have_alt"):
            self._execute_check(category, "html_images_have_alt", html_tests.check_images_have_alt, self.soup)

        # Example for a list-based check
        if "required_tags" in config:
            for tag in config["required_tags"]:
                self._execute_check(category, f"html_has_{tag}_tag", html_tests.check_has_tag, self.soup, tag)

        # ... Add similar logic for all other HTML checks ...

    def _run_css_checks(self, category, config):
        """Runs all configured CSS checks."""
        if not self.css_content:
            self._add_result(category, "css_parsing", "failed", "Could not find or parse style.css.")
            return

        if config.get("best_practices", {}).get("no_important"):
            self._execute_check(category, "css_no_important", css_tests.check_no_important, self.css_content)

        # ... Add similar logic for all other CSS checks ...

    def _run_js_checks(self, category, config):
        """Runs all configured JavaScript checks."""
        if not self.js_content:
            self._add_result(category, "js_parsing", "failed", "Could not find or parse script.js.")
            return

        if config.get("syntax_and_declarations", {}).get("uses_strict_mode"):
            self._execute_check(category, "js_uses_strict_mode", js_tests.check_uses_strict_mode, self.js_content)

        # ... Add similar logic for all other JS checks ...

    def _execute_check(self, category, test_name, check_function, *args):
        """
        A helper to run a single check and record its result.
        """
        try:
            check_function(*args)
            self._add_result(category, test_name, "passed")
        except AssertionError as e:
            self._add_result(category, test_name, "failed", str(e))

    def _add_result(self, category, test_name, status, message=""):
        """Adds a test result to the appropriate category."""
        self.results[category].append({
            "test": test_name,
            "status": status,
            "message": message,
            "subject": "html-css-js"  # Or derive from config if needed
        })

    def normalize_output(self):
        """
        Saves the results to the standardized JSON report files.
        """
        for category, results_list in self.results.items():
            if results_list:
                output_path = os.path.join(self.RESULTS_DIR, f"test_{category}_results.json")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(results_list, f, indent=2, ensure_ascii=False)
