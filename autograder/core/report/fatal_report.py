import os
import json




class FatalReporter:
    """
    This class is responsible for generating a report for fatal errors in the autograder.
    It reads a JSON file containing error details and formats it into a
    user-friendly markdown report.
    """
    # --- Project Directory Setup ---
    # These paths are configured to locate necessary files within the project structure.
    _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE_DIR)))
    VALIDATION_DIR = os.path.join(_PROJECT_ROOT, "autograder",'validation')
    REQUEST_BUCKET_DIR = os.path.join(_PROJECT_ROOT, 'request_bucket')
    RESULTS_DIR = os.path.join(VALIDATION_DIR, 'tests', 'results')

    @staticmethod
    def generate_feedback(report_path=None):
        """
        Generates a markdown feedback report based on fatal error results from a JSON file.

        This method reads a JSON file that details fatal errors encountered by the
        autograder, formats them into a structured and readable markdown report,
        and returns the report as a string.

        Args:
            report_path (str, optional): The full path to the JSON report file.
                                         If None, it defaults to a file named
                                         'fatal_errors.json' in the class's RESULTS_DIR.

        Returns:
            str: A string containing the formatted markdown report.
        """
        # If no specific path is provided, construct the default path
        if report_path is None:
            print(FatalReporter.RESULTS_DIR)
            report_path = os.path.join(FatalReporter.RESULTS_DIR, 'fatal_report.json')

        # --- Read and Validate Report File ---
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            return "## ❌ Error\nCould not find the fatal error report file. Please contact an administrator."
        except json.JSONDecodeError:
            return "## ❌ Error\nCould not parse the fatal error report file due to a syntax error. Please contact an administrator."

        errors = data.get("errors", [])
        if not errors:
            return "## ✅ No Fatal Errors Found\nYour submission passed all initial checks."

        # --- Group Errors for Structured Reporting ---
        grouped_errors = {}
        for error in errors:
            error_type = error.get("type", "unknown_error")
            if error_type not in grouped_errors:
                grouped_errors[error_type] = []
            grouped_errors[error_type].append(error.get("message", "No message provided."))

        # --- Build the Markdown Report ---
        markdown_report = ["# 🚨 Autograder Fatal Error Report\n"]
        markdown_report.append(
            "We're sorry, but the autograder could not run due to the following critical issues with your submission. Please fix them and resubmit.\n")

        # Handle specific, common error types with custom formatting
        if "file_check" in grouped_errors:
            markdown_report.append("---")
            markdown_report.append("## 📁 Missing Files")
            markdown_report.append(
                "The following required files were not found. Please ensure they are named correctly and are located in the root directory of your project.\n")
            for msg in grouped_errors.pop("file_check"):
                # Attempt to extract the filename for cleaner display
                try:
                    filename = msg.split("'")[1]
                    markdown_report.append(f"- ` {filename} `")
                except IndexError:
                    markdown_report.append(f"- {msg}")
            markdown_report.append("\n")

        # Handle any other error types generically
        for error_type, messages in grouped_errors.items():
            markdown_report.append("---")
            heading = error_type.replace('_', ' ').title()
            markdown_report.append(f"## ❗ {heading}")
            for msg in messages:
                markdown_report.append(f"- {msg}")
            markdown_report.append("\n")

        markdown_report.append("---\n")
        markdown_report.append(
            "**Next Steps:** Please review the errors listed above, correct your project files accordingly, and submit your work again.")

        return "\n".join(markdown_report)

    @classmethod
    def create(cls, result):
        """
        This class method would be responsible for creating the initial
        fatal_errors.json file before generate_feedback is called.
        (Implementation is beyond the scope of this example).
        """
        # Example:
        # report_path = os.path.join(cls.RESULTS_DIR, 'fatal_errors.json')
        # with open(report_path, 'w', encoding='utf-8') as f:
        #     json.dump(result, f, indent=2)
        pass

if __name__ == "__main__":
    # Example usage
    report = FatalReporter.generate_feedback()
    print(report)
    # Note: In a real scenario, you would call FatalReporter.create(result) to create the initial report file.
