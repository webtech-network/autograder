import logging

from autograder.context import request_context
from autograder.core.grading.grader import Grader
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.models.feedback_preferences import FeedbackPreferences
from autograder.core.report.reporter_factory import Reporter
from autograder.core.utils.upstash_driver import Driver
from connectors.models.assignment_config import AssignmentConfig
from connectors.models.autograder_request import AutograderRequest
from autograder.builder.tree_builder import CriteriaTree
from autograder.builder.template_library.library import TemplateLibrary


from autograder.builder.pre_flight import PreFlight

class Autograder:
    @staticmethod
    def grade(autograder_request: AutograderRequest):
        logger = logging.getLogger(__name__)
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
                logger.info("Running pre-flight setup commands")
                impediments = PreFlight.run()
                if impediments:
                     error_messages = [impediment['message'] for impediment in impediments]
                     logger.error(f"Pre-flight checks failed with errors: {error_messages}")
                     return AutograderResponse("fail", 0.0, "\n".join(error_messages))
                logger.info("Pre-flight setup completed with no impediments")

            # Step 2: Get test template
            template_name = autograder_request.assignment_config.template
            if template_name == "custom":
                logger.info(f"Loading custom test template provided!")
                test_template = TemplateLibrary.get_template(template_name,autograder_request.assignment_config.custom_template_str)
            else:
                logger.info(f"Loading test template: '{template_name}'")
                test_template = TemplateLibrary.get_template(template_name)
            if test_template is None:
                logger.error(f"Template '{template_name}' not found in TemplateLibrary")
                raise ValueError(f"Unsupported template: {template_name}")
            logger.info(f"Test template '{test_template.template_name}' instantiated successfully")

            # Step 3: Build criteria tree
            logger.info("Building criteria tree from assignment configuration:")
            logger.debug(f"Criteria configuration: {autograder_request.assignment_config.criteria}")
            if test_template.requires_pre_executed_tree:
                logger.info("Template requires pre-executed criteria tree.")
                criteria_tree = CriteriaTree.build_pre_executed_tree(test_template)
                criteria_tree.print_pre_executed_tree()
            elif not test_template.requires_pre_executed_tree:
                logger.info("Template does not require pre-executed criteria tree.")
                criteria_tree = CriteriaTree.build_non_executed_tree()
            else:
                error_msg = f"Template '{template_name}' has an invalid 'requires_pre_executed_tree' setting."
                logger.error(error_msg)
                raise ValueError(error_msg)
            test_template.stop()
            criteria_tree.print_pre_executed_tree() # print tree again to show result injection from ai executor
            logger.info("Criteria tree built successfully")


            logger.info(f"Test template '{template_name}' loaded successfully")

            # Step 4: Initialize grader
            logger.info("Initializing grader with criteria tree and test template")
            grader = Grader(criteria_tree, test_template)
            logger.debug(f"Grader initialized for student: {autograder_request.student_name}")

            # Step 5: Run grading
            logger.info("Running grading process")
            logger.debug(f"Submission files: {list(autograder_request.submission_files.keys())}")
            result = grader.run()
            logger.info(f"Grading completed. Final score: {result.final_score}")

            if autograder_request.include_feedback:
                # Step 6: Setup feedback preferences
                logger.info("Processing feedback preferences")
                feedback = FeedbackPreferences.from_dict()
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
                        reporter = Reporter.create_ai_reporter(result,feedback, test_template, quota)
                    else:
                        logger.warning("Quota exceeded for student, falling back to default feedback.")
                        reporter = Reporter.create_default_reporter(result, feedback,test_template)
                else:
                    raise ValueError(f"Unsupported feedback mode: {feedback_mode}")

                # Step 8: Generate feedback
                logger.info("Generating feedback report")
                feedback_report = reporter.generate_feedback()
                logger.info("Feedback report generated successfully")

                # Step 9: Create and return the successful response
                logger.info("Creating successful autograder response")
                response = AutograderResponse("Success", result.final_score, feedback_report,result.get_test_report())
                logger.info("Autograder process completed successfully")
                return response
            else:
                logger.info("Feedback not requested, returning score only")
                return AutograderResponse("Success", result.final_score, feedback="",test_report=result.get_test_report())

        except Exception as e:
            # Catch any exception, log it, and return a failure response
            error_message = f"An unexpected error occurred during the grading process: {str(e)}"
            logger.error(error_message)
            logger.exception("Full exception traceback:")
            return AutograderResponse(status="fail", final_score=0.0, feedback=error_message)

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
            template="web dev"  # Use the web dev template
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