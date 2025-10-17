"""Pre Flight module."""

import logging

from autograder.context import request_context


class PreFlight:
    def __init__(self, required_files=None, setup_commands=None):
        self.required_files = required_files if required_files else []
        self.setup_commands = setup_commands if setup_commands else []
        self.fatal_errors = []
        self.logger = logging.getLogger("PreFlight")

    def check_required_files(self):
        """
        Checks for the existence of required files in the submission.
        """
        request = request_context.get_request()
        submission_files = request.submission_files
        self.logger.debug("Checking required files")
        for file in self.required_files:
            if file not in submission_files:
                error_msg = f"**Erro:** Arquivo ou diretório obrigatório não encontrado: `'{file}'`"
                self.logger.error(error_msg)
                self.fatal_errors.append({"type": "file_check", "message": error_msg})

    @classmethod
    def run(cls):
        """
        Creates a PreFlight instance and runs the pre-flight checks.
        """
        request = request_context.get_request()
        setup_dict = request.assignment_config.setup
        preflight = cls(
            required_files=setup_dict.get("file_checks", []),
            setup_commands=setup_dict.get("commands", []),
        )
        preflight.check_required_files()
        # Future: Add command execution logic here if needed
        return preflight.fatal_errors
