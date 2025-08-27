from autograder.core.grading.grader import Grader
from connectors.models.assignment_config import AssignmentConfig
from connectors.models.autograder_request import AutograderRequest
from autograder.builder.tree_builder import CriteriaTree
from builder.template_library.library import TemplateLibrary
class Autograder:

    @staticmethod
    def grade(autograder_request:AutograderRequest):
        criteria_tree = CriteriaTree.build(autograder_request.assignment_config.criteria)
        test_template = TemplateLibrary.get_template("web dev")
        if test_template is None:
            raise ValueError(f"Unsupported template: {'web dev'}")
        grader = Grader(criteria_tree, test_template)
        result = grader.run(autograder_request.submission_files,autograder_request.student_name)
        return result


# Example usage:
if __name__ == "__main__":
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
    assignment_config = AssignmentConfig(None,criteria_json,None,None,None,None,None)
    autograder_request = AutograderRequest(submission_files,assignment_config,"student123")
    print(Autograder.grade(autograder_request))
