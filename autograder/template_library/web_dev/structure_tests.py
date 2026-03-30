from typing import Optional, List

from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.param_description import ParamDescription
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from sandbox_manager.sandbox_container import SandboxContainer


class CheckProjectStructure(TestFunction):
    """Checks if a specific file exists in the submission."""
    @property
    def name(self):
        return "check_project_structure"
    @property
    def description(self):
        return "Verifica se o caminho da estrutura esperada existe nos arquivos de envio."
    @property
    def required_file(self):
        return None
    @property
    def parameter_description(self):
        return [
            ParamDescription("submission_files", "O dicionário de arquivos enviados.", "dictionary"),
            ParamDescription("expected_structure", "O caminho do arquivo esperado.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, expected_structure: str = "", **kwargs) -> TestResult:
        """Executes the file existence check."""
        if not files:
            return TestResult(self.name, 0, "No files provided.")

        submission_files = {f.filename: f for f in files}
        exists = expected_structure in submission_files
        score = 100 if exists else 0
        report = f"O arquivo '{expected_structure}' existe." if exists else f"O arquivo '{expected_structure}' não existe."
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
        return "Verifica se um diretório específico existe no envio."
    @property
    def required_file(self):
        return None
    @property
    def parameter_description(self):
        return [
            ParamDescription("submission_files", "O dicionário de arquivos enviados.", "dictionary"),
            ParamDescription("dir_path", "O caminho do diretório.", "string")
        ]
    def execute(self, files: Optional[List[SubmissionFile]], sandbox: Optional[SandboxContainer], *args, dir_path: str = "", **kwargs) -> TestResult:
        """Executes the directory existence check."""
        if not files:
            return TestResult(self.name, 0, "No files provided.")

        submission_files = {f.filename: f for f in files}
        exists = any(f.startswith(dir_path.rstrip('/') + '/') for f in submission_files.keys())
        score = 100 if exists else 0
        report = f"O diretório '{dir_path}' existe." if exists else f"O diretório '{dir_path}' não existe."
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            parameters={"dir_path": dir_path}
        )
