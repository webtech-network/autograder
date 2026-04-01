import logging
from typing import List, Optional, Any
from autograder.models.dataclass.submission import Submission
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language, ResponseCategory, CommandResponse
from autograder.translations import t

class SandboxService:
    """
    Service responsible for sandbox management and setup command execution.
    Decoupled from PreFlightService to allow standalone sandbox lifecycle management.
    """
    def __init__(self):
        self.logger = logging.getLogger("SandboxService")

    def create_sandbox(self, submission: Submission) -> Optional[SandboxContainer]:
        """
        Creates and prepares a sandbox environment for the submission.
        
        Args:
            submission: The submission object containing language and files.
        Returns:
            The prepared SandboxContainer or None if creation failed.
        """
        if not submission.language:
            self.logger.error("No language specified in submission for sandbox creation")
            raise ValueError("Submission language is required for sandbox creation")
            
        try:
            from sandbox_manager.manager import get_sandbox_manager
            sandbox_manager = get_sandbox_manager()
            sandbox = sandbox_manager.get_sandbox(submission.language)
            self.logger.debug("Sandbox created for language %s", submission.language)

            # Prepare workdir by copying submission files to container
            if submission.submission_files:
                try:
                    sandbox.prepare_workdir(submission.submission_files)
                    self.logger.debug("Workdir prepared with %s files", len(submission.submission_files))
                except Exception as e:
                    self.logger.error("Failed to prepare workdir in sandbox: %s", str(e))
                    # Release the sandbox back to pool since it's unusable
                    sandbox_manager.release_sandbox(submission.language, sandbox)
                    return None

            return sandbox
        except Exception as e:
            self.logger.error("Failed to create sandbox for language %s: %s", submission.language, str(e))
            return None

    def release_sandbox(self, language: Language, sandbox: SandboxContainer):
        """
        Releases a sandbox back to the manager pool.
        """
        try:
            from sandbox_manager.manager import get_sandbox_manager
            sandbox_manager = get_sandbox_manager()
            sandbox_manager.release_sandbox(language, sandbox)
            self.logger.info("Sandbox released for language %s", language)
        except Exception as e:
            self.logger.warning("Failed to release sandbox: %s", str(e))

    def run_setup_command(self, sandbox: SandboxContainer, command_spec: Any, idx: int = 0, locale: Optional[str] = None) -> CommandResponse:
        """
        Executes a single setup command (e.g., compilation) in the provided sandbox.
        
        The caller (e.g., PreFlightService) is responsible for interpreting the response
        and creating appropriate error objects. 
        
        Args:
            sandbox: The sandbox container to execute the command in.
            command_spec: Command specification (either string or dict with 'command' key).
            idx: Optional index used for default naming if 'name' is not provided in spec.
            locale: User's locale for error messages (default: None, resolves to 'en')
        
        Returns:
            CommandResponse: Result of the command. ResponseCategory indicates success/failure.
        """
        if not sandbox:
            error_msg = t("preflight.error.setup_command_missing_sandbox", locale=locale)
            self.logger.error(error_msg)
            return CommandResponse(
                stdout="",
                stderr=error_msg,
                exit_code=-1,
                execution_time=0,
                category=ResponseCategory.SYSTEM_ERROR
            )

        # Parse command specification
        if isinstance(command_spec, dict):
            command_name = command_spec.get('name', f'Setup Command {idx + 1}')
            command = command_spec.get('command')
            if not command:
                error_msg = t("preflight.error.setup_command_missing_field", locale=locale, command_name=command_name)
                self.logger.error(error_msg)
                return CommandResponse(
                    stdout="",
                    stderr=error_msg,
                    exit_code=-1,
                    execution_time=0,
                    category=ResponseCategory.SYSTEM_ERROR
                )
        elif isinstance(command_spec, str):
            command_name = f'Setup Command {idx + 1}'
            command = command_spec
        else:
            error_msg = t("preflight.error.setup_command_invalid_format", locale=locale, index=idx)
            self.logger.error(error_msg)
            return CommandResponse(
                stdout="",
                stderr=error_msg,
                exit_code=-1,
                execution_time=0,
                category=ResponseCategory.SYSTEM_ERROR
            )

        self.logger.debug("Executing setup command '%s': %s", command_name, command)
        try:
            return sandbox.run_command(command)
        except Exception as e:
            error_msg = t("preflight.error.setup_command_failed_execution", locale=locale, command_name=command_name, error=str(e), command=command)
            self.logger.error(error_msg)
            return CommandResponse(
                stdout="",
                stderr=error_msg,
                exit_code=-1,
                execution_time=0,
                category=ResponseCategory.SYSTEM_ERROR
            )
