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
            self.logger.info(f"Using setup config for {lang_key}")
            return setup_config[lang_key]
        else:
            self.logger.warning(f"No setup config found for language {lang_key}, using empty config")
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

    def check_setup_commands(self, sandbox: SandboxContainer) -> bool:
        """
        Executes setup commands in a sandbox environment.
        Returns True if all commands succeed, False otherwise.

        Setup commands can be either:
        - String: "javac Calculator.java"
        - Object: {"name": "Compile Calculator", "command": "javac Calculator.java"}

        args:
            - sandbox: The sandbox container where setup commands should be executed. Should not be None if setup_commands are defined.
        """
        self.logger.debug("Checking setup commands")
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
            # Parse command specification (supports both string and object format)
            if isinstance(command_spec, dict):
                command_name = command_spec.get('name', f'Setup Command {idx + 1}')
                command = command_spec.get('command')
                if not command:
                    error_msg = f"**Error:** Setup command '{command_name}' is missing the 'command' field"
                    self.logger.error(error_msg)
                    self.fatal_errors.append(PreflightError(
                        type=PreflightCheckType.SETUP_COMMAND,
                        message=error_msg,
                        details={"command_name": command_name, "index": idx}
                    ))
                    continue
            elif isinstance(command_spec, str):
                command_name = f'Setup Command {idx + 1}'
                command = command_spec
            else:
                error_msg = f"**Error:** Invalid setup command format at index {idx}: expected string or object"
                self.logger.error(error_msg)
                self.fatal_errors.append(PreflightError(
                    type=PreflightCheckType.SETUP_COMMAND,
                    message=error_msg,
                    details={"index": idx, "type": str(type(command_spec))}
                ))
                continue

            self.logger.debug(f"Executing setup command '{command_name}': {command}")
            try:
                response = sandbox.run_command(command)
                self.logger.debug(f"Setup command '{command_name}' exit code: {response.exit_code}")
                self.logger.debug(f"Setup command '{command_name}' category: {response.category.value}")

                # Use the new category classification
                if response.category != ResponseCategory.SUCCESS:
                    error_msg = self._format_setup_command_error(command_name, command, response)
                    self.logger.error(error_msg)
                    self.fatal_errors.append(PreflightError(
                        type=PreflightCheckType.SETUP_COMMAND,
                        message=error_msg,
                        details={
                            "command_name": command_name,
                            "command": command,
                            "exit_code": response.exit_code,
                            "category": response.category.value,  # Track the category here
                            "stdout": response.stdout,
                            "stderr": response.stderr
                        }
                    ))
            except Exception as e:
                error_msg = f"**Error:** Setup command '{command_name}' failed to execute: `{str(e)}`\n\nCommand: `{command}`"
                self.logger.error(error_msg)
                self.fatal_errors.append(PreflightError(
                    type=PreflightCheckType.SETUP_COMMAND,
                    message=error_msg,
                    details={"command_name": command_name, "command": command, "error": str(e)}
                ))

        return len([e for e in self.fatal_errors if e.type == PreflightCheckType.SETUP_COMMAND]) == 0

    def _format_setup_command_error(self, command_name: str, command: str, response) -> str:
        """
        Format a detailed error message for failed setup commands.

        Args:
            command_name: Human-readable name of the command
            command: The actual command that was executed
            response: CommandResponse object with execution details
        """
        error_msg = f"**Error:** Setup command '{command_name}' failed with exit code {response.exit_code}\n\n"
        error_msg += f"**Command:** `{command}`\n\n"

        if response.stdout and response.stdout.strip():
            error_msg += f"**Output (stdout):**\n```\n{response.stdout.strip()}\n```\n\n"

        if response.stderr and response.stderr.strip():
            error_msg += f"**Error Output (stderr):**\n```\n{response.stderr.strip()}\n```"

        return error_msg.strip()

    def create_sandbox(self, submission: Submission) -> Optional[SandboxContainer]:
        """
        Creates a sandbox environment for the submission if needed.
        Sandbox image is based on the submission language.
        Returns the created SandboxContainer or None if not needed.

        args:
            - submission: The submission object containing necessary information for sandbox creation (e.g., language, files).
        """
        if not submission.language:
            self.logger.error("No language specified in submission for sandbox creation")
            raise ValueError("Submission language is required for sandbox creation")
        try:
            from sandbox_manager.manager import get_sandbox_manager
            sandbox_manager = get_sandbox_manager()
            sandbox = sandbox_manager.get_sandbox(submission.language)
            self.logger.debug(f"Sandbox created for language {submission.language}")

            # Prepare workdir by copying submission files to container
            if submission.submission_files:
                try:
                    sandbox.prepare_workdir(submission.submission_files)
                    self.logger.debug(f"Workdir prepared with {len(submission.submission_files)} files")
                except Exception as e:
                    error_msg = f"**Error:** Failed to prepare workdir in sandbox: `{str(e)}`"
                    self.logger.error(error_msg)
                    self.fatal_errors.append(PreflightError(
                        type=PreflightCheckType.SANDBOX_CREATION,
                        message=error_msg,
                        details={"error": str(e)}
                    ))
                    # Release the sandbox back to pool since it's unusable
                    sandbox_manager.release_sandbox(submission.language, sandbox)
                    return None

            return sandbox
        except Exception as e:
            error_msg = f"**Error:** Failed to create sandbox for language `{submission.language}`: `{str(e)}`"
            self.logger.error(error_msg)
            self.fatal_errors.append(PreflightError(
                type=PreflightCheckType.SANDBOX_CREATION,
                message=error_msg,
                details={"language": submission.language, "error": str(e)}
            ))
            return None


    def has_errors(self) -> bool:
        """Check if any fatal errors were found during preflight checks."""
        return len(self.fatal_errors) > 0

    def get_error_messages(self) -> List[str]:
        """Get all error messages as a list of strings."""
        return [error.message for error in self.fatal_errors]
