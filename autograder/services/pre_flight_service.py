import logging
from typing import List, Optional
from autograder.models.dataclass.preflight_error import PreflightError, PreflightCheckType
from autograder.models.dataclass.submission import Submission
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language, ResponseCategory


class PreFlightService:
    def __init__(self, setup_config, submission_language: Language):
        """
        Initialize PreFlightService with language-specific setup configuration.

        Args:
            setup_config: Language-specific configs: {'python': {...}, 'java': {...}, 'node': {...}, 'cpp': {...}}
            submission_language: Language of the submission (required)
        """
        self.submission_language = submission_language
        self.raw_setup_config = setup_config or {}
        self.logger = logging.getLogger("PreFlight")
        self.fatal_errors: List[PreflightError] = []

        # Resolve language-specific config
        resolved_config = self._resolve_setup_config(setup_config, submission_language)

        self.required_files = resolved_config.get('required_files', [])
        self.setup_commands = resolved_config.get('setup_commands', [])

    def _resolve_setup_config(self, setup_config, submission_language: Language) -> dict:
        """
        Resolve setup config for the submission language.

        Format (required):
        {
            "python": {
                "required_files": ["file.py"],
                "setup_commands": []
            },
            "java": {
                "required_files": ["File.java"],
                "setup_commands": ["javac File.java"]
            },
            "node": {
                "required_files": ["file.js"],
                "setup_commands": ["npm install"]
            },
            "cpp": {
                "required_files": ["file.cpp"],
                "setup_commands": ["g++ file.cpp -o file"]
            }
        }
        """
        if not setup_config:
            return {}

        lang_key = submission_language.value
        if lang_key in setup_config:
            self.logger.info("Using setup config for %s", lang_key)
            return setup_config[lang_key]
        self.logger.warning("No setup config found for language %s, using empty config", lang_key)
        return {}

    def check_required_files(self, submission_files) -> bool:
        """
        Checks for the existence of required files in the submission.
        Returns True if all required files exist, False otherwise.
        """
        self.logger.debug("Checking required files")

        if not self.required_files:
            self.logger.debug("No required files to check")
            return True

        for file in self.required_files:
            if file not in submission_files:
                error_msg = f"**Erro:** Arquivo ou diretório obrigatório não encontrado: `'{file}'`"
                self.logger.error(error_msg)
                self.fatal_errors.append(PreflightError(
                    type=PreflightCheckType.FILE_CHECK,
                    message=error_msg,
                    details={"missing_file": file}
                ))

        # Return True only if no file check errors were added
        file_check_errors = [e for e in self.fatal_errors if e.type == PreflightCheckType.FILE_CHECK]
        return len(file_check_errors) == 0




    def has_errors(self) -> bool:
        """Check if any fatal errors were found during preflight checks."""
        return len(self.fatal_errors) > 0

    def get_error_messages(self) -> List[str]:
        """Get all error messages as a list of strings."""
        return [error.message for error in self.fatal_errors]
