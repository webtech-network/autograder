from typing import List, Dict, Any


# Assuming these models are in a separate file, e.g., autograder.builder.models.criteria_tree
class TestCall:
    def __init__(self, args: List[Any]):
        self.args = args

    def __repr__(self):
        return f"TestCall(args={self.args})"


class Test:
    def __init__(self, name: str, filename: str):
        self.name = name
        self.file = filename
        self.calls: List[TestCall] = []

    def add_call(self, call: TestCall):
        self.calls.append(call)

    def __repr__(self):
        return f"Test(name='{self.name}', file='{self.file}', calls={len(self.calls)})"


class Subject:
    def __init__(self, name, weight=0):
        self.name = name
        self.weight = weight
        self.tests: List[Test] | None = None
        self.subjects: Dict[str, 'Subject'] | None = None

    def __repr__(self):
        if self.subjects is not None:
            return f"Subject(name='{self.name}', weight={self.weight}, subjects={len(self.subjects)})"
        return f"Subject(name='{self.name}', weight={self.weight}, tests={len(self.tests)})"


class TestCategory:
    def __init__(self, name: str):
        self.name = name
        self.max_score = 100
        self.subjects: Dict[str, Subject] = {}

    def add_subject(self, subject: Subject):
        self.subjects[subject.name] = subject

    def set_weight(self, weight: int):
        self.max_score = weight

    def __repr__(self):
        return f"TestCategory(name='{self.name}', max_score={self.max_score}, subjects={list(self.subjects.keys())})"


class Criteria:
    def __init__(self):
        self.base = TestCategory("base")
        self.bonus = TestCategory("bonus")
        self.penalty = TestCategory("penalty")

    def __repr__(self):
        return f"Criteria(categories=['base', 'bonus', 'penalty'])"

    def print_tree(self):
        print(f"🌲 Criteria Tree")
        self._print_category(self.base, prefix="  ")
        self._print_category(self.bonus, prefix="  ")
        self._print_category(self.penalty, prefix="  ")

    def _print_category(self, category: TestCategory, prefix: str):
        if not category.subjects:
            return
        print(f"{prefix}📁 {category.name.upper()} (max_score: {category.max_score})")
        for subject in category.subjects.values():
            self._print_subject(subject, prefix=prefix + "    ")

    def _print_subject(self, subject: Subject, prefix: str):
        weight_display = int(subject.weight) if subject.weight == int(subject.weight) else f"{subject.weight:.2f}"
        print(f"{prefix}📘 {subject.name} (weight: {weight_display})")
        if subject.subjects is not None:
            for sub in subject.subjects.values():
                self._print_subject(sub, prefix=prefix + "    ")
        if subject.tests is not None:
            for test in subject.tests:
                print(f"{prefix}  - 🧪 {test.name} (file: {test.file})")
                for call in test.calls:
                    print(f"{prefix}    - Parameters: {call.args}")


class CriteriaTreeFactory:
    """A factory for creating a Criteria object from a configuration dictionary."""

    @staticmethod
    def build(config_dict: dict) -> Criteria:
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
                        CriteriaTreeFactory._parse_subject(s_name, s_data)
                        for s_name, s_data in category_data["subjects"].items()
                    ]
                    CriteriaTreeFactory._balance_subject_weights(subjects)
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
            subject.tests = CriteriaTreeFactory._parse_tests(subject_data["tests"])
        elif "subjects" in subject_data:
            child_subjects = [
                CriteriaTreeFactory._parse_subject(sub_name, sub_data)
                for sub_name, sub_data in subject_data["subjects"].items()
            ]
            CriteriaTreeFactory._balance_subject_weights(child_subjects)
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
                # Assume a default file if not specified, or raise an error
                # For this example, we'll assume a default, but a real case might need a file attribute
                test = Test(name=test_item, filename="index.html")  # Default file
                test.add_call(TestCall(args=[]))
                parsed_tests.append(test)

            elif isinstance(test_item, dict):
                # Handle complex test definitions (e.g., {"file": "...", "name": "...", "calls": [...]})
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
                "name": "check_internal_links_to_articles",
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
  "bonus": {
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
  "penalty": {
    "weight": 50,
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
            "name": "has_forbidden_tag",
            "calls": [
              ["script"]
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
    criteria = CriteriaTreeFactory.build(criteria_json)
    criteria.print_tree()