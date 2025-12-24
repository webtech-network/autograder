import logging
from typing import List
from autograder.models.dataclass.preflight_error import PreflightError, PreflightCheckType


class PreFlightService:
    def __init__(self, setup_config):
        self.required_files = setup_config.get('required_files', [])
        self.setup_commands = setup_config.get('setup_commands', [])
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

    def check_setup_commands(self) -> bool:
        """
        Executes setup commands in a sandbox environment.
        Returns True if all commands succeed, False otherwise.

        TODO: Implement sandbox container creation and command execution.
        Note: Should validate that sandbox is required if setup_commands are present.
        """
        self.logger.debug("Checking setup commands")

        if not self.setup_commands:
            self.logger.debug("No setup commands to execute")
            return True

        # TODO: Implement actual setup command execution
        # This should:
        # 1. Create sandbox container
        # 2. Execute each command
        # 3. Check exit codes
        # 4. Append PreflightError if any command fails

        return True

    def has_errors(self) -> bool:
        """Check if any fatal errors were found during preflight checks."""
        return len(self.fatal_errors) > 0

    def get_error_messages(self) -> List[str]:
        """Get all error messages as a list of strings."""
        return [error.message for error in self.fatal_errors]


"""
Setup commands here is a problem. 
The pre-flight service should be responsible for also creating the sandbox container
and executing the setup commmands, so that if one of them fails, the pipeline already stops
However, it's important to check if there's really a need for creating a sandbox. 
Maybe add a config validation step before the pipeline starts?
Example: If someone sets setup commands but the template does not require a sandbox,
it should raise a configuration error before starting the pipeline.
"""


