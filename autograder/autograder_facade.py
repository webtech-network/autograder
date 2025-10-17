"""
Autograder Facade Module.

This module provides the main entry point for the autograding system through
the Autograder class. It orchestrates the entire grading pipeline from setup
through execution to feedback generation.

Architecture:
    This facade implements the core business logic of the autograder,
    coordinating between the builder (criteria tree construction), executor
    (test running), and reporter (feedback generation) components.

Typical Usage:
    request = AutograderRequest(...)
    response = Autograder.grade(request)
"""

import logging

from autograder.builder.pre_flight import PreFlight
from autograder.builder.template_library.library import TemplateLibrary
from autograder.builder.tree_builder import CriteriaTree
from autograder.context import request_context
from autograder.core.grading.grader import Grader
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.models.feedback_preferences import FeedbackPreferences
from autograder.core.report.reporter_factory import Reporter
from autograder.core.utils.upstash_driver import Driver
from connectors.models.assignment_config import AssignmentConfig
from connectors.models.autograder_request import AutograderRequest


class Autograder:
    """
    Main facade for the autograding system.

    This class provides a single, simplified interface to the complex autograding
    subsystem. It follows the Facade design pattern to hide the complexity of
    the criteria tree building, test execution, and feedback generation.

    The grading process follows these steps:
        1. Pre-flight setup (install dependencies, prepare environment)
        2. Template loading (get test definitions)
        3. Criteria tree building (structure the grading rubric)
        4. Test execution (run all tests and collect results)
        5. Score calculation (compute weighted final score)
        6. Feedback generation (create student-facing report)

    Note:
        This class is stateless and uses static methods. All state is managed
        through the request_context singleton.
    """

    @staticmethod
    def grade(autograder_request: AutograderRequest):
        """
        Execute the complete autograding pipeline for a student submission.

        This is the main entry point for grading. It processes a student's submission
        through the entire grading pipeline, from environment setup to final feedback
        generation.

        Args:
            autograder_request (AutograderRequest): Complete request object containing:
                - submission_files: Dict of filename -> file content
                - assignment_config: Grading criteria and configuration
                - student_name: Student identifier
                - feedback_mode: "default" or "AI" for feedback generation
                - openai_key: Optional API key for AI feedback
                - redis_url/token: Optional caching configuration

        Returns:
            AutograderResponse: Contains:
                - status: "pass" or "fail"
                - final_score: Numerical score (0-100)
                - feedback: Generated feedback message

        Raises:
            ValueError: If template is not found or configuration is invalid
            Exception: If pre-flight checks fail or grading encounters errors

        Pipeline Stages:
            1. Pre-flight: Run setup commands (npm install, pip install, etc.)
            2. Template Loading: Load test definitions for assignment type
            3. Tree Building: Construct criteria tree from configuration
            4. Test Execution: Run all tests and collect results
            5. Score Calculation: Compute weighted scores across categories
            6. Feedback Generation: Create student-facing report (default or AI)

        Example:
            >>> request = AutograderRequest(
            ...     submission_files={"app.py": "print('hello')"},
            ...     assignment_config=config,
            ...     student_name="Alice"
            ... )
            >>> response = Autograder.grade(request)
            >>> print(f"Score: {response.final_score}")
        """
        logger = logging.getLogger(__name__)
        logger.info("Starting autograder process")

        # Set the request in the global context at the beginning
        # This makes the request available to all components without
        # passing it explicitly
        request_context.set_request(autograder_request)

        # Configure OpenAI API if key is provided for AI-powered feedback
        if autograder_request.openai_key:
            msg = "OpenAI key provided, AI feedback mode may be used"
            logger.info(msg)
            logger.info("Setting environment variable for OpenAI key")
            import os

            os.environ["OPENAI_API_KEY"] = autograder_request.openai_key

        try:
            # ========== STEP 1: PRE-FLIGHT SETUP ==========
            # Run setup commands (e.g., npm install, pip install) if defined
            # This prepares the environment before running tests
            if autograder_request.assignment_config.setup:
                logger.info("Running pre-flight setup commands")
                impediments = PreFlight.run()

                # If setup fails, return immediately with error response
                if impediments:
                    error_messages = [
                        impediment["message"] for impediment in impediments
                    ]
                    logger.error(
                        f"Pre-flight checks failed with errors: {error_messages}"
                    )
                    return AutograderResponse("fail", 0.0, "\n".join(error_messages))
                logger.info("Pre-flight setup completed with no impediments")

            # ========== STEP 2: LOAD TEST TEMPLATE ==========
            # Templates define how to run tests for specific assignment types
            # (e.g., web development, Python scripts, API testing)
            template_name = autograder_request.assignment_config.template

            if template_name == "custom":
                # Load custom template provided by instructor
                logger.info("Loading custom test template provided!")
                test_template = TemplateLibrary.get_template(
                    template_name,
                    autograder_request.assignment_config.custom_template_str,
                )
            else:
                # Load built-in template from library
                logger.info(f"Loading test template: '{template_name}'")
                test_template = TemplateLibrary.get_template(template_name)

            # Validate template was found
            if test_template is None:
                msg = f"Template '{template_name}' not found in " "TemplateLibrary"
                logger.error(msg)
                raise ValueError(f"Unsupported template: {template_name}")
            msg = (
                f"Test template '{test_template.template_name}' "
                "instantiated successfully"
            )
            logger.info(msg)

            # ========== STEP 3: BUILD CRITERIA TREE ==========
            # The criteria tree structures the grading rubric hierarchically
            # It organizes tests into categories (base, bonus, penalty) and subjects
            logger.info("Building criteria tree from assignment configuration:")
            criteria_config = autograder_request.assignment_config.criteria
            logger.debug(f"Criteria configuration: {criteria_config}")

            # Choose tree building strategy based on template requirements
            if test_template.requires_pre_executed_tree:
                # Pre-executed tree: Run tests during tree construction
                # Use this for templates that need test results before grading
                logger.info("Template requires pre-executed criteria tree.")
                criteria_tree = CriteriaTree.build_pre_executed_tree(test_template)
                criteria_tree.print_pre_executed_tree()

            elif not test_template.requires_pre_executed_tree:
                # Non-executed tree: Build structure first, execute tests later
                # Use this for standard templates
                msg = "Template does not require pre-executed criteria tree."
                logger.info(msg)
                criteria_tree = CriteriaTree.build_non_executed_tree()

            else:
                # Invalid configuration
                error_msg = (
                    f"Template '{template_name}' has an invalid "
                    f"'requires_pre_executed_tree' setting."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Stop template execution (cleanup any running processes)
            test_template.stop()

            # Print tree to show test results (if pre-executed with AI)
            criteria_tree.print_pre_executed_tree()
            logger.info("Criteria tree built successfully")

            logger.info(f"Test template '{template_name}' loaded successfully")

            # Step 4: Initialize grader
            logger.info("Initializing grader with criteria tree and test template")
            grader = Grader(criteria_tree, test_template)
            logger.debug(
                f"Grader initialized for student: {autograder_request.student_name}"
            )

            # Step 5: Run grading
            logger.info("Running grading process")
            logger.debug(
                f"Submission files: {list(autograder_request.submission_files.keys())}"
            )
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
                    reporter = Reporter.create_default_reporter(
                        result, feedback, test_template
                    )
                    logger.info("Default reporter created successfully")

                elif feedback_mode == "ai":
                    logger.info("Creating AI reporter")

                    # Validate AI requirements
                    if not all(
                        [
                            autograder_request.openai_key,
                            autograder_request.redis_url,
                            autograder_request.redis_token,
                        ]
                    ):
                        error_msg = (
                            "OpenAI key, Redis URL, and Redis token are "
                            "required for AI feedback mode."
                        )
                        logger.error(error_msg)
                        raise ValueError(error_msg)

                    logger.info("All AI requirements validated successfully")

                    # Setup Redis driver
                    driver = Driver.create(
                        autograder_request.redis_token, autograder_request.redis_url
                    )
                    student_credentials = autograder_request.student_credentials

                    if not driver.token_exists(student_credentials):
                        driver.create_token(student_credentials)

                    if driver.decrement_token_quota(student_credentials):
                        quota = driver.get_token_quota(student_credentials)
                        msg = f"Quota check passed. Remaining quota: {quota}"
                        logger.info(msg)
                        reporter = Reporter.create_ai_reporter(
                            result, feedback, test_template, quota
                        )
                    else:
                        msg = (
                            "Quota exceeded for student, "
                            "falling back to default feedback."
                        )
                        logger.warning(msg)
                        reporter = Reporter.create_default_reporter(
                            result, feedback, test_template
                        )
                else:
                    raise ValueError(f"Unsupported feedback mode: {feedback_mode}")

                # Step 8: Generate feedback
                logger.info("Generating feedback report")
                feedback_report = reporter.generate_feedback()
                logger.info("Feedback report generated successfully")

                # Step 9: Create and return the successful response
                logger.info("Creating successful autograder response")
                response = AutograderResponse(
                    "Success",
                    result.final_score,
                    feedback_report,
                    result.get_test_report(),
                )
                logger.info("Autograder process completed successfully")
                return response
            else:
                logger.info("Feedback not requested, returning score only")
                return AutograderResponse(
                    "Success",
                    result.final_score,
                    feedback="",
                    test_report=result.get_test_report(),
                )

        except Exception as e:
            # Catch any exception, log it, and return a failure response
            error_message = (
                f"An unexpected error occurred during the grading process: {str(e)}"
            )
            logger.error(error_message)
            logger.exception("Full exception traceback:")
            return AutograderResponse(
                status="fail", final_score=0.0, feedback=error_message
            )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Example usage (this would normally come from an external request)
    criteria_json = {
        "test_library": "essay ai grader",
        "base": {
            "weight": 100,
            "subjects": {
                "foundations": {
                    "weight": 60,
                    "tests": [
                        {"name": "thesis_statement"},
                        {"name": "clarity_and_cohesion"},
                        {"name": "grammar_and_spelling"},
                    ],
                },
                "prompt_adherence": {
                    "weight": 40,
                    "tests": [
                        {
                            "name": "adherence_to_prompt",
                            "calls": [
                                [
                                    "Analyze the primary causes of the "
                                    "Industrial Revolution and its impact "
                                    "on 19th-century society."
                                ]
                            ],
                        }
                    ],
                },
            },
        },
        "bonus": {
            "weight": 30,
            "subjects": {
                "rhetorical_skill": {
                    "weight": 70,
                    "tests": [
                        {"name": "counterargument_handling"},
                        {"name": "vocabulary_and_diction"},
                        {"name": "sentence_structure_variety"},
                    ],
                },
                "deeper_analysis": {
                    "weight": 30,
                    "tests": [
                        {
                            "name": "topic_connection",
                            "calls": [
                                ["technological innovation", "social inequality"]
                            ],
                        }
                    ],
                },
            },
        },
        "penalty": {
            "weight": 25,
            "subjects": {
                "logical_integrity": {
                    "weight": 100,
                    "tests": [
                        {"name": "logical_fallacy_check"},
                        {"name": "bias_detection"},
                        {"name": "originality_and_plagiarism"},
                    ],
                }
            },
        },
    }
    submission_files = {
        "essay.txt": (
            "Artificial intelligence (AI) is no longer a concept confined to "
            "science fiction; it is a transformative force actively reshaping "
            "industries and redefining the nature of work. Its integration "
            "into the modern workforce presents a profound duality: on one "
            "hand, it offers unprecedented opportunities for productivity and "
            "innovation, while on the other, it poses significant challenges "
            "related to job displacement and economic inequality. Navigating "
            "this transition successfully requires a proactive and nuanced "
            "approach from policymakers, businesses, and individuals alike.\n"
            "The primary benefit of AI in the workplace is its capacity to "
            "augment human potential and drive efficiency. AI-powered systems "
            "can analyze vast datasets in seconds, automating routine "
            "cognitive and manual tasks, which frees human workers to focus "
            "on more complex, creative, and strategic endeavors. For "
            "instance, in medicine, AI algorithms assist radiologists in "
            "detecting tumors with greater accuracy, while in finance, they "
            "identify fraudulent transactions far more effectively than any "
            "human team. This collaboration between human and machine not "
            "only boosts output but also creates new roles centered around AI "
            "development, ethics, and system maintenance—jobs that did not "
            "exist a decade ago.\n"
            "However, this technological advancement casts a significant "
            "shadow of disruption. The same automation that drives efficiency "
            "also leads to job displacement, particularly for roles "
            "characterized by repetitive tasks. Assembly line workers, data "
            "entry clerks, and even some paralegal roles face a high risk of "
            "obsolescence. This creates a widening skills gap, where demand "
            "for high-level technical skills soars while demand for "
            "traditional skills plummets. Without robust mechanisms for "
            "reskilling and upskilling the existing workforce, this gap "
            "threatens to exacerbate socio-economic inequality, creating a "
            "divide between those who can command AI and those who are "
            "displaced by it. There are many gramatical errors in this "
            "sentence, for testing purposes.\n"
            "The most critical challenge, therefore, is not to halt "
            "technological progress but to manage its societal impact. A "
            "multi-pronged strategy is essential. Governments and educational "
            "institutions must collaborate to reform curricula, emphasizing "
            "critical thinking, digital literacy, and lifelong learning. "
            "Furthermore, corporations have a responsibility to invest in "
            "their employees through continuous training programs. Finally, "
            "strengthening social safety nets, perhaps through concepts like "
            "Universal Basic Income (UBI) or enhanced unemployment benefits, "
            "may be necessary to support individuals as they navigate this "
            "volatile transition period.\n"
            "In conclusion, AI is a double-edged sword. Its potential to "
            "enhance productivity and create new avenues for growth is "
            "undeniable, but so are the risks of displacement and inequality. "
            "The future of work will not be a battle of humans versus "
            "machines, but rather a story of adaptation. By investing in "
            "education, promoting equitable policies, and fostering a culture "
            "of continuous learning, we can harness the power of AI to build "
            "a more prosperous and inclusive workforce for all."
        )
    }

    feedback_json = {
        "test_library": "essay",
        "base": {
            "weight": 100,
            "subjects": {
                "semana_5": {
                    "weight": 40,
                    "subjects": {
                        "html": {
                            "weight": 60,
                            "subjects": {
                                "structure": {
                                    "weight": 40,
                                    "tests": [
                                        {
                                            "file": "index.html",
                                            "name": "has_tag",
                                            "calls": [
                                                ["body", 1],
                                                ["header", 1],
                                                ["nav", 1],
                                                ["main", 1],
                                                ["article", 4],
                                                ["img", 5],
                                                ["footer", 1],
                                                ["div", 1],
                                                ["form", 1],
                                                ["input", 1],
                                                ["button", 1],
                                            ],
                                        },
                                        {
                                            "file": "index.html",
                                            "name": "has_attribute",
                                            "calls": [["class", 2]],
                                        },
                                    ],
                                },
                                "link": {
                                    "weight": 20,
                                    "tests": [
                                        {
                                            "file": "index.html",
                                            "name": "check_css_linked",
                                        },
                                        {
                                            "file": "index.html",
                                            "name": "check_internal_links_to_article",
                                            "calls": [[4]],
                                        },
                                    ],
                                },
                            },
                        },
                        "css": {
                            "weight": 40,
                            "subjects": {
                                "responsivity": {
                                    "weight": 50,
                                    "tests": [
                                        {
                                            "file": "css/styles.css",
                                            "name": "uses_relative_units",
                                        },
                                        {
                                            "file": "css/styles.css",
                                            "name": "check_media_queries",
                                        },
                                        {
                                            "file": "css/styles.css",
                                            "name": "check_flexbox_usage",
                                        },
                                    ],
                                },
                                "style": {
                                    "weight": 50,
                                    "tests": [
                                        {
                                            "file": "css/styles.css",
                                            "name": "has_style",
                                            "calls": [
                                                ["font-size", 1],
                                                ["font-family", 1],
                                                ["text-align", 1],
                                                ["display", 1],
                                                ["position", 1],
                                                ["margin", 1],
                                                ["padding", 1],
                                            ],
                                        }
                                    ],
                                },
                            },
                        },
                    },
                },
                "semana_6": {
                    "weight": 60,
                    "subjects": {
                        "bootstrap_fundamentals": {
                            "weight": 70,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "check_bootstrap_linked",
                                },
                                {
                                    "file": "index.html",
                                    "name": "check_internal_links",
                                    "calls": [[3]],
                                },
                                {
                                    "file": "index.html",
                                    "name": "has_class",
                                    "calls": [
                                        [["container", "container-fluid"], 1],
                                        [["row"], 1],
                                        [["col-*"], 3],
                                        [["text-center"], 1],
                                        [["d-flex", "d-*-flex"], 1],
                                        [["bg-*"], 1],
                                    ],
                                },
                            ],
                        },
                        "css_and_docs": {
                            "weight": 30,
                            "tests": [
                                {
                                    "file": "css/styles.css",
                                    "name": "check_media_queries",
                                },
                                {
                                    "file": "css/styles.css",
                                    "name": "has_style",
                                    "calls": [
                                        ["margin", 1],
                                        ["padding", 1],
                                        ["width", 1],
                                    ],
                                },
                                {
                                    "file": "all",
                                    "name": "check_project_structure",
                                    "calls": [["README.md"]],
                                },
                            ],
                        },
                    },
                },
            },
        },
        "bonus": {
            "weight": 40,
            "subjects": {
                "semana_5": {
                    "weight": 40,
                    "subjects": {
                        "accessibility": {
                            "weight": 20,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "check_all_images_have_alt",
                                }
                            ],
                        },
                        "head_detail": {
                            "weight": 80,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "check_head_details",
                                    "calls": [["title"], ["meta"]],
                                },
                                {
                                    "file": "index.html",
                                    "name": "check_attribute_and_value",
                                    "calls": [
                                        ["meta", "charset", "UTF-8"],
                                        ["meta", "name", "viewport"],
                                        ["meta", "name", "description"],
                                        ["meta", "name", "author"],
                                        ["meta", "name", "keywords"],
                                    ],
                                },
                            ],
                        },
                    },
                },
                "semana_6": {
                    "weight": 60,
                    "subjects": {
                        "bootstrap_components": {
                            "weight": 60,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "has_class",
                                    "calls": [
                                        [["card"], 1],
                                        [["card-body"], 1],
                                        [["card-title"], 1],
                                        [["navbar"], 1],
                                        [["navbar-nav"], 1],
                                        [["breadcrumb"], 1],
                                        [["breadcrumb-item"], 1],
                                        [["carousel"], 1],
                                        [["slide"], 1],
                                        [["carousel-item"], 1],
                                    ],
                                }
                            ],
                        },
                        "formatting_classes": {
                            "weight": 40,
                            "tests": [
                                {
                                    "file": "index.html",
                                    "name": "has_class",
                                    "calls": [
                                        [
                                            [
                                                "mt-*",
                                                "ms-*",
                                                "me-*",
                                                "mb-*",
                                                "pt-*",
                                                "ps-*",
                                                "pe-*",
                                                "pb-*",
                                                "gap-*",
                                            ],
                                            8,
                                        ]
                                    ],
                                },
                                {
                                    "file": "index.html",
                                    "name": "has_class",
                                    "calls": [
                                        [["w-*", "mh-*", "mw-*", "vw-*", "vh-*"], 4]
                                    ],
                                },
                            ],
                        },
                    },
                },
            },
        },
        "penalty": {
            "weight": 50,
            "subjects": {
                "semana_5": {
                    "weight": 40,
                    "subjects": {
                        "html": {
                            "weight": 50,
                            "tests": [
                                {"file": "index.html", "name": "check_bootstrap_usage"},
                                {
                                    "file": "css/styles.css",
                                    "name": "check_id_selector_over_usage",
                                    "calls": [[2]],
                                },
                                {
                                    "file": "index.html",
                                    "name": "has_tag",
                                    "calls": [["script", 1]],
                                },
                                {
                                    "file": "index.html",
                                    "name": "check_html_direct_children",
                                },
                                {
                                    "file": "index.html",
                                    "name": "check_tag_not_inside",
                                    "calls": [["header", "main"], ["footer", "main"]],
                                },
                            ],
                        },
                        "project_structure": {
                            "weight": 50,
                            "tests": [
                                {
                                    "file": "all",
                                    "name": "check_dir_exists",
                                    "calls": [["css"], ["imgs"]],
                                },
                                {
                                    "file": "all",
                                    "name": "check_project_structure",
                                    "calls": [["css/styles.css"]],
                                },
                            ],
                        },
                    },
                }
            },
        },
    }
    config = AssignmentConfig(
        criteria_json, feedback_json, setup=None, template="essay"
    )
    request = AutograderRequest(submission_files, config, "Arthur", "123", "default")
    facade = Autograder.grade(request)
    print(facade.feedback)
