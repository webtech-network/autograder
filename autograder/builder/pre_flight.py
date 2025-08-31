import logging

class PreFlight:
    def __init__(self,required_files=None,setup_commands=None):
        self.required_files = required_files if required_files else []
        self.setup_commands = setup_commands if setup_commands else []
        self.fatal_errors = []
        self.logger = logging.getLogger("PreFlight")

    def check_required_files(self, submission_files: dict):
        """
        Checks for the existence of required files in the submission.
        """
        self.logger.debug("Checking required files")
        for file in self.required_files:
            if file not in submission_files:
                error_msg = f"Required file or directory not found: '{file}'"
                self.logger.error(error_msg)
                self.fatal_errors.append({"type": "file_check", "message": error_msg})

    @classmethod
    def run(cls,setup_dict: dict, submission_files: dict):
        """
        Creates a PreFlight instance and runs the pre-flight checks.
        """
        preflight = cls(
            required_files=setup_dict.get('file_checks', []),
            setup_commands=setup_dict.get('commands', [])
        )
        preflight.check_required_files(submission_files)
        # Future: Add command execution logic here if needed
        return preflight.fatal_errors

if __name__ == "__main__":
    # Example usage
    setup_config = {
        "file_checks": ["/app/index.html", "styles.css", "script.js"],
        "commands": [
            {"name": "Install Dependencies", "command": "npm install", "background": False}
        ]
    }
    submission_files_example = {
        "/app/index.html": "<html></html>",
        "styles.css": "body { }"
        # Note: script.js is missing
    }
    errors = PreFlight.run(setup_config, submission_files_example)
    print("Fatal Errors:", errors)
