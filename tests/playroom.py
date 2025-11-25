"""
Playroom for simulating the Autograder system.

This script sets up and runs a complete grading workflow by:
1. Defining mock submission files (HTML, CSS).
2. Defining mock configuration files (criteria, feedback, setup).
3. Building a complete AutograderRequest.
4. Calling the Autograder.grade() facade method.
5. Printing the final score and feedback.

This simulation uses the 'web dev' template and a criteria.json
that is based on 'autograder/core/schemas/config_schemas/criteria_schema.json'.

--------------------------------------------------------------------------
EXPECTED SCORE CALCULATION:
Based on the mock files and the criteria below, the expected score is ~82.5.

- Base Score (67.04 / 100):
  - HTML (60%):
    - structure (40% of HTML):
      - has_tag (11 calls): 7/11 pass -> 63.6
      - has_attribute (1 call): 1/1 pass -> 100
      - Avg: (63.6 + 100) / 2 = 81.8
    - link (20% of HTML):
      - check_css_linked (1 call): 1/1 pass -> 100
      - check_internal_links... (1 call): 0/1 pass -> 0
      - Avg: (100 + 0) / 2 = 50
    - HTML Sub-total: (81.8 * 0.66) + (50 * 0.33) = 70.5  (Weights 40+20 balanced)
    - HTML Score: 70.5 * 0.60 (HTML weight) = 42.3
  - CSS (40%):
    - responsivity (50% of CSS):
      - uses_relative_units: pass -> 100
      - check_media_queries: fail -> 0
      - check_flexbox_usage: pass -> 100
      - Avg: (100 + 0 + 100) / 3 = 66.6
    - style (50% of CSS):
      - has_style (7 calls): 4/7 pass -> 57.1
    - CSS Sub-total: (66.6 * 0.5) + (57.1 * 0.5) = 61.85
    - CSS Score: 61.85 * 0.40 (CSS weight) = 24.74
  - TOTAL BASE: 42.3 (HTML) + 24.74 (CSS) = 67.04

- Bonus Score (84.0 / 100, on 40 pt scale):
  - accessibility (20%): check_all_images_have_alt: pass -> 100
  - head_detail (80%):
    - check_head_details (2 calls): 2/2 pass -> 100
    - check_attribute_and_value (5 calls): 3/5 pass -> 60
    - Avg: (100 + 60) / 2 = 80
  - TOTAL BONUS: (100 * 0.2) + (80 * 0.8) = 20 + 64 = 84

- Penalty Score (35.0 / 100, on 50 pt scale):
  - html (50%):
    - check_bootstrap_usage: fail -> 0 (penalty 100)
    - check_id_selector_over_usage: pass -> 100 (penalty 0)
    - has_forbidden_tag: pass -> 100 (penalty 0)
    - check_html_direct_children: pass -> 100 (penalty 0)
    - check_tag_not_inside: pass -> 100 (penalty 0)
    - Avg Penalty: (100 + 0 + 0 + 0 + 0) / 5 = 20
  - project_structure (50%):
    - check_dir_exists: fail -> 0 (penalty 100)
    - check_project_structure: pass -> 100 (penalty 0)
    - Avg Penalty: (100 + 0) / 2 = 50
  - TOTAL PENALTY (avg penalty %): (20 * 0.5) + (50 * 0.5) = 10 + 25 = 35

- Final Score Calculation:
  - final = 67.04 (base)
  - bonus_to_add = (84 / 100) * 40 = 33.6
  - final = 67.04 + 33.6 = 100.64
  - final = min(100, 100.64) = 100
  - penalty_to_subtract = (35 / 100) * 50 = 17.5
  - FINAL = 100 - 17.5 = 82.5
--------------------------------------------------------------------------
"""

import logging
import json
from autograder.autograder_facade import Autograder
from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig

