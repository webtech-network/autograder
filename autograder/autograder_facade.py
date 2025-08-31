import logging
from autograder.core.grading.grader import Grader
from autograder.core.models.autograder_response import AutograderResponse
from autograder.core.models.feedback_preferences import FeedbackPreferences
from autograder.core.report.reporter_factory import Reporter
from autograder.core.utils.upstash_driver import Driver
from connectors.models.assignment_config import AssignmentConfig
from connectors.models.autograder_request import AutograderRequest
from autograder.builder.tree_builder import CriteriaTree
from autograder.builder.template_library.library import TemplateLibrary


class Autograder:

    @staticmethod
    def grade(autograder_request: AutograderRequest):
        logger = logging.getLogger(__name__)
        logger.info("Starting autograder process")

        try:
            # Step 1: Build criteria tree
            print(autograder_request.assignment_config.criteria)

            logger.info("Building criteria tree from assignment configuration:")
            print(autograder_request.assignment_config.criteria)
            logger.debug(f"Criteria configuration: {autograder_request.assignment_config.criteria}")
            criteria_tree = CriteriaTree.build(autograder_request.assignment_config.criteria)
            logger.info("Criteria tree built successfully")

            # Step 2: Get test template
            template_name = autograder_request.assignment_config.template
            logger.info(f"Loading test template: '{template_name}'")
            test_template = TemplateLibrary.get_template(template_name)

            if test_template is None:
                logger.error(f"Template '{template_name}' not found in TemplateLibrary")
                raise ValueError(f"Unsupported template: {template_name}")

            logger.info(f"Test template '{template_name}' loaded successfully")

            # Step 3: Initialize grader
            logger.info("Initializing grader with criteria tree and test template")
            grader = Grader(criteria_tree, test_template)
            logger.debug(f"Grader initialized for student: {autograder_request.student_name}")

            # Step 4: Run grading
            logger.info("Running grading process")
            logger.debug(f"Submission files: {list(autograder_request.submission_files.keys())}")
            result = grader.run(autograder_request.submission_files, autograder_request.student_name)
            logger.info(f"Grading completed. Final score: {result.final_score}")

            # Step 5: Setup feedback preferences
            logger.info("Processing feedback preferences")
            feedback = FeedbackPreferences.from_dict(autograder_request.assignment_config.feedback)
            logger.debug(f"Feedback mode: {autograder_request.feedback_mode}")

            # Step 6: Create reporter based on feedback mode
            reporter = None
            feedback_mode = autograder_request.feedback_mode

            if feedback_mode == "default":
                logger.info("Creating default reporter")
                reporter = Reporter.create_default_reporter(result, feedback)
                logger.info("Default reporter created successfully")

            elif feedback_mode == "ai":
                logger.info("Creating AI reporter")

                # Validate AI requirements
                if not autograder_request.openai_key:
                    logger.error("OpenAI key is required for AI feedback mode but not provided")
                    raise ValueError("OpenAI key is required for AI feedback mode.")

                if not autograder_request.redis_url:
                    logger.error("Redis URL is required for AI feedback mode but not provided")
                    raise ValueError("Redis URL is required for AI feedback mode.")

                if not autograder_request.redis_token:
                    logger.error("Redis token is required for AI feedback mode but not provided")
                    raise ValueError("Redis token is required for AI feedback mode.")

                logger.info("All AI requirements validated successfully")

                # Setup Redis driver
                logger.info("Creating Redis driver connection")
                driver = Driver.create(autograder_request.redis_token, autograder_request.redis_url)
                logger.info("Redis driver created successfully")

                # Check and create token if needed
                student_credentials = autograder_request.student_credentials
                logger.info(f"Checking token existence for student: {student_credentials}")

                if not driver.token_exists(student_credentials):
                    logger.info("Token not found, creating new token for student")
                    driver.create_token(student_credentials)
                    logger.info("New token created successfully")
                else:
                    logger.info("Token already exists for student")

                # Check quota and decrement
                logger.info("Checking and decrementing token quota")
                allowed = driver.decrement_token_quota(student_credentials)

                if allowed:
                    quota = driver.get_quota(student_credentials)
                    logger.info(f"Quota check passed. Remaining quota: {quota}")
                    logger.info("Creating AI reporter")
                    reporter = Reporter.create_ai_reporter(result, autograder_request.openai_key, quota)
                    logger.info("AI reporter created successfully")
                else:
                    logger.warning("Quota exceeded for student, proceeding without AI feedback")
                    # You might want to handle this case differently
                    reporter = Reporter.create_default_reporter(result, feedback)
                    logger.info("Fallback to default reporter due to quota limits")

            else:
                logger.error(f"Unsupported feedback mode: {feedback_mode}")
                raise ValueError(f"Unsupported feedback mode: {feedback_mode}")

            # Step 7: Generate feedback
            logger.info("Generating feedback report")
            feedback_report = reporter.generate_feedback()
            logger.info("Feedback report generated successfully")
            logger.debug(f"Feedback report length: {len(feedback_report)} characters")

            # Step 8: Create response
            logger.info("Creating autograder response")
            response = AutograderResponse("Success", result.final_score, feedback_report)
            logger.info("Autograder process completed successfully")
            logger.info(f"Final response - Status: {response.status}, Score: {response.final_score}")

            return response

        except Exception as e:
            logger.error(f"Error during autograder process: {str(e)}")
            logger.exception("Full exception traceback:")
            raise


