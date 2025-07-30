import asyncio
import os
from autograder.core.config_processing.config import Config
from autograder.core.grading.grader import Grader
from autograder.core.grading.scorer import Scorer
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.report.reporter_factory import Reporter
from autograder.core.test_engine.engine import TestEngine
from autograder.core.utils.upstash_driver import Driver
from time import sleep


class Autograder:
    """
    Autograder class that serves as a facade for the entire autograder system.
    This class will be used by the Adapters to perform the grading process and achieve the final score + feedback.
    """

    @staticmethod
    def _recreate_directory(directory_path: str):
        """
        Helper method to completely remove a directory and all its contents,
        and then recreate it. This ensures a clean state.
        :param directory_path: The absolute path to the directory to clean.
        """
        print(f"Resetting directory: {directory_path}")
        # If the directory exists, remove it completely.
        if os.path.isdir(directory_path):
            try:
                shutil.rmtree(directory_path)
            except Exception as e:
                print(f'Error: Failed to delete directory {directory_path}. Reason: {e}')

        # Recreate the directory.
        '''
        try:
            os.makedirs(directory_path, exist_ok=True)
        except Exception as e:
            print(f'Error: Failed to create directory {directory_path}. Reason: {e}')
            '''

    @staticmethod
    def finish_session():
        """
        This method is used to clean all the previous configurations and start a new grading session.
        :return:
        """
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
        # This will now correctly wait for the async tests to finish
        await TestEngine.run_tests(test_framework)
        sleep(2)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "request_bucket", "criteria.json")
        # Normalize the path to resolve ".." correctly
        normalized_path = os.path.normpath(config_path)
        assignment_config = Config.create_config(normalized_path)

        base_grader = Grader.create(assignment_config.base_config)
        bonus_grader = Grader.create(assignment_config.bonus_config)
        penalty_grader = Grader.create(assignment_config.penalty_config)
        result = Scorer.build_and_grade(student_name, assignment_config, base_grader, bonus_grader, penalty_grader)
        print("Final Score: ", result)
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
        return AutograderResponse(result.final_score, feedback)


# --- FIX IS HERE ---
if __name__ == "__main__":
    """
    This is the entry point for the Autograder. 
    It is used for testing purposes and can be run directly to see the grading process in action.
    """


    # 1. Define an async function to be the entry point
    async def main():
        print("Starting autograder...")
        # 2. Use 'await' to properly call the async 'grade' method
        response = await Autograder.grade(test_framework="pytest", student_name="John Doe", feedback_type="default")
        print(f"Final Score: {response.final_score}")
        print("Feedback:")
        print(response.feedback)


    # 3. Use asyncio.run() to execute the async main function
    asyncio.run(main())