# Configure logging to see the autograder's output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def define_mock_submission_files() -> dict:
    """
    Creates a dictionary of mock student submission files.
    This submission is intentionally imperfect to trigger different scores.
    """
    index_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <link rel="stylesheet" href="style.css">
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="description" content="A mock page">
    </head>
    <body>
        <header class="main-header">
            <h1>Welcome</h1>
        </header>
        <main>
            <div class="content">
                <p>This is a paragraph.</p>
                <img src="image.jpg" alt="A mock image">
            </div>
        </main>
        <footer class="main-footer">
            <p>&copy; 2025</p>
        </footer>
    </body>
    </html>
    """

    style_css = """
    body {
        font-family: sans-serif;
        margin: 20px; /* has_style: margin */
        padding: 1em; /* has_style: padding, uses_relative_units */
        font-size: 16px; /* has_style: font-size */
        text-align: center; /* has_style: text-align */
    }

    .main-header {
        display: flex; /* check_flexbox_usage */
    }

    /* Intentionally using bootstrap class to fail penalty */
    .container {
        width: 100%;
    }
    """

    # Note: This submission is missing:
    # Tags: nav, article, form, input, button
    # CSS: media queries
    # Files: 'css/' directory
    return {
        "index.html": index_html,
        "style.css": style_css
    }


def define_mock_criteria_json() -> dict:
    """
    Loads the criteria configuration from the schema file.
    In a real scenario, this would come from the request.
    """
    # This is the content from autograder/core/schemas/config_schemas/criteria_schema.json
    return {
        "base": {
            "weight": 100,
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
                                        ["head", 1], ["body", 1], ["header", 1], ["nav", 1], ["main", 1],
                                        ["article", 4], ["img", 1], ["footer", 1], ["div", 1],
                                        ["form", 1], ["input", 1], ["button", 1]
                                    ]
                                },
                                {
                                    "file": "index.html",
                                    "name": "has_attribute",
                                    "calls": [["class", 2]]
                                }
                            ]
                        },
                        "link": {
                            "weight": 20,
                            "tests": [
                                {"file": "index.html", "name": "check_css_linked"},
                                {
                                    "file": "index.html",
                                    "name": "check_internal_links_to_article",
                                    "calls": [[4]]
                                }
                            ]
                        }
                    }
                },
                "css": {
                    "weight": 40,
                    "subjects": {
                        "responsivity": {
                            "weight": 50,
                            "tests": [
                                {"file": "style.css", "name": "uses_relative_units"},
                                {"file": "style.css", "name": "check_media_queries"},
                                {"file": "style.css", "name": "check_flexbox_usage"}
                            ]
                        },
                        "style": {
                            "weight": 50,
                            "tests": [
                                {
                                    "file": "style.css",
                                    "name": "has_style",
                                    "calls": [
                                        ["font-size", 1], ["font-family", 1], ["text-align", 1],
                                        ["display", 1], ["position", 1], ["margin", 1], ["padding", 1]
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        },
        "bonus": {
            "weight": 40,
            "subjects": {
                "accessibility": {
                    "weight": 20,
                    "tests": [{"file": "index.html", "name": "check_all_images_have_alt"}]
                },
                "head_detail": {
                    "weight": 80,
                    "tests": [
                        {
                            "file": "index.html",
                            "name": "check_head_details",
                            "calls": [["title"], ["meta"]]
                        },
                        {
                            "file": "index.html",
                            "name": "check_attribute_and_value",
                            "calls": [
                                ["meta", "charset", "UTF-8"],
                                ["meta", "name", "viewport"],
                                ["meta", "name", "description"],
                                ["meta", "name", "author"],
                                ["meta", "name", "keywords"]
                            ]
                        }
                    ]
                }
            }
        },
        "penalty": {
            "weight": 50,
            "subjects": {
                "html": {
                    "weight": 50,
                    "tests": [
                        {"file": "style.css", "name": "check_bootstrap_usage"},
                        {
                            "file": "style.css",
                            "name": "check_id_selector_over_usage",
                            "calls": [[2]]
                        },
                        {
                            "file": "index.html",
                            "name": "has_forbidden_tag",
                            "calls": [["script"]]
                        },
                        {"file": "index.html", "name": "check_html_direct_children"},
                        {
                            "file": "index.html",
                            "name": "check_tag_not_inside",
                            "calls": [["header", "main"], ["footer", "main"]]
                        }
                    ]
                },
                "project_structure": {
                    "weight": 50,
                    "tests": [
                        {
                            "file": "all",
                            "name": "check_dir_exists",
                            "calls": [["css"], ["imgs"]]
                        },
                        {
                            "file": "all",
                            "name": "check_project_structure",
                            "calls": [["style.css"]]
                        }
                    ]
                }
            }
        }
    }


def define_mock_feedback_json() -> dict:
    """Creates a mock feedback configuration."""
    return {
        "general": {
            "report_title": "Playroom Simulation Report",
            "show_score": True,
            "add_report_summary": True
        },
        "default": {
            "category_headers": {
                "base": "✅ Core Requirements",
                "bonus": "⭐ Bonus Points",
                "penalty": "🚨 Penalties"
            }
        }
    }


def define_mock_setup_json() -> dict:
    """Creates a mock setup configuration for pre-flight checks."""
    return {
        "file_checks": [
            "index.html",
            "style.css"
        ],
        "commands": []
    }
def print_result_tree(node, indent=0):
    """
    Recursively prints the result tree in a hierarchical format.
    
    """
    prefix = "  " * indent
    score_str = f"{node.weighted_score:.2f}" if node.weighted_score is not None else "N/A"
    
    # Based on the level chose an icon to output
    if indent == 0:
        icon = "🌳"
    elif indent == 1:
        icon = "📁"
    else:
        icon = "📘"
    
    
    weight_str = f" (w={node.weight:.1f})" if node.weight > 0 else ""
    test_str = f" [{node.total_test} tests]" if hasattr(node, 'total_test') and node.total_test > 0 else ""
    
    # Show unweighted score if different from weighted
    if node.unweighted_score and node.weighted_score != node.unweighted_score:
        score_str += f" (raw: {node.unweighted_score:.2f})"
    
    print(f"{prefix}{icon} {node.name}{weight_str}: {score_str}{test_str}")
    
    # Children recursion    
    for child in node.children:
        print_result_tree(child, indent + 1)


def run_simulation():
    """
    Main function to build and run the autograder simulation.
    """
    logger.info("--- [PLAYROOM] STARTING AUTOGRADER SIMULATION ---")

    # 1. Define all components for the request
    submission_files = define_mock_submission_files()
    criteria_json = define_mock_criteria_json()
    feedback_json = define_mock_feedback_json()
    setup_json = define_mock_setup_json()

    logger.info(f"Loaded {len(submission_files)} mock submission files.")

    # 2. Create AssignmentConfig
    assignment_config = AssignmentConfig(
        template="webdev",
        criteria=criteria_json,
        feedback=feedback_json,
        setup=setup_json
    )
    logger.info(f"Created AssignmentConfig for template: '{assignment_config.template}'")

    # 3. Create AutograderRequest
    autograder_request = AutograderRequest(
        submission_files=submission_files,
        assignment_config=assignment_config,
        student_name="Playroom Tester",
        student_credentials="playroom_tester_01",
        include_feedback=True,
        feedback_mode="default"
    )
    logger.info(f"Created AutograderRequest for: {autograder_request.student_name}")
    logger.info("Feedback mode set to: 'default'")

    # 4. Run the Autograder facade
    logger.info("--- [PLAYROOM] CALLING Autograder.grade() ---")
    try:
        response = Autograder.grade(autograder_request)
        logger.info("--- [PLAYROOM] Autograder.grade() FINISHED ---")

        # 5. Print the results
        print("\n" + "=" * 50)
        print("          AUTOGRADER SIMULATION RESULT")
        print("=" * 50 + "\n")
        print(f"Status: {response.status}")
        print(f"Final Score: {response.final_score}")

        print("\n" + "=" * 70)
        print("          HIERARCHICAL RESULT TREE")
        print("=" * 70 + "\n")
        
        if hasattr(response, 'result_tree') and response.result_tree:
          # Print the result hierachy tree
            print_result_tree(response.result_tree)

        print("\n--- DETAILED FEEDBACK ---")
        print(response.feedback)
        print("\n" + "=" * 50)
        print("         END OF SIMULATION")
        print("=" * 50 + "\n")

        

    except Exception as e:
        logger.error(f"--- [PLAYROOM] SIMULATION FAILED ---")
        logger.error(f"An exception occurred: {e}", exc_info=True)


if __name__ == "__main__":
    # This allows the script to be run directly from the root directory
    run_simulation()
