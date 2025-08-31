import logging
from autograder.core.grading.grader import Grader
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.models.feedback_preferences import FeedbackPreferences
from autograder.core.report.reporter_factory import Reporter
from autograder.core.utils.upstash_driver import Driver
from connectors.models.autograder_request import AutograderRequest
from autograder.builder.tree_builder import CriteriaTree
from autograder.builder.template_library.library import TemplateLibrary


from autograder.builder.pre_flight import PreFlight

class Autograder:

    @staticmethod
    def grade(autograder_request: AutograderRequest):
        logger = logging.getLogger(__name__)
        logger.info("Starting autograder process")

        try:
            # Step 1: Handle Pre-flight checks if setup is defined
            if autograder_request.assignment_config.setup:
                logger.info("Running pre-flight setup commands")
                # Assuming PreFlight class exists and has a 'run' method
                impediments = PreFlight.run(autograder_request.assignment_config.setup, autograder_request.submission_files)
                if impediments:
                     error_messages = [impediment['message'] for impediment in impediments]
                     logger.error(f"Pre-flight checks failed with errors: {error_messages}")
                     return AutograderResponse("fail", 0.0, "\n".join(error_messages))
                logger.info("Pre-flight setup completed with no impediments")

            # Step 2: Build criteria tree
            logger.info("Building criteria tree from assignment configuration:")
            logger.debug(f"Criteria configuration: {autograder_request.assignment_config.criteria}")
            criteria_tree = CriteriaTree.build(autograder_request.assignment_config.criteria)
            logger.info("Criteria tree built successfully")

            # Step 3: Get test template
            template_name = autograder_request.assignment_config.template
            logger.info(f"Loading test template: '{template_name}'")
            test_template = TemplateLibrary.get_template(template_name)

            if test_template is None:
                logger.error(f"Template '{template_name}' not found in TemplateLibrary")
                raise ValueError(f"Unsupported template: {template_name}")

            logger.info(f"Test template '{template_name}' loaded successfully")

            # Step 4: Initialize grader
            logger.info("Initializing grader with criteria tree and test template")
            grader = Grader(criteria_tree, test_template)
            logger.debug(f"Grader initialized for student: {autograder_request.student_name}")

            # Step 5: Run grading
            logger.info("Running grading process")
            logger.debug(f"Submission files: {list(autograder_request.submission_files.keys())}")
            result = grader.run(autograder_request.submission_files, autograder_request.student_name)
            logger.info(f"Grading completed. Final score: {result.final_score}")

            # Step 6: Setup feedback preferences
            logger.info("Processing feedback preferences")
            feedback = FeedbackPreferences.from_dict(autograder_request.assignment_config.feedback)
            logger.debug(f"Feedback mode: {autograder_request.feedback_mode}")

            # Step 7: Create reporter based on feedback mode
            reporter = None
            feedback_mode = autograder_request.feedback_mode

            if feedback_mode == "default":
                logger.info("Creating default reporter")
                reporter = Reporter.create_default_reporter(result, feedback)
                logger.info("Default reporter created successfully")

            elif feedback_mode == "ai":
                logger.info("Creating AI reporter")

                # Validate AI requirements
                if not all(
                        [autograder_request.openai_key, autograder_request.redis_url, autograder_request.redis_token]):
                    error_msg = "OpenAI key, Redis URL, and Redis token are required for AI feedback mode."
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                logger.info("All AI requirements validated successfully")

                # Setup Redis driver
                driver = Driver.create(autograder_request.redis_token, autograder_request.redis_url)
                student_credentials = autograder_request.student_credentials

                if not driver.token_exists(student_credentials):
                    driver.create_token(student_credentials)

                if driver.decrement_token_quota(student_credentials):
                    quota = driver.get_token_quota(student_credentials)
                    logger.info(f"Quota check passed. Remaining quota: {quota}")
                    reporter = Reporter.create_ai_reporter(result, feedback, autograder_request.openai_key, quota)
                else:
                    logger.warning("Quota exceeded for student, falling back to default feedback.")
                    reporter = Reporter.create_default_reporter(result, feedback)
            else:
                raise ValueError(f"Unsupported feedback mode: {feedback_mode}")

            # Step 8: Generate feedback
            logger.info("Generating feedback report")
            feedback_report = reporter.generate_feedback()
            logger.info("Feedback report generated successfully")

            # Step 9: Create and return the successful response
            logger.info("Creating successful autograder response")
            response = AutograderResponse("Success", result.final_score, feedback_report)
            logger.info("Autograder process completed successfully")
            return response

        except Exception as e:
            # Catch any exception, log it, and return a failure response
            error_message = f"An unexpected error occurred during the grading process: {str(e)}"
            logger.error(error_message)
            logger.exception("Full exception traceback:")
            return AutograderResponse(status="fail", final_score=0.0, feedback=error_message)