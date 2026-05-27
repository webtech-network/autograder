import logging
from typing import Dict, Optional

from autograder.models.abstract.step import Step
from autograder.models.pipeline_execution import PipelineExecution
from autograder.models.dataclass.step_result import StepResult, StepName, StepCategory
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

    @property
    def step_category(self) -> StepCategory:
        return StepCategory.GRADING

    def _execute(self, pipeline_exec: PipelineExecution) -> PipelineExecution:
        submission = pipeline_exec.submission
        language = submission.language

        if not language:
            logger.warning("No language specified for submission; skipping structural analysis.")
            return pipeline_exec.add_step_result(
                StepResult.success(
                    self.step_name,
                    StructuralAnalysisResult(
                        roots={},
                        available=False,
                        reason="missing_submission_language",
                    ),
                )
            )

        if SgRoot is None:
            logger.warning("ast-grep-py is not installed; skipping structural analysis.")
            return pipeline_exec.add_step_result(
                StepResult.success(
                    self.step_name,
                    StructuralAnalysisResult(
                        roots={},
                        available=False,
                        reason="ast_grep_unavailable",
                    ),
                )
            )

        ast_grep_lang = self._map_language(language)
        if not ast_grep_lang:
            logger.warning(f"Language {language.value} is not supported by ast-grep; skipping.")
            return pipeline_exec.add_step_result(
                StepResult.success(
                    self.step_name,
                    StructuralAnalysisResult(
                        roots={},
                        available=False,
                        reason=f"unsupported_language:{language.value}",
                    ),
                )
            )

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

        result = StructuralAnalysisResult(roots=roots, available=True)
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
