from autograder.core.config_processing.config import Config
from autograder.core.grading.grader import Grader
from autograder.core.grading.scorer import Scorer
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.report.reporter_factory import Reporter
from autograder.core.test_engine.engine import TestEngine
from autograder.core.utils.upstash_driver import Driver

class Autograder:
    """
    Autograder class that serves as a facade for the entire autograder system.
    This class will be used by the Adapters to perform the grading process and achieve the final score + feedback.
    """
    @staticmethod
    def grade(
            test_framework = "pytest",
            student_name = None,
            student_credentials=None,
            feedback_type="default",
            openai_key=None,
            redis_url=None,
            redis_token=None
                            ):
        TestEngine.run_tests(test_framework)
        assignment_config = Config.create_config("/request_bucket/criteria.json") #TODO: add error handling for file not found
        base_grader = Grader.create(assignment_config.base_config)
        bonus_grader = Grader.create(assignment_config.bonus_config)
        penalty_grader = Grader.create(assignment_config.penalty_config)
        result = Scorer.build_and_grade(student_name, assignment_config, base_grader, bonus_grader, penalty_grader)
        if feedback_type == "default":
            reporter = Reporter.create_default_reporter(result)
        elif feedback_type == "ai":
            if not openai_key:
                raise ValueError("OpenAI key is required for AI feedback.")
            if not redis_url or not redis_token:
                raise ValueError("Redis URL and token are required for AI feedback.")
            driver = Driver.create(redis_token,redis_url)
            if not driver.token_exists(student_credentials): # In Github Adapter, student_credentials is the author
                driver.create_token(student_credentials,10) #TODO: allow to set the quota from the config file
            allowed = driver.decrement_token_quota(student_credentials)
            if allowed:
                quota = driver.get_token_quota(student_credentials)
                reporter = Reporter.create_ai_reporter(result, openai_key,quota)
        else:
            raise ValueError("Invalid feedback type. Choose 'default' or 'ai'.")
        feedback = reporter.generate_feedback()
        return AutograderResponse(result.final_score, feedback)