# Example usage:
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('autograder.log')
        ]
    )

    # Create a mock AutograderRequest object
    criteria_json = {
        "base": {
            "subjects": {
                "html": {
                    "weight": 100,
                    "tests": [
                        {"has_tag": [["div", 50], ["span", 10], ["h1", 10], ["h2", 10], ["h3", 10], ["p", 10]]},
                        {"has_attribute": [["class", 20], ["id", 20], ["src", 20], ["href", 20], ["alt", 20]]},
                        {"has_structure": ["header", "nav", "main", "section", "article", "footer"]},
                        "check_no_unclosed_tags",
                        "check_no_inline_styles",
                        "check_css_linked"
                    ]
                },
                "css": {
                    "weight": 0
                },
                "javascript": {
                    "weight": 0
                }
            }
        },
        "bonus": {
            "weight": 40,
            "subjects": {
                "accessibility": {
                    "weight": 15,
                    "tests": [
                        {"has_attribute": [["aria-label", 10], ["role", 5], ["tabindex", 5]]},
                        "check_headings_sequential",
                        "check_all_images_have_alt"
                    ]
                },
                "advanced_features": {
                    "weight": 10,
                    "tests": [
                        {"css_uses_property": [["display", "grid"], ["--*", "css-variable"]]},
                        {"js_uses_feature": ["arrow_function", "template_literal", "let_const"]}
                    ]
                },
                "responsiveness": {
                    "weight": 5,
                    "tests": [
                        "check_has_media_queries",
                        "check_viewport_meta_tag"
                    ]
                }
            }
        },
        "penalty": {
            "weight": 20,
            "subjects": {
                "html_validation": {
                    "weight": 10,
                    "tests": [
                        {"has_deprecated_tag": [["font", 5], ["center", 5], ["marquee", 10]]}
                    ]
                },
                "css_malpractice": {
                    "weight": 10,
                    "tests": [
                        {"count_usage": [["!important", 5]]}
                    ]
                },
                "js_malpractice": {
                    "weight": 15,
                    "tests": [
                        {"uses_forbidden_method": [["eval", 50], ["document.write", 20]]},
                        {"count_global_vars": [5]}
                    ]
                }
            }
        }
    }

    submission_files = {
        "index.html": """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Página de Teste</title>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>

        <header>
            <h1>Bem-vindo à Página de Teste</h1>
            <h3>Sub-cabeçalho H3</h3> </header>

        <main id="main-content">
            <p class="intro">Este é um parágrafo de introdução para testar o sistema.</p>

            <img src="image1.jpg" alt="Descrição da imagem 1">
            <img src="image2.jpg"> <div>
                <p>Este é um div com um <font color="red">texto antigo</font> dentro.</p> </div>

            <a href="#">Este é um link de teste.</a>
        </main>


        <footer>
            <p>&copy; 2024 Autograder Test Page</p>
        </footer>

        <script src="script.js"></script>
    </body>
    </html>
    """,

        "style.css": """
    /* Arquivo CSS para Teste */

    body {
        font-family: sans-serif;
        color: #333; /* Passa no teste 'css_uses_property' */
    }

    #main-content {
        display: flex; /* Passa no teste 'css_uses_property' */
        width: 80%;
    }

    .intro {
        font-size: 16px;
        /* Penalidade: Uso de !important */
        color: navy !important;
    }

    /* Penalidade: Regra de CSS vazia */
    .empty-rule {

    }
    """,

        "script.js": """
    // Arquivo JavaScript para Teste

    document.addEventListener('DOMContentLoaded', () => {
        const header = document.getElementById('main-content');
        console.log('Página carregada e script executado.');
    });

    // Penalidade: Uso do método proibido 'document.write'
    document.write("<p>Este texto foi adicionado com document.write</p>");

    // Teste de feature: usa arrow function
    const simpleFunction = () => {
        return true;
    };
    """
    }

    feedback_preferences = {
        "general": {
            "report_title": "Relatório Final - Desafio Web",
            "add_report_summary": True,
            "online_content": [
                {
                    "url": "https://developer.mozilla.org/pt-BR/docs/Web/HTML/Element/img",
                    "description": "Guia completo sobre a tag <img>.",
                    "linked_tests": ["check_all_images_have_alt"]
                }
            ]
        },
        "ai": {
            "assignment_context": "Este é um desafio focado em HTML semântico e CSS responsivo.",
            "feedback_persona": "Professor Sênior"
        },
        "default": {
            "category_headers": {
                "base": "✔️ Requisitos Obrigatórios",
                "bonus": "🎉 Pontos Bônus",
                "penalty": "🚨 Pontos de Atenção"
            }
        }
    }

    assignment_config = AssignmentConfig(criteria_json, feedback_preferences, None, template="web dev")
    autograder_request = AutograderRequest(submission_files, assignment_config, "student123")
    response = Autograder.grade(autograder_request)
    print(response)
    print(response.feedback)