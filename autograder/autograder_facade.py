import logging

from autograder.builder.models.template import Template
from autograder.context import request_context
from autograder.core.grading.grader import Grader
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.models.feedback_preferences import FeedbackPreferences
from autograder.core.models.result import Result
from autograder.core.report.reporter_factory import Reporter
from autograder.core.utils.upstash_driver import Driver
from connectors.models.assignment_config import AssignmentConfig
from connectors.models.autograder_request import AutograderRequest
from autograder.builder.tree_builder import CriteriaTree
from autograder.builder.template_library.library import TemplateLibrary


from autograder.builder.pre_flight import PreFlight

logger = logging.getLogger(__name__)

class Autograder:

    # Static member that's accessible by all methods
    selected_template : Template = None
    feedback_preferences: FeedbackPreferences = None

    @staticmethod
    def grade(autograder_request: AutograderRequest):
        logger.info("Starting autograder process")

        # Set the request in the global context at the beginning of the process
        request_context.set_request(autograder_request)
        if autograder_request.openai_key:
            logger.info("OpenAI key provided, AI feedback mode may be used")
            logger.info("Setting environment variable for OpenAI key")
            import os
            os.environ["OPENAI_API_KEY"] = autograder_request.openai_key
        try:

            # Step 1: Handle Pre-flight checks if setup is defined
            if autograder_request.assignment_config.setup:
                Autograder._pre_flight_step()

            # Step 2: Get test template
            logger.info("Importing test template")
            Autograder._import_template_step()

            # Step 3: Build criteria tree
            logger.info("Building criteria tree from assignment configuration:")
            Autograder._build_criteria_step()

            # Step 4: Initialize and run grader
            logger.info("Starting grading process")
            result = Autograder._start_and_run_grader()
            logger.info(f"Grading completed. Final score: {result.final_score}")
            
            if autograder_request.redis_token and autograder_request.redis_url:
              Autograder.export_final_score(result.final_score)

            if autograder_request.include_feedback:
                # Step 5: Setup feedback preferences
                logger.info("Processing feedback preferences")
                Autograder._setup_feedback_pref()
                logger.debug(f"Feedback mode: {autograder_request.feedback_mode}")

                # Step 6: Create reporter based on feedback mode
                Autograder.create_feedback_report(result)

                # Step 7: Generate feedback
                logger.info("Generating feedback report")
                feedback_report = Autograder._generate_feedback()
                logger.info("Feedback report generated successfully")


                # Step 8: Create and return the successful response
                logger.info("Creating successful autograder response")
                response = AutograderResponse(
                    status = "Success",
                    final_score = result.final_score,
                    feedback = feedback_report,
                    test_report = result.get_test_report()
                )
                logger.info("Autograder process completed successfully")
                return response
            else:
                logger.info("Feedback not requested, returning score only")
                return AutograderResponse(
                     status="Success",
                     final_score=result.final_score,
                     feedback="",
                     test_report=result.get_test_report()
                )


        except Exception as e:
            # Catch any exception, log it, and return a failure response
            error_message = f"An unexpected error occurred during the grading process: {str(e)}"
            logger.error(error_message)
            logger.exception("Full exception traceback:")
            return AutograderResponse(status="fail", final_score=0.0, feedback=error_message, test_report=[])

    @staticmethod
    def _pre_flight_step():

         if request_context.get_request() and request_context.get_request().assignment_config.setup:
                logger.info("Running pre-flight setup commands")
                impediments = PreFlight.run()
                if impediments:
                     error_messages = [impediment['message'] for impediment in impediments]
                     error_text = "\n".join(error_messages)
                     logger.error(f"Pre-flight checks failed with errors: {error_messages}")
                     raise RuntimeError(error_text)

         logger.info("Pre-flight setup completed with no impediments")



    @staticmethod
    def _import_template_step():
        req = request_context.get_request()
        template_name = req.assignment_config.template
        if template_name == "custom":
            logger.info(f"Loading custom test template provided!")
            test_template = TemplateLibrary.get_template(template_name,req.assignment_config.custom_template_str)
        else:
            logger.info(f"Loading test template: '{template_name}'")
            test_template = TemplateLibrary.get_template(template_name)
        if test_template is None:
            logger.error(f"Template '{template_name}' not found in TemplateLibrary")
            raise ValueError(f"Unsupported template: {template_name}")

        logger.info(f"Test template '{test_template.template_name}' instantiated successfully")
        Autograder.selected_template = test_template


    @staticmethod
    def _build_criteria_step():
        req = request_context.get_request()
        test_template = Autograder.selected_template

        if test_template.requires_pre_executed_tree:
            logger.info("Template requires pre-executed criteria tree.")
            criteria_tree = CriteriaTree.build_pre_executed_tree(test_template)
            criteria_tree.print_pre_executed_tree()
        else:
            logger.info("Template does not require pre-executed criteria tree.")
            criteria_tree = CriteriaTree.build_non_executed_tree()

        test_template.stop()
        criteria_tree.print_pre_executed_tree()
        logger.info("Criteria tree built successfully")

        req.criteria_tree = criteria_tree
        return criteria_tree

    @staticmethod
    def _start_and_run_grader():
        req = request_context.get_request()
        criteria_tree = req.criteria_tree
        test_template = Autograder.selected_template


        logger.info("Initializing grader with criteria tree and test template")
        grader = Grader(criteria_tree, test_template)
        logger.debug(f"Grader initialized for student: {req.student_name}")


        logger.info(f"Running grading process")

        result = grader.run()

        return result

    @staticmethod
    def export_final_score(final_score):
        req = request_context.get_request()
        student_credentials = req.student_credentials
        if req.redis_token and req.redis_url:
            logger.info("Sending final score to Redis")
            driver = Driver.create(req.redis_token, req.redis_url)
            if driver is not None:
                if driver.user_exists(student_credentials):
                    driver.set_score(student_credentials, final_score)
                else:
                    driver.create_user(student_credentials)
                    driver.set_score(student_credentials, final_score)
                logger.info("Final score sent to Redis successfully")

    @staticmethod
    def _setup_feedback_pref():
        feedback = FeedbackPreferences.from_dict()
        Autograder.feedback_preferences = feedback

    @staticmethod
    def create_feedback_report(result: Result):

        req = request_context.get_request()
        template = Autograder.selected_template
        feedback = Autograder.feedback_preferences
        feedback_mode = req.feedback_mode


        if feedback_mode == "default":
            logger.info("Creating default reporter")
            reporter = Reporter.create_default_reporter(result, feedback,template)
            logger.info("Default reporter created successfully")

        elif feedback_mode == "ai":
            logger.info("Creating AI reporter")

            if not all(
                    [req.openai_key,req.redis_url, req.redis_token]):
                error_msg = "OpenAI key, Redis URL, and Redis token are required for AI feedback mode."
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info("All AI requirements validated successfully")

            # Setup Redis driver
            driver = Driver.create(req.redis_token, req.redis_url)
            student_credentials = req.student_credentials


            if not driver.user_exists(student_credentials):
                driver.create_user(student_credentials)

            if driver.decrement_user_quota(student_credentials):
                quota = driver.get_user_quota(student_credentials)
                logger.info(f"Quota check passed. Remaining quota: {quota}")
                reporter = Reporter.create_ai_reporter(result,feedback, template, quota)
            else:
                logger.warning("Quota exceeded for student, falling back to default feedback.")
                reporter = Reporter.create_default_reporter(result, feedback,template)

        else:
                raise ValueError(f"Unsupported feedback mode: {feedback_mode}")

        req.reporter = reporter
        return reporter

    @staticmethod
    def _generate_feedback():
        req = request_context.get_request()
        reporter = req.reporter
        feedback_report = reporter.generate_feedback()
        req.feedback_report = feedback_report
        return feedback_report



