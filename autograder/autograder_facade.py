import asyncio
import json
import logging
import os
import shutil
import traceback
from time import sleep

from autograder.core.config_processing.criteria_config import CriteriaConfig
from autograder.core.grading.grader import Grader
from autograder.core.grading.scorer import Scorer
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.report.fatal_report import FatalReporter
from autograder.core.report.reporter_factory import Reporter
from autograder.core.test_engine.engine import TestEngine
from autograder.core.utils.upstash_driver import Driver
from connectors.models.autograder_request import AutograderRequest

# --- Setup robust logging ---
# Configure logger to print messages to the console.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class Autograder:
    """
    Autograder class that serves as a facade for the entire autograder system.
    This class will be used by the Adapters to perform the grading process and achieve the final score + feedback.
    TODO: Refactor FACADE to receive an AutograderRequest object as input to the grade() method and handle file positioning internally.
    """

    @staticmethod
    async def connect(autograder_request: AutograderRequest) -> AutograderResponse:
        """
        Main FACADE method that receives the AutograderRequest object, prepares the grading session, performs it, and returns the AutograderResponse.
        Ensures cleanup is always performed, even if an error occurs.
        """
        try:
            logging.info("Connected! Preparing grading session...")
            Autograder.prepare_session(autograder_request.assignment_config, autograder_request.submission_files)
            response = await Autograder.grade(
                autograder_request.assignment_config.test_framework,
                autograder_request.student_name,
                autograder_request.student_credentials,
                autograder_request.feedback_mode,
                autograder_request.openai_key,
                autograder_request.redis_url,
                autograder_request.redis_token
            )
            return response
        except Exception as e:
            # --- Robust Error Handling ---
            # Log the full exception traceback for debugging.
            error_trace = traceback.format_exc()
            logging.error(f"A critical error occurred in the connect method: {e}\n{error_trace}")
            # Generate a fatal error report for the user.
            FatalReporter.report_error(
                "An unexpected error occurred during the grading process. "
                "Please contact support and provide the following details.",
                str(e)
            )
            # Return a structured failure response.
            return Autograder.early_exit()
        finally:
            Autograder.finish_session()

    @staticmethod
    def prepare_session(assignment_config, submission_files):
        """
        Receives all the files needed and places them in the correct directories for the grading job.
        Handles nested directories in filenames and ignores the first (root) directory.
        """
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            validation_path = os.path.join(current_dir, "validation")
            validation_tests_path = os.path.join(validation_path, "__tests__")
            request_bucket_path = os.path.join(current_dir, "request_bucket")
            submission_path = os.path.join(request_bucket_path, "submission")

            logging.info("Building directory structure...")
            os.makedirs(validation_tests_path, exist_ok=True)
            os.makedirs(submission_path, exist_ok=True)
            os.makedirs(os.path.join(validation_tests_path, "results"), exist_ok=True)

            logging.info("Choosing file extension based on test framework...")
            framework = getattr(assignment_config, "test_framework", "pytest")
            ext = ".py" if framework == "pytest" else ".js" if framework == "jest" else ".json" if framework == "ai" else ".txt"

            logging.info("Placing test files...")
            test_files = assignment_config.test_files
            # ... (placing test_base, test_bonus, test_penalty files remains the same)
            if test_files.test_base:
                with open(os.path.join(validation_tests_path, f"test_base{ext}"), "w", encoding="utf-8") as f:
                    logging.info("Writing base test file...")
                    f.write(test_files.test_base)
            if test_files.test_bonus:
                with open(os.path.join(validation_tests_path, f"test_bonus{ext}"), "w", encoding="utf-8") as f:
                    logging.info("Writing bonus test file...")
                    f.write(test_files.test_bonus)
            if test_files.test_penalty:
                with open(os.path.join(validation_tests_path, f"test_penalty{ext}"), "w", encoding="utf-8") as f:
                    logging.info("Writing penalty test file...")
                    f.write(test_files.test_penalty)
            logging.info("Test files placed.")

            for filename, content in test_files.other_files.items():
                # --- MODIFICATION START ---
                # Strip the root folder from the path
                path_parts = filename.split(os.path.sep)
                relative_filename = os.path.join(*path_parts[1:]) if len(path_parts) > 1 else filename

                # Construct the full path using the new relative filename
                full_path = os.path.join(validation_path, relative_filename)
                directory = os.path.dirname(full_path)
                os.makedirs(directory, exist_ok=True)
                # --- MODIFICATION END ---
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)

            logging.info("Placing configuration files...")
            # ... (placing config files remains the same)
            if assignment_config.criteria:
                with open(os.path.join(request_bucket_path, "criteria.json"), "w", encoding="utf-8") as f:
                    json.dump(json.loads(assignment_config.criteria), f, ensure_ascii=False, indent=2)
            if assignment_config.feedback:
                with open(os.path.join(request_bucket_path, "feedback.json"), "w", encoding="utf-8") as f:
                    json.dump(json.loads(assignment_config.feedback), f, ensure_ascii=False, indent=2)
            if assignment_config.ai_feedback:
                with open(os.path.join(request_bucket_path, "ai-feedback.json"), "w", encoding="utf-8") as f:
                    json.dump(json.loads(assignment_config.ai_feedback), f, ensure_ascii=False, indent=2)
            if assignment_config.setup:
                with open(os.path.join(request_bucket_path, "autograder-setup.json"), "w", encoding="utf-8") as f:
                    json.dump(json.loads(assignment_config.setup), f, ensure_ascii=False, indent=2)
            logging.info("Configuration files placed.")

            logging.info("Placing submission files...")
            for filename, content in submission_files.items():
                # --- MODIFICATION START ---
                # Split the path into parts using the OS-specific separator
                path_parts = filename.split(os.path.sep)

                # If there are path parts (i.e., it's in a folder), strip the first one
                # Otherwise (it's just a file), use the original filename
                relative_filename = os.path.join(*path_parts[1:]) if len(path_parts) > 1 else filename

                # Construct the full path using the new relative filename
                full_path = os.path.join(submission_path, relative_filename)
                directory = os.path.dirname(full_path)
                os.makedirs(directory, exist_ok=True)
                # --- MODIFICATION END ---
                with open(full_path, "w", encoding="utf-8") as f:
                    logging.info(f"Writing submission file: {relative_filename}...")
                    f.write(content)
        except (IOError, OSError) as e:
            logging.error(f"Failed to prepare session due to a file system error: {e}")
            raise

    @staticmethod
    def _recreate_directory(directory_path: str):
        """
        Helper method to completely remove a directory and all its contents,
        and then recreate it. This ensures a clean state.
        :param directory_path: The absolute path to the directory to clean.
        """
        logging.info(f"Resetting directory: {directory_path}")
        if os.path.isdir(directory_path):
            try:
                shutil.rmtree(directory_path)
            except Exception as e:
                logging.error(f'Error: Failed to delete directory {directory_path}. Reason: {e}')

        try:
            os.makedirs(directory_path, exist_ok=True)
        except Exception as e:
            logging.error(f'Error: Failed to create directory {directory_path}. Reason: {e}')

    @staticmethod
    def early_exit():
        fatal_report = FatalReporter.generate_feedback()
        return AutograderResponse("Fail", 0.0, fatal_report)

    @staticmethod
    def finish_session():
        """
        This method cleans all previous configurations and files to start a new grading session.
        It cleans the contents of /validation and /request_bucket.
        :return: A new instance of the Autograder.
        """
        logging.info("Finishing session and cleaning up workspace...")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        validation_path = os.path.join(current_dir, "validation")
        request_bucket_path = os.path.join(current_dir, "request_bucket")

        Autograder._recreate_directory(validation_path)
        Autograder._recreate_directory(request_bucket_path)

        validation_results_path = os.path.join(validation_path, "results")
        submission_path = os.path.join(request_bucket_path, "submission")

        os.makedirs(validation_results_path, exist_ok=True)
        os.makedirs(submission_path, exist_ok=True)

        logging.info("Cleanup complete. Ready for a new session.")
        return Autograder()

    @staticmethod
    async def grade(
            test_framework="pytest",
            student_name=None,
            student_credentials=None,
            feedback_type="default",
            openai_key=None,
            redis_url=None,
            redis_token=None
    ):
        """
        Main grading method with robust error handling.
        """
        try:
            await TestEngine.run(test_framework)
            sleep(2)
            if TestEngine.fatal_error:
                return Autograder.early_exit()
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "request_bucket", "criteria.json")
            normalized_path = os.path.normpath(config_path)

            assignment_config = CriteriaConfig.create_config(normalized_path)

            base_grader = Grader.create(assignment_config.base_config)
            bonus_grader = Grader.create(assignment_config.bonus_config)
            penalty_grader = Grader.create(assignment_config.penalty_config)

            result = Scorer.build_and_grade(student_name, assignment_config, base_grader, bonus_grader, penalty_grader)
            logging.info(f"Final Score: {result.final_score}")

            reporter = None
            if feedback_type == "default":
                reporter = Reporter.create_default_reporter(result)
            elif feedback_type == "ai":
                if not openai_key:
                    raise ValueError("OpenAI key is required for AI feedback.")
                if not redis_url or not redis_token:
                    raise ValueError("Redis URL and token are required for AI feedback.")
                driver = Driver.create(redis_token, redis_url)
                if not driver.token_exists(student_credentials):
                    driver.create_token(student_credentials, 10)
                allowed = driver.decrement_token_quota(student_credentials)
                if allowed:
                    quota = driver.get_token_quota(student_credentials)
                    reporter = Reporter.create_ai_reporter(result, openai_key, quota)
            else:
                raise ValueError("Invalid feedback type. Choose 'default' or 'ai'.")

            feedback = reporter.generate_feedback()

            return AutograderResponse("Success", result.final_score, feedback)

        except Exception as e:
            # --- More detailed logging in the `grade` method ---
            error_trace = traceback.format_exc()
            logging.error(f"An error occurred during the grading process: {e}\n{error_trace}")
            # Re-raise to be handled by the main `connect` method's exception handler.
            raise


