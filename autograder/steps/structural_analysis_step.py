import logging
from typing import Dict, Optional

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName
from autograder.models.dataclass.structural_analysis_result import StructuralAnalysisResult
from sandbox_manager.models.sandbox_models import Language

logger = logging.getLogger(__name__)

try:
    from ast_grep_py import SgRoot
except ImportError:
    SgRoot = None

class StructuralAnalysisStep(Step):
    """
    Parses submission files into ast-grep SgRoot objects.
    This enables structural pattern matching in subsequent grading steps.
    """

    @property
    def step_name(self) -> StepName:
        return StepName.STRUCTURAL_ANALYSIS

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        submission = pipeline_exec.submission
        language = submission.language
        
        if not language:
            logger.warning("No language specified for submission; skipping structural analysis.")
            return pipeline_exec.add_step_result(StepResult.success(self.step_name, StructuralAnalysisResult(roots={})))

        if SgRoot is None:
            logger.error("ast-grep-py is not installed; structural analysis will be skipped.")
            return pipeline_exec.add_step_result(StepResult.fail(self.step_name, "ast-grep-py not installed"))

        ast_grep_lang = self._map_language(language)
        if not ast_grep_lang:
            logger.warning(f"Language {language.value} is not supported by ast-grep; skipping.")
            return pipeline_exec.add_step_result(StepResult.success(self.step_name, StructuralAnalysisResult(roots={})))

        roots: Dict[str, Optional[SgRoot]] = {}
        for filename, sub_file in submission.submission_files.items():
            # Only parse files that likely contain code
            if not self._is_code_file(filename):
                continue

            try:
                roots[filename] = SgRoot(sub_file.content, ast_grep_lang)
            except Exception as e:
                logger.warning(f"Failed to parse {filename} with ast-grep: {e}")
                roots[filename] = None

        result = StructuralAnalysisResult(roots=roots)
        return pipeline_exec.add_step_result(StepResult.success(self.step_name, result))

    def _map_language(self, language: Language) -> Optional[str]:
        mapping = {
            Language.PYTHON: "python",
            Language.JAVA: "java",
            Language.NODE: "javascript",
            Language.CPP: "cpp",
            Language.C: "c",
        }
        return mapping.get(language)

    def _is_code_file(self, filename: str) -> bool:
        """Heuristic to avoid parsing non-code files."""
        # Common binary/config/doc extensions to ignore
        ignored_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.tar', '.gz', '.json', '.yaml', '.yml', '.md', '.txt'}
        return not any(filename.lower().endswith(ext) for ext in ignored_extensions)