if __name__ == "__main__":
    if __name__ == "__main__":
        logging.basicConfig(level=logging.INFO)

        # 1. Define submission files for web dev
        submission_files = {
            "index.html": """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
        <header>
            <h1>Welcome</h1>
        </header>
        <main>
            <p>This is a paragraph.</p>
            <img src="image.jpg" alt="A descriptive alt text">
        </main>
        <footer>
            <p>&copy; 2025</p>
        </footer>
    </body>
    </html>
            """,
            "style.css": """
    body {
        font-family: sans-serif;
        margin: 20px;
    }
    header {
        background-color: #f0f0f0;
        padding: 1em;
    }
            """
        }

        # 2. Define criteria_json for web dev
        criteria_json = {
            "test_library": "web_dev",  # Match the template name
            "base": {
                "weight": 100,
                "subjects": {
                    "html_structure": {
                        "weight": 70,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "has_tag",
                                "calls": [
                                    ["head", 1],
                                    ["body", 1],
                                    ["header", 1],
                                    ["main", 1],
                                    ["footer", 1]
                                ]
                            },
                            {
                                "file": "index.html",
                                "name": "check_css_linked"
                            }
                        ]
                    },
                    "accessibility": {
                        "weight": 30,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "check_all_images_have_alt"
                            }
                        ]
                    }
                }
            },
            "bonus": {
                "weight": 20,  # Example bonus weight
                "subjects": {
                    "best_practices": {
                        "weight": 100,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "uses_semantic_tags"
                            }
                        ]
                    }
                }
            },
            "penalty": {
                "weight": 10,  # Example penalty weight
                "subjects": {
                    "bad_practices": {
                        "weight": 100,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "check_no_inline_styles"
                            }
                        ]
                    }
                }
            }
        }

        # 3. Define feedback_json (can be simple or complex)
        feedback_json = {
            "general": {
                "report_title": "Web Dev Assignment Report",
                "show_score": True
            },
            "default": {
                "category_headers": {
                    "base": "✅ Core HTML/CSS",
                    "bonus": "⭐ Best Practices Bonus",
                    "penalty": "🚨 Points Deducted"
                }
            }
        }

        # 4. Define setup_json with file checks
        setup_json = {
            "file_checks": [
                "index.html",
                "style.css"
            ],
            "commands": []  # No commands needed for static web dev
        }

        # 5. Create AssignmentConfig using the web dev template
        config = AssignmentConfig(
            criteria=criteria_json,
            feedback=feedback_json,
            setup=setup_json,
            template="webdev"  # Use the web dev template
        )

        # 6. Create AutograderRequest
        request = AutograderRequest(
            submission_files=submission_files,
            assignment_config=config,
            student_name="Local Tester",
            student_credentials="local_tester_01",  # Credentials for local testing
            include_feedback=True,  # Request feedback
            feedback_mode="default"  # Use default feedback for simplicity
        )

        # 7. Run the grading process
        logger = logging.getLogger(__name__)
        logger.info("--- Running Local Web Dev Test ---")
        facade_response = Autograder.grade(request)

        # 8. Print the results
        logger.info("--- Grading Complete ---")
        print(f"Status: {facade_response.status}")
        print(f"Final Score: {facade_response.final_score}")
        print("\n--- Feedback ---")
        print(facade_response.feedback)
        print("\n--- Test Report ---")
        if facade_response.test_report:
            for test in facade_response.test_report:
                print(f"- {test.subject_name}: {test.test_name} -> Score: {test.score}, Report: {test.report}")
        else:
            print("No test report generated.")
