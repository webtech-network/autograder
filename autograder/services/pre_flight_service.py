import logging
from typing import List, Optional
from autograder.models.dataclass.preflight_error import PreflightError, PreflightCheckType
from autograder.models.dataclass.submission import Submission
from autograder.services.sandbox_service import SandboxService
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
        self._sandbox_service = SandboxService()

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

    def has_errors(self) -> bool:
        """
        Check if any fatal errors were recorded during preflight checks.
        """
        return len(self.fatal_errors) > 0

    def get_error_messages(self) -> List[str]:
        """
        Get all fatal error messages recorded during preflight checks.
        These messages are typically Markdown strings for student feedback.
        """
        return [error.message for error in self.fatal_errors]

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

    def check_setup_commands(self, sandbox: SandboxContainer) -> bool:
        """
        Executes setup commands in the sandbox and interprets the results.
        Creates PreflightError objects for any failures.
        
        Returns:
            True if all commands succeeded, False otherwise. Errors are stored in self.fatal_errors.
        """
        if not sandbox:
            error_msg = "Sandbox environment is required for executing setup commands but was not created."
            self.logger.error(error_msg)
            self.fatal_errors.append(PreflightError(
                type=PreflightCheckType.SETUP_COMMAND,
                message=error_msg,
                details={}
            ))
            return False

        if not self.setup_commands:
            self.logger.debug("No setup commands to execute")
            return True

        for idx, command_spec in enumerate(self.setup_commands):
            # Call SandboxService to execute one command at a time
            response = self._sandbox_service.run_setup_command(sandbox, command_spec, idx)

            # Check if response indicates an error
            if response.category != ResponseCategory.SUCCESS:
                # Extract command name and command for error reporting
                if isinstance(command_spec, dict):
                    command_name = command_spec.get('name', f'Setup Command {idx + 1}')
                    command = command_spec.get('command', '')
                else:
                    command_name = f'Setup Command {idx + 1}'
                    command = command_spec

                error_msg = self._format_command_error(command_name, command, response)
                self.logger.error(error_msg)
                self.fatal_errors.append(PreflightError(
                    type=PreflightCheckType.SETUP_COMMAND,
                    message=error_msg,
                    details={
                        "command_name": command_name,
                        "command": command,
                        "exit_code": response.exit_code,
                        "category": response.category.value,
                        "stdout": response.stdout,
                        "stderr": response.stderr
                    }
                ))
                # Stop on first failure for setup commands (e.g., failed compilation)
                return False

        return True

    def _format_command_error(self, command_name: str, command: str, response) -> str:
        """Helper to format detailed error messages for students."""
        if response.category == ResponseCategory.SYSTEM_ERROR:
            # For system errors, the stderr already contains the error message
            return f"**Error:** {response.stderr}"
        
        error_msg = f"**Error:** Setup command '{command_name}' failed"
        if response.category:
            error_msg += f" ({response.category.value})"
        error_msg += f" with exit code {response.exit_code}\n\n"
        
        error_msg += f"**Command:** `{command}`\n\n"

        if response.stdout and response.stdout.strip():
            error_msg += f"**Output (stdout):**\n```\n{response.stdout.strip()}\n```\n\n"

        if response.stderr and response.stderr.strip():
            error_msg += f"**Error Output (stderr):**\n```\n{response.stderr.strip()}\n```"

        return error_msg.strip()
