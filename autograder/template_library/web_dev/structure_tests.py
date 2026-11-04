from typing import Annotated

from pydantic import Field

from autograder.models.abstract.test_function import EvaluationInput, TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t


class CheckProjectStructure(TestFunction):
    """Checks if a specific file exists in the submission."""

    uses_context_files = True
    @property
    def name(self):
        return "check_project_structure"
    @property
    def description(self):
        return t("web_dev.structure.check_project_structure.description")
    def execute(self, evaluation: EvaluationInput, *,
                expected_structure: Annotated[str, Field(min_length=1, description=t("web_dev.structure.check_project_structure.param.expected_structure"))],
                ) -> TestResult:
        """Executes the file existence check."""
        files = evaluation.files
        if not files:
            return TestResult(self.name, 0, t("web_dev.error.no_files", locale=evaluation.locale))

        submission_files = {f.filename: f for f in files}
        exists = expected_structure in submission_files
        score = 100 if exists else 0
        locale = evaluation.locale
        report = t("web_dev.structure.check_project_structure.report.found", locale=locale, expected_structure=expected_structure) if exists else t("web_dev.structure.check_project_structure.report.not_found", locale=locale, expected_structure=expected_structure)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )

class CheckDirExists(TestFunction):
    """Checks if a specific directory exists in the submission."""

    uses_context_files = True
    @property
    def name(self):
        return "check_dir_exists"
    @property
    def description(self):
        return t("web_dev.structure.check_dir_exists.description")
    def execute(self, evaluation: EvaluationInput, *,
                dir_path: Annotated[str, Field(min_length=1, description=t("web_dev.structure.check_dir_exists.param.dir_path"))],
                ) -> TestResult:
        """Executes the directory existence check."""
        files = evaluation.files
        if not files:
            return TestResult(self.name, 0, t("web_dev.error.no_files", locale=evaluation.locale))

        submission_files = {f.filename: f for f in files}
        exists = any(f.startswith(dir_path.rstrip('/') + '/') for f in submission_files.keys())
        score = 100 if exists else 0
        locale = evaluation.locale
        report = t("web_dev.structure.check_dir_exists.report.found", locale=locale, dir_path=dir_path) if exists else t("web_dev.structure.check_dir_exists.report.not_found", locale=locale, dir_path=dir_path)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report
        )
