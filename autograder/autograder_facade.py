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

            # Step 2: Get test template
            template_name = autograder_request.assignment_config.template
            logger.info(f"Loading test template: '{template_name}'")
            test_template = TemplateLibrary.get_template(template_name)
            if test_template is None:
                logger.error(f"Template '{template_name}' not found in TemplateLibrary")
                raise ValueError(f"Unsupported template: {template_name}")

            # Step 3: Build criteria tree
            logger.info("Building criteria tree from assignment configuration:")
            logger.debug(f"Criteria configuration: {autograder_request.assignment_config.criteria}")
            if test_template.requires_pre_executed_tree:
                logger.info("Template requires pre-executed criteria tree.")
                criteria_tree = CriteriaTree.build_pre_executed_tree(autograder_request.assignment_config.criteria,test_template,autograder_request.submission_files)
            elif not test_template.requires_pre_executed_tree:
                logger.info("Template does not require pre-executed criteria tree.")
                criteria_tree = CriteriaTree.build_non_executed_tree(autograder_request.assignment_config.criteria)
            else:
                error_msg = f"Template '{template_name}' has an invalid 'requires_pre_executed_tree' setting."
                logger.error(error_msg)
                raise ValueError(error_msg)
            logger.info("Criteria tree built successfully")


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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Example usage (this would normally come from an external request)
    submission_files = {"index.html":"""
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mock Submission</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="styles.css">
</head>
<body>

    <nav class="navbar navbar-expand-lg bg-dark navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="#">Project</a>
            <div class="navbar-nav">
                <a class="nav-link" href="#section1">Section 1</a>
                <a class="nav-link" href="#section2">Section 2</a>
                <a class="nav-link" href="#section3">Section 3</a>
            </div>
        </div>
    </nav>

    <main class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item">Home</li>
                <li class="breadcrumb-item active" aria-current="page">Mock Page</li>
            </ol>
        </nav>

        <div class="row text-center mb-5">
            <h1 class="pt-3">Grid System Example</h1>
            <div class="col-md-4">
                <div class="card w-100">
                    <div class="card-body">
                        <h5 class="card-title">Card One</h5>
                        <p class="card-text">Some content here.</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Card Two</h5>
                        <p class="card-text">Some more content.</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Card Three</h5>
                        <p class="card-text">Final card content.</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="d-flex justify-content-center bg-light p-5 gap-3">
            <div>Flex Item 1</div>
            <div>Flex Item 2</div>
        </div>
        
        <div id="myCarousel" class="carousel slide mt-5" data-bs-ride="carousel">
            <div class="carousel-inner">
                <div class="carousel-item active">
                    <svg class="bd-placeholder-img bd-placeholder-img-lg d-block w-100" width="800" height="400" xmlns="http://www.w3.org/2000/svg" role="img"><title>Placeholder</title><rect width="100%" height="100%" fill="#777"></rect></svg>
                </div>
                <div class="carousel-item">
                    <svg class="bd-placeholder-img bd-placeholder-img-lg d-block w-100" width="800" height="400" xmlns="http://www.w3.org/2000/svg" role="img"><title>Placeholder</title><rect width="100%" height="100%" fill="#666"></rect></svg>
                </div>
            </div>
        </div>

        <section id="section1" class="p-5 vh-100">
            <h2>Section 1</h2>
        </section>
        <section id="section2" class="p-5 vh-100">
            <h2>Section 2</h2>
        </section>
        <section id="section3" class="p-5 vh-100">
            <h2>Section 3</h2>
        </section>

    </main>

    <footer class="text-center p-4 bg-dark text-white mt-auto">
        <p>Mock Footer</p>
    </footer>

</body>
</html>
    """,
                        "css/styles.css":"""
                        <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mock Submission</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="styles.css">
</head>
<body>

    <nav class="navbar navbar-expand-lg bg-dark navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="#">Project</a>
            <div class="navbar-nav">
                <a class="nav-link" href="#section1">Section 1</a>
                <a class="nav-link" href="#section2">Section 2</a>
                <a class="nav-link" href="#section3">Section 3</a>
            </div>
        </div>
    </nav>

    <main class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item">Home</li>
                <li class="breadcrumb-item active" aria-current="page">Mock Page</li>
            </ol>
        </nav>

        <div class="row text-center mb-5">
            <h1 class="pt-3">Grid System Example</h1>
            <div class="col-md-4">
                <div class="card w-100">
                    <div class="card-body">
                        <h5 class="card-title">Card One</h5>
                        <p class="card-text">Some content here.</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Card Two</h5>
                        <p class="card-text">Some more content.</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Card Three</h5>
                        <p class="card-text">Final card content.</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="d-flex justify-content-center bg-light p-5 gap-3">
            <div>Flex Item 1</div>
            <div>Flex Item 2</div>
        </div>
        
        <div id="myCarousel" class="carousel slide mt-5" data-bs-ride="carousel">
            <div class="carousel-inner">
                <div class="carousel-item active">
                    <svg class="bd-placeholder-img bd-placeholder-img-lg d-block w-100" width="800" height="400" xmlns="http://www.w3.org/2000/svg" role="img"><title>Placeholder</title><rect width="100%" height="100%" fill="#777"></rect></svg>
                </div>
                <div class="carousel-item">
                    <svg class="bd-placeholder-img bd-placeholder-img-lg d-block w-100" width="800" height="400" xmlns="http://www.w3.org/2000/svg" role="img"><title>Placeholder</title><rect width="100%" height="100%" fill="#666"></rect></svg>
                </div>
            </div>
        </div>

        <section id="section1" class="p-5 vh-100">
            <h2>Section 1</h2>
        </section>
        <section id="section2" class="p-5 vh-100">
            <h2>Section 2</h2>
        </section>
        <section id="section3" class="p-5 vh-100">
            <h2>Section 3</h2>
        </section>

    </main>

    <footer class="text-center p-4 bg-dark text-white mt-auto">
        <p>Mock Footer</p>
    </footer>

</body>
</html>"""}
    criteria_json = {
  "test_library": "web_dev",
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
                    ["button", 1]
                  ]
                },
                {
                  "file": "index.html",
                  "name": "has_attribute",
                  "calls": [
                    ["class", 2]
                  ]
                }
              ]
            },
            "link": {
              "weight": 20,
              "tests": [
                {
                  "file": "index.html",
                  "name": "check_css_linked"
                },
                {
                  "file": "index.html",
                  "name": "check_internal_links_to_article",
                  "calls": [
                    [4]
                  ]
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
                {
                  "file": "css/styles.css",
                  "name": "uses_relative_units"
                },
                {
                  "file": "css/styles.css",
                  "name": "check_media_queries"
                },
                {
                  "file": "css/styles.css",
                  "name": "check_flexbox_usage"
                }
              ]
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
                    ["padding", 1]
                  ]
                }
              ]
            }
          }
        }
    }
      },
      "semana_6": {
        "weight": 60,
        "subjects": {
        "bootstrap_fundamentals": {
            "weight": 70,
            "tests": [
              {
                "file": "index.html",
                "name": "check_bootstrap_linked"
              },
              {
                "file": "index.html",
                "name": "check_internal_links",
                "calls": [
                  [3]
                ]
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
                  [["bg-*"], 1]
                ]
              }
            ]
        },
        "css_and_docs": {
            "weight": 30,
            "tests": [
              {
                "file": "css/styles.css",
                "name": "check_media_queries"
              },
              {
                "file": "css/styles.css",
                "name": "has_style",
                "calls": [
                  ["margin", 1],
                  ["padding", 1],
                  ["width", 1]
                ]
              },
              {
                "file": "all",
                "name": "check_project_structure",
                "calls": [
                  ["README.md"]
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
      "semana_5": {
        "weight": 40,
        "subjects": {
        "accessibility": {
          "weight": 20,
          "tests": [
            {
              "file": "index.html",
              "name": "check_all_images_have_alt"
            }
          ]
        },
        "head_detail": {
          "weight": 80,
          "tests": [
            {
              "file": "index.html",
              "name": "check_head_details",
              "calls": [
                ["title"],
                ["meta"]
              ]
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
                      [["carousel-item"], 1]
                    ]
                 }
            ]
        },
        "formatting_classes": {
            "weight": 40,
            "tests": [
                 {
                    "file": "index.html",
                    "name": "has_class",
                    "calls": [
                      [["mt-*", "ms-*", "me-*", "mb-*", "pt-*", "ps-*", "pe-*", "pb-*", "gap-*"], 8]
                    ]
                 },
                 {
                    "file": "index.html",
                    "name": "has_class",
                    "calls": [
                      [["w-*", "mh-*", "mw-*", "vw-*", "vh-*"], 4]
                    ]
                 }
            ]
        }
    }
      }
    }
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
            {
              "file": "index.html",
              "name": "check_bootstrap_usage"
            },
            {
              "file": "css/styles.css",
              "name": "check_id_selector_over_usage",
              "calls": [
                [2]
              ]
            },
            {
              "file": "index.html",
              "name": "has_tag",
              "calls": [
                ["script", 1]
              ]
            },
            {
              "file": "index.html",
              "name": "check_html_direct_children"
            },
            {
              "file": "index.html",
              "name": "check_tag_not_inside",
              "calls": [
                ["header", "main"],
                ["footer", "main"]
              ]
            }
          ]
        },
        "project_structure": {
          "weight": 50,
          "tests": [
            {
              "file": "all",
              "name": "check_dir_exists",
              "calls": [
                ["css"],
                ["imgs"]
              ]
            },
            {
              "file": "all",
              "name": "check_project_structure",
              "calls": [
                ["css/styles.css"]
              ]
            }
          ]
        }
    }
      }
    }
  }
}
    setup_json = {
  "test_library": "web_dev",
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
                    ["button", 1]
                  ]
                },
                {
                  "file": "index.html",
                  "name": "has_attribute",
                  "calls": [
                    ["class", 2]
                  ]
                }
              ]
            },
            "link": {
              "weight": 20,
              "tests": [
                {
                  "file": "index.html",
                  "name": "check_css_linked"
                },
                {
                  "file": "index.html",
                  "name": "check_internal_links_to_article",
                  "calls": [
                    [4]
                  ]
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
                {
                  "file": "css/styles.css",
                  "name": "uses_relative_units"
                },
                {
                  "file": "css/styles.css",
                  "name": "check_media_queries"
                },
                {
                  "file": "css/styles.css",
                  "name": "check_flexbox_usage"
                }
              ]
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
                    ["padding", 1]
                  ]
                }
              ]
            }
          }
        }
    }
      },
      "semana_6": {
        "weight": 60,
        "subjects": {
        "bootstrap_fundamentals": {
            "weight": 70,
            "tests": [
              {
                "file": "index.html",
                "name": "check_bootstrap_linked"
              },
              {
                "file": "index.html",
                "name": "check_internal_links",
                "calls": [
                  [3]
                ]
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
                  [["bg-*"], 1]
                ]
              }
            ]
        },
        "css_and_docs": {
            "weight": 30,
            "tests": [
              {
                "file": "css/styles.css",
                "name": "check_media_queries"
              },
              {
                "file": "css/styles.css",
                "name": "has_style",
                "calls": [
                  ["margin", 1],
                  ["padding", 1],
                  ["width", 1]
                ]
              },
              {
                "file": "all",
                "name": "check_project_structure",
                "calls": [
                  ["README.md"]
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
      "semana_5": {
        "weight": 40,
        "subjects": {
        "accessibility": {
          "weight": 20,
          "tests": [
            {
              "file": "index.html",
              "name": "check_all_images_have_alt"
            }
          ]
        },
        "head_detail": {
          "weight": 80,
          "tests": [
            {
              "file": "index.html",
              "name": "check_head_details",
              "calls": [
                ["title"],
                ["meta"]
              ]
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
                      [["carousel-item"], 1]
                    ]
                 }
            ]
        },
        "formatting_classes": {
            "weight": 40,
            "tests": [
                 {
                    "file": "index.html",
                    "name": "has_class",
                    "calls": [
                      [["mt-*", "ms-*", "me-*", "mb-*", "pt-*", "ps-*", "pe-*", "pb-*", "gap-*"], 8]
                    ]
                 },
                 {
                    "file": "index.html",
                    "name": "has_class",
                    "calls": [
                      [["w-*", "mh-*", "mw-*", "vw-*", "vh-*"], 4]
                    ]
                 }
            ]
        }
    }
      }
    }
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
            {
              "file": "index.html",
              "name": "check_bootstrap_usage"
            },
            {
              "file": "css/styles.css",
              "name": "check_id_selector_over_usage",
              "calls": [
                [2]
              ]
            },
            {
              "file": "index.html",
              "name": "has_tag",
              "calls": [
                ["script", 1]
              ]
            },
            {
              "file": "index.html",
              "name": "check_html_direct_children"
            },
            {
              "file": "index.html",
              "name": "check_tag_not_inside",
              "calls": [
                ["header", "main"],
                ["footer", "main"]
              ]
            }
          ]
        },
        "project_structure": {
          "weight": 50,
          "tests": [
            {
              "file": "all",
              "name": "check_dir_exists",
              "calls": [
                ["css"],
                ["imgs"]
              ]
            },
            {
              "file": "all",
              "name": "check_project_structure",
              "calls": [
                ["css/styles.css"]
              ]
            }
          ]
        }
    }
      }
    }
  }
}
    feedback_json = {
  "test_library": "web_dev",
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
                    ["button", 1]
                  ]
                },
                {
                  "file": "index.html",
                  "name": "has_attribute",
                  "calls": [
                    ["class", 2]
                  ]
                }
              ]
            },
            "link": {
              "weight": 20,
              "tests": [
                {
                  "file": "index.html",
                  "name": "check_css_linked"
                },
                {
                  "file": "index.html",
                  "name": "check_internal_links_to_article",
                  "calls": [
                    [4]
                  ]
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
                {
                  "file": "css/styles.css",
                  "name": "uses_relative_units"
                },
                {
                  "file": "css/styles.css",
                  "name": "check_media_queries"
                },
                {
                  "file": "css/styles.css",
                  "name": "check_flexbox_usage"
                }
              ]
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
                    ["padding", 1]
                  ]
                }
              ]
            }
          }
        }
    }
      },
      "semana_6": {
        "weight": 60,
        "subjects": {
        "bootstrap_fundamentals": {
            "weight": 70,
            "tests": [
              {
                "file": "index.html",
                "name": "check_bootstrap_linked"
              },
              {
                "file": "index.html",
                "name": "check_internal_links",
                "calls": [
                  [3]
                ]
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
                  [["bg-*"], 1]
                ]
              }
            ]
        },
        "css_and_docs": {
            "weight": 30,
            "tests": [
              {
                "file": "css/styles.css",
                "name": "check_media_queries"
              },
              {
                "file": "css/styles.css",
                "name": "has_style",
                "calls": [
                  ["margin", 1],
                  ["padding", 1],
                  ["width", 1]
                ]
              },
              {
                "file": "all",
                "name": "check_project_structure",
                "calls": [
                  ["README.md"]
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
      "semana_5": {
        "weight": 40,
        "subjects": {
        "accessibility": {
          "weight": 20,
          "tests": [
            {
              "file": "index.html",
              "name": "check_all_images_have_alt"
            }
          ]
        },
        "head_detail": {
          "weight": 80,
          "tests": [
            {
              "file": "index.html",
              "name": "check_head_details",
              "calls": [
                ["title"],
                ["meta"]
              ]
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
                      [["carousel-item"], 1]
                    ]
                 }
            ]
        },
        "formatting_classes": {
            "weight": 40,
            "tests": [
                 {
                    "file": "index.html",
                    "name": "has_class",
                    "calls": [
                      [["mt-*", "ms-*", "me-*", "mb-*", "pt-*", "ps-*", "pe-*", "pb-*", "gap-*"], 8]
                    ]
                 },
                 {
                    "file": "index.html",
                    "name": "has_class",
                    "calls": [
                      [["w-*", "mh-*", "mw-*", "vw-*", "vh-*"], 4]
                    ]
                 }
            ]
        }
    }
      }
    }
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
            {
              "file": "index.html",
              "name": "check_bootstrap_usage"
            },
            {
              "file": "css/styles.css",
              "name": "check_id_selector_over_usage",
              "calls": [
                [2]
              ]
            },
            {
              "file": "index.html",
              "name": "has_tag",
              "calls": [
                ["script", 1]
              ]
            },
            {
              "file": "index.html",
              "name": "check_html_direct_children"
            },
            {
              "file": "index.html",
              "name": "check_tag_not_inside",
              "calls": [
                ["header", "main"],
                ["footer", "main"]
              ]
            }
          ]
        },
        "project_structure": {
          "weight": 50,
          "tests": [
            {
              "file": "all",
              "name": "check_dir_exists",
              "calls": [
                ["css"],
                ["imgs"]
              ]
            },
            {
              "file": "all",
              "name": "check_project_structure",
              "calls": [
                ["css/styles.css"]
              ]
            }
          ]
        }
    }
      }
    }
  }
}
    config = AssignmentConfig(criteria_json,feedback_json,setup_json,"web dev")
    request = AutograderRequest(submission_files,config,"Arthur","123","default")
    facade = Autograder.grade(request)