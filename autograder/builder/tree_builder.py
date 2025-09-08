from typing import List, Dict, Any

from autograder.builder.models.criteria_tree import Criteria, Subject, Test, TestCall, TestResult
from autograder.builder.models.template import Template
from autograder.builder.template_library.templates.web_dev import WebDevLibrary


class CriteriaTree:
    """A factory for creating a Criteria object from a configuration dictionary."""

    @staticmethod
    def build_pre_executed_tree(config_dict: dict, template: Template, submission_files: dict) -> Criteria:
        """ Builds a Criteria tree and pre-executes all tests, having leaves as TestResult objects."""
        criteria = Criteria()

        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                category = getattr(criteria, category_name)
                category_data = config_dict[category_name]

                if "weight" in category_data:
                    category.max_score = category_data.get("weight", 100)

                if "subjects" in category_data:
                    subjects = [
                        CriteriaTree._parse_and_execute_subject(s_name, s_data, template, submission_files)
                        for s_name, s_data in category_data["subjects"].items()
                    ]
                    CriteriaTree._balance_subject_weights(subjects)
                    for subject in subjects:
                        category.add_subject(subject)
        return criteria

    @staticmethod
    def build_non_executed_tree(config_dict: dict) -> Criteria:
        """Builds the entire criteria tree, including balancing subject weights."""
        criteria = Criteria()

        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                category = getattr(criteria, category_name)
                category_data = config_dict[category_name]

                # Set max_score for bonus and penalty categories
                if "weight" in category_data:
                    category.max_score = category_data.get("weight", 100)

                if "subjects" in category_data:
                    subjects = [
                        CriteriaTree._parse_subject(s_name, s_data)
                        for s_name, s_data in category_data["subjects"].items()
                    ]
                    CriteriaTree._balance_subject_weights(subjects)
                    for subject in subjects:
                        category.add_subject(subject)
        return criteria

    @staticmethod
    def _balance_subject_weights(subjects: List[Subject]):
        """Balances the weights of a list of sibling subjects to sum to 100."""
        total_weight = sum(s.weight for s in subjects)
        if total_weight > 0 and total_weight != 100:
            scaling_factor = 100 / total_weight
            for subject in subjects:
                subject.weight *= scaling_factor

    @staticmethod
    def _parse_subject(subject_name: str, subject_data: dict) -> Subject:
        """Recursively parses a subject and balances the weights of its children."""
        if "tests" in subject_data and "subjects" in subject_data:
            raise ValueError(f"Config error: Subject '{subject_name}' cannot have both 'tests' and 'subjects'.")

        subject = Subject(subject_name, subject_data.get("weight", 0))
        if "tests" in subject_data:
            subject.tests = CriteriaTree._parse_tests(subject_data["tests"])
        elif "subjects" in subject_data:
            child_subjects = [
                CriteriaTree._parse_subject(sub_name, sub_data)
                for sub_name, sub_data in subject_data["subjects"].items()
            ]
            CriteriaTree._balance_subject_weights(child_subjects)
            subject.subjects = {s.name: s for s in child_subjects}
        else:
            subject.tests = []
        return subject

    @staticmethod
    def _parse_and_execute_subject(subject_name: str, subject_data: dict, template: Template, submission_files: dict) -> Subject:
        """Recursively parses a subject, executes its tests, and balances the weights of its children."""
        if "tests" in subject_data and "subjects" in subject_data:
            raise ValueError(f"Config error: Subject '{subject_name}' cannot have both 'tests' and 'subjects'.")

        subject = Subject(subject_name, subject_data.get("weight", 0))

        if "tests" in subject_data:
            parsed_tests = CriteriaTree._parse_tests(subject_data["tests"])
            executed_tests = []
            for test in parsed_tests:
                # The run method executes the test and returns a list of TestResult objects
                test_results = test.get_result(template, submission_files, subject_name)
                executed_tests.extend(test_results)
            subject.tests = executed_tests  # Store TestResult objects instead of Test objects
        elif "subjects" in subject_data:
            child_subjects = [
                CriteriaTree._parse_and_execute_subject(sub_name, sub_data, template, submission_files)
                for sub_name, sub_data in subject_data["subjects"].items()
            ]
            CriteriaTree._balance_subject_weights(child_subjects)
            subject.subjects = {s.name: s for s in child_subjects}
        else:
            subject.tests = []
        return subject

    @staticmethod
    def _parse_tests(test_data: list) -> List[Test]:
        """Parses a list of test definitions from the configuration."""
        parsed_tests = []
        for test_item in test_data:
            if isinstance(test_item, str):
                # Handle simple test names (e.g., "check_no_unclosed_tags")
                test = Test(name=test_item, filename="index.html")  # Default file
                test.add_call(TestCall(args=[]))
                parsed_tests.append(test)

            elif isinstance(test_item, dict):
                # Handle complex test definitions
                test_name = test_item.get("name")
                test_file = test_item.get("file")
                if not test_name or not test_file:
                    raise ValueError(f"Test definition is missing 'name' or 'file': {test_item}")

                test = Test(name=test_name, filename=test_file)

                if "calls" in test_item:
                    for call_args in test_item["calls"]:
                        test.add_call(TestCall(args=call_args))
                else:
                    # If no 'calls' are specified, it's a single call with no arguments
                    test.add_call(TestCall(args=[]))

                parsed_tests.append(test)

        return parsed_tests



if __name__ == "__main__":
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
    submission_files = {"index.html":"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>Welcome to My Page</h1> <!-- ✅ Matches test requirement -->
    <p>This is a simple webpage.</p> <!-- ✅ Just needs a paragraph -->

    <button id="myButton">Click Me!</button> <!-- ✅ Button with correct ID & text -->

    <script src="script.js"></script>
</body>
</html>""",
                        "style.css":"""body {}
    font-size: 16px; /* ✅ Uses relative unit (px is acceptable here) */
    font-family: Arial, sans-serif; /* ✅ Valid font family */
    text-align: center; /* ✅ Valid text alignment */
    display: flex; /* ✅ Uses Flexbox */
    position: relative; /* ✅ Valid position */
    margin: 0; /* ✅ Valid margin */
    padding: 0; /* ✅ Valid padding */"""
}
    #tree = CriteriaTree.build_pre_executed_tree(criteria_json, WebDevLibrary(), submission_files)
    tree = CriteriaTree.build_non_executed_tree(criteria_json)
    #tree.print_pre_executed_tree()
    tree.print_tree()