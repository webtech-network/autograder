from typing import Optional, List

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from sandbox_manager.sandbox_container import SandboxContainer


class CheckProjectStructure(TestFunction):
    """Checks if a specific file exists in the submission."""
    @property
    def name(self):
        return "check_project_structure"
    @property
    def description(self):
        return t("web_dev.structure.check_project_structure.description")
    @property
    def required_file(self):
        return None
    @property
    def parameter_description(self):
        return [
            ParamDescription("submission_files", t("web_dev.structure.check_project_structure.param.submission_files"), "dictionary"),
            ParamDescription("expected_structure", t("web_dev.structure.check_project_structure.param.expected_structure"), "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, expected_structure: str = "", **kwargs) -> TestResult:
        """Executes the file existence check."""
        if not files:
            return TestResult(self.name, 0, t("web_dev.error.no_files", locale=kwargs.get("locale")))

        submission_files = {f.filename: f for f in files}
        exists = expected_structure in submission_files
        score = 100 if exists else 0
        locale = kwargs.get("locale")
        report = t("web_dev.structure.check_project_structure.report.found", locale=locale, expected_structure=expected_structure) if exists else t("web_dev.structure.check_project_structure.report.not_found", locale=locale, expected_structure=expected_structure)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"expected_structure": expected_structure}
        )

class CheckDirExists(TestFunction):
    """Checks if a specific directory exists in the submission."""
    @property
    def name(self):
        return "check_dir_exists"
    @property
    def description(self):
        return t("web_dev.structure.check_dir_exists.description")
    @property
    def required_file(self):
        return None
    @property
    def parameter_description(self):
        return [
            ParamDescription("submission_files", t("web_dev.structure.check_dir_exists.param.submission_files"), "dictionary"),
            ParamDescription("dir_path", t("web_dev.structure.check_dir_exists.param.dir_path"), "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, dir_path: str = "", **kwargs) -> TestResult:
        """Executes the directory existence check."""
        if not files:
            return TestResult(self.name, 0, t("web_dev.error.no_files", locale=kwargs.get("locale")))

        submission_files = {f.filename: f for f in files}
        exists = any(f.startswith(dir_path.rstrip('/') + '/') for f in submission_files.keys())
        score = 100 if exists else 0
        locale = kwargs.get("locale")
        report = t("web_dev.structure.check_dir_exists.report.found", locale=locale, dir_path=dir_path) if exists else t("web_dev.structure.check_dir_exists.report.not_found", locale=locale, dir_path=dir_path)
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"dir_path": dir_path}
        )
