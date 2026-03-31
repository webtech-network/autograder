import logging
from typing import List, Optional, Any
from autograder.models.dataclass.preflight_error import PreflightError, PreflightCheckType
from autograder.models.dataclass.submission import Submission
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language, ResponseCategory

class SandboxService:
    """
    Service responsible for sandbox management and setup command execution.
    Decoupled from PreFlightService to allow standalone sandbox lifecycle management.
    """
    def __init__(self):
        self.logger = logging.getLogger("SandboxService")
        self.fatal_errors: List[PreflightError] = []

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

    def run_setup_commands(self, sandbox: SandboxContainer, setup_commands: List[Any]) -> bool:
        """
        Executes setup commands (e.g., compilation) in the provided sandbox.
        
        Returns:
            True if all commands succeeded, False otherwise. Errors are stored in self.fatal_errors.
        """
        self.logger.debug("Running setup commands")
        if not sandbox:
            error_msg = "Sandbox environment is required for executing setup commands but was not created."
            self.logger.error(error_msg)
            self.fatal_errors.append(PreflightError(
                type=PreflightCheckType.SETUP_COMMAND,
                message=error_msg,
                details={}
            ))
            return False
            
        if not setup_commands:
            self.logger.debug("No setup commands to execute")
            return True

        for idx, command_spec in enumerate(setup_commands):
            # Parse command specification
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
                            "category": response.category.value,
                            "stdout": response.stdout,
                            "stderr": response.stderr
                        }
                    ))
            except Exception as e:
                error_msg = f"**Error:** Setup command '{command_name}' failed to execute: `{str(e)}`"
                self.logger.error(error_msg)
                self.fatal_errors.append(PreflightError(
                    type=PreflightCheckType.SETUP_COMMAND,
                    message=error_msg,
                    details={"command_name": command_name, "command": command, "error": str(e)}
                ))

        return len([e for e in self.fatal_errors if e.type == PreflightCheckType.SETUP_COMMAND]) == 0

    def _format_setup_command_error(self, command_name: str, command: str, response) -> str:
        """Helper to format detailed error messages for students."""
        error_msg = f"**Error:** Setup command '{command_name}' failed with exit code {response.exit_code}\n\n"
        error_msg += f"**Command:** `{command}`\n\n"

        if response.stdout and response.stdout.strip():
            error_msg += f"**Output (stdout):**\n```\n{response.stdout.strip()}\n```\n\n"

        if response.stderr and response.stderr.strip():
            error_msg += f"**Error Output (stderr):**\n```\n{response.stderr.strip()}\n```"

        return error_msg.strip()

    def has_errors(self) -> bool:
        return len(self.fatal_errors) > 0

    def get_error_messages(self) -> List[str]:
        return [error.message for error in self.fatal_errors]