if __name__ == "__main__":
    from connectors.models.assignment_config import AssignmentConfig
    from connectors.models.autograder_request import AutograderRequest

    opt = int(input("1 - Jest Test\n2 - Pytest\nChoose the test framework to run: "))
    if opt == 1:
        ass = AssignmentConfig.load_preset("html-css-js")
        submission_files = {
            "index.html":
                """<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="style.css">
        </head>
        <body>
            <h1>Welcome to My Page</h1>
            <p>This is a simple webpage.</p>
            <button id="myButton">Click Me!</button>
            <script src="script.js"></script>
        </body>
        </html>""",
            "style.css": """
        body { background-color: lightblue; }
        h1 { color: darkblue; }
            """,
            "script.js":
                """
    document.getElementById("myButton").addEventListener("click", function() {
        this.textContent = "Clicked!";
    });
            """
        }
        request = AutograderRequest({"index.html": submission_files["index.html"]}, ass, "Arthur Carvalho", "123",
                                    "default")


    async def main():
        logging.info("Starting autograder...")
        try:
            response = await Autograder.connect(request)
            logging.info(f"STATUS: {response.status}")
            logging.info(f"Final Score: {response.final_score}")
            logging.info("--- FEEDBACK ---")
            print(response.feedback) # Using print here for clean feedback output
        except Exception as e:
            # This top-level catch is a final safety net.
            logging.critical(f"Autograder run failed catastrophically. Error: {e}")


    asyncio.run(main())