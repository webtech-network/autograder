import logging
from typing import List, Optional
from autograder.models.dataclass.preflight_error import PreflightError, PreflightCheckType
from autograder.models.dataclass.submission import Submission
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.manager import get_sandbox_manager


class PreFlightService:
    def __init__(self, setup_config):
        self.required_files = setup_config.get('required_files', [])
        self.setup_commands = setup_config.get('setup_commands', []) # TODO: Implement proper setup config object
        self.fatal_errors: List[PreflightError] = []
        self.logger = logging.getLogger("PreFlight")

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

        for command in self.setup_commands:
            self.logger.debug(f"Executing setup command: {command}")
            try:
                response = sandbox.run_command(command)
                if response.exit_code != 0: # TODO: Implement response object in sandbox manager
                    error_msg = f"**Error:** Setup command failed: `'{command}'` with output`{response.output}`"
                    self.logger.error(error_msg)
                    self.fatal_errors.append(PreflightError(
                        type=PreflightCheckType.SETUP_COMMAND,
                        message=error_msg,
                        details={"command": command, "output": response.output}
                    ))
            except Exception as e:
                error_msg = f"**Error:** Failed to execute setup commands: `'{command}'` with output `{str(e)}`"
                self.logger.error(error_msg)
                self.fatal_errors.append(PreflightError(
                    type=PreflightCheckType.SETUP_COMMANDS,
                    message=error_msg,
                    details={"command": command, "error": str(e)}
                ))

        return True

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