from random import weibullvariate
from typing import List, Dict

from autograder.builder.models.criteria_tree import Criteria, TestCall, Test, Subject



class CriteriaTree:
    """A factory for creating a Criteria object from a configuration dictionary."""

    @staticmethod
    def build(config_dict: dict) -> Criteria:
        """Builds the entire criteria tree, including balancing subject weights."""
        criteria = Criteria()

        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                category = getattr(criteria, category_name)
                if category != "base":
                    category.set_weight(config_dict[category_name].get("weight", 100))
                print("category",category)
                category_data = config_dict[category_name]
                if "subjects" in category_data:
                    subjects = [
                        CriteriaTree._parse_subject(s_name, s_data)
                        for s_name, s_data in category_data["subjects"].items()
                    ]
                    # Balance the weights of the top-level subjects in the category
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
            # Balance the weights of the children of this subject
            CriteriaTree._balance_subject_weights(child_subjects)
            subject.subjects = {s.name: s for s in child_subjects}
        else:
            subject.tests = []
        return subject

    @staticmethod
    def _parse_tests(test_data: list) -> List[Test]:
        tests_dict: Dict[str, Test] = {}
        for test_item in test_data:
            if isinstance(test_item, str):
                test_name = test_item
                if test_name not in tests_dict:
                    tests_dict[test_name] = Test(name=test_name)
                tests_dict[test_name].add_call(TestCall(args=[]))
            elif isinstance(test_item, dict):
                for test_name, calls_data in test_item.items():
                    if test_name not in tests_dict:
                        tests_dict[test_name] = Test(name=test_name)
                    for call_args in calls_data:
                        if isinstance(call_args, list):
                            tests_dict[test_name].add_call(TestCall(args=call_args))
                        elif isinstance(call_args, dict):
                            key, value = list(call_args.items())[0]
                            tests_dict[test_name].add_call(TestCall(args=[key, value]))
                        else:
                            tests_dict[test_name].add_call(TestCall(args=[call_args]))
        return list(tests_dict.values())



# ===============================================================
# 3. Example Usage
# ===============================================================

def custom_tree():
    example_config = {
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
                "has_tag": [
                  [
                    "body",
                    1
                  ],
                  [
                    "header",
                    1
                  ],
                  [
                    "nav",
                    1
                  ],
                  [
                    "main",
                    1
                  ],
                  [
                    "article",
                    4
                  ],
                  [
                    "img",
                    5
                  ],
                  [
                    "footer",
                    1
                  ],
                  [
                    "div",
                    1
                  ],
                  [
                    "form",
                    1
                  ],
                  [
                    "input",
                    1
                  ],
                  [
                    "button",
                    1
                  ]
                ]
              },
              {
                "has_attribute": [
                  [
                    "class",
                    2
                  ]
                ]
              }
            ]
          },
          "link": {
            "weight": 20,
            "tests": [
              "check_css_linked",
              {
                "check_internal_links_to_articles": [
                  [
                    4
                  ]
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
              "uses_relative_units",
              "check_media_queries",
              "check_flexbox_usage"
            ]
          },
          "style": {
            "weight": 50,
            "tests": [
              {
                "has_style": [
                  [
                    "font-size"
                  ],
                  [
                    "font-family"
                  ],
                  [
                    "text-align"
                  ],
                  [
                    "display"
                  ],
                  [
                    "position"
                  ],
                  [
                    "margin"
                  ],
                  [
                    "padding"
                  ]
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
        "tests": [
          "check_all_images_have_alt"
        ]
      },
      "head_detail": {
        "weight": 80,
        "tests": [
          {
            "check_head_details": [
              [
                "title"
              ],
              [
                "meta"
              ]
            ]
          },
          {
            "check_attribute_and_value": [
              [
                "meta",
                "charset",
                "UTF-8"
              ],
              [
                "meta",
                "name",
                "viewport"
              ],
              [
                "meta",
                "name",
                "description"
              ],
              [
                "meta",
                "name",
                "author"
              ],
              [
                "meta",
                "name",
                "keywords"
              ]
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
          "check_bootstrap_usage",
          {
            "check_id_selector_over_usage": [
              [
                1
              ]
            ]
          },
          "check_html_direct_children",
          {
            "check_tag_not_inside": [
              [
                "header",
                "main"
              ],
              [
                "footer",
                "main"
              ]
            ]
          }
        ]
      },
      "project_structure": {
        "weight": 50,
        "tests": [
          {
            "check_dir_exists": [
              [
                "css"
              ],
              [
                "imgs"
              ]
            ]
          },
          {
            "check_project_structure": [
              [
                "css/styles.css"
              ]
            ]
          }
        ]
      }
    }
  }
}


    return CriteriaTree.build(example_config)
if __name__ == '__main__':
    root = custom_tree()
    root.print_tree()