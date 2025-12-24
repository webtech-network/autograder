from typing import List, Dict, Any

from autograder.builder.models.criteria_tree import Criteria, Subject, Test, TestResult
from autograder.builder.models.template import Template
from autograder.context import request_context

class CriteriaTree:
    """A factory for creating a Criteria object from a configuration dictionary."""
    @staticmethod
    def build_pre_executed_tree(template: Template) -> Criteria:
        """ Builds a Criteria tree and pre-executes all tests, having leaves as TestResult objects."""

        request = request_context.get_request()
        config_dict = request.assignment_config.criteria
        submission_files = request.submission_files
        criteria = Criteria()

        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                category = getattr(criteria, category_name)
                category_data = config_dict[category_name]

                if "weight" in category_data:
                    category.max_score = category_data.get("weight", 100)

                # Validate that category doesn't have both subjects and tests
                if "subjects" in category_data and "tests" in category_data:
                    raise ValueError(f"Config error: Category '{category_name}' cannot have both 'tests' and 'subjects'.")

                if "subjects" in category_data:
                    subjects_data = category_data["subjects"]
                    if isinstance(subjects_data, list):
                        # New format: subjects is an array
                        subjects = [
                            CriteriaTree._parse_and_execute_subject(s.get("subject_name"), s, template, submission_files)
                            for s in subjects_data
                        ]
                    else:
                        # Old format: subjects is a dict (for backward compatibility)
                        subjects = [
                            CriteriaTree._parse_and_execute_subject(s_name, s_data, template, submission_files)
                            for s_name, s_data in subjects_data.items()
                        ]
                    CriteriaTree._balance_subject_weights(subjects)
                    for subject in subjects:
                        category.add_subject(subject)
                elif "tests" in category_data:
                    # Handle tests directly at category level
                    parsed_tests = CriteriaTree._parse_tests(category_data["tests"])
                    executed_tests = []
                    for test in parsed_tests:
                        test_results = test.get_result(template, submission_files, category_name)
                        executed_tests.extend(test_results)
                    category.tests = executed_tests
        return criteria

    @staticmethod
    def build_non_executed_tree() -> Criteria:
        """Builds the entire criteria tree, including balancing subject weights."""
        criteria = Criteria()
        request = request_context.get_request()
        config_dict = request.assignment_config.criteria
        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                category = getattr(criteria, category_name)
                category_data = config_dict[category_name]

                # Set max_score for bonus and penalty categories
                if "weight" in category_data:
                    category.max_score = category_data.get("weight", 100)

                # Validate that category doesn't have both subjects and tests
                if "subjects" in category_data and "tests" in category_data:
                    raise ValueError(f"Config error: Category '{category_name}' cannot have both 'tests' and 'subjects'.")

                if "subjects" in category_data:
                    subjects_data = category_data["subjects"]
                    if isinstance(subjects_data, list):
                        # New format: subjects is an array
                        subjects = [
                            CriteriaTree._parse_subject(s.get("subject_name"), s)
                            for s in subjects_data
                        ]
                    else:
                        # Old format: subjects is a dict (for backward compatibility)
                        subjects = [
                            CriteriaTree._parse_subject(s_name, s_data)
                            for s_name, s_data in subjects_data.items()
                        ]
                    CriteriaTree._balance_subject_weights(subjects)
                    for subject in subjects:
                        category.add_subject(subject)
                elif "tests" in category_data:
                    # Handle tests directly at category level
                    category.tests = CriteriaTree._parse_tests(category_data["tests"])
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
            subjects_data = subject_data["subjects"]
            if isinstance(subjects_data, list):
                # New format: subjects is an array
                child_subjects = [
                    CriteriaTree._parse_subject(sub.get("subject_name"), sub)
                    for sub in subjects_data
                ]
            else:
                # Old format: subjects is a dict (for backward compatibility)
                child_subjects = [
                    CriteriaTree._parse_subject(sub_name, sub_data)
                    for sub_name, sub_data in subjects_data.items()
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
            subjects_data = subject_data["subjects"]
            if isinstance(subjects_data, list):
                # New format: subjects is an array
                child_subjects = [
                    CriteriaTree._parse_and_execute_subject(sub.get("subject_name"), sub, template, submission_files)
                    for sub in subjects_data
                ]
            else:
                # Old format: subjects is a dict (for backward compatibility)
                child_subjects = [
                    CriteriaTree._parse_and_execute_subject(sub_name, sub_data, template, submission_files)
                    for sub_name, sub_data in subjects_data.items()
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
                test = Test(name=test_item)  # Default file
                test.parameters = {}
                parsed_tests.append(test)

            elif isinstance(test_item, dict):
                # Handle complex test definitions
                test_name = test_item.get("name")
                test_file = test_item.get("file")
                if not test_name:
                    raise ValueError(f"Test definition is missing 'name': {test_item}")

                test = Test(name=test_name, filename=test_file)

                # New format: "parameters" as an array of name-value pairs
                if "parameters" in test_item:
                    params = test_item["parameters"]
                    # New array format: [{"name": "tag", "value": "div"}, ...]
                    if isinstance(params, list):
                        # Empty array -> empty parameters
                        if not params:
                            test.parameters = {}
                        # Check if first item is a dict with 'name' key (new array format)
                        elif isinstance(params[0], dict) and "name" in params[0]:
                            # Validate and convert all items
                            try:
                                test.parameters = {
                                    p["name"]: p["value"] 
                                    for p in params 
                                    if isinstance(p, dict) and "name" in p and "value" in p
                                }
                            except KeyError as e:
                                raise ValueError(f"Invalid parameter format in test '{test_name}': missing 'name' or 'value' key")
                        # Old list format (positional args from backward compatibility)
                        else:
                            test.parameters = params
                    # Old dict format for backward compatibility: {"tag": "div", ...}
                    else:
                        test.parameters = params
                # Old format: "calls" as an array (backward compatibility)
                elif "calls" in test_item:
                    # In old format, calls were arrays of positional arguments
                    # We need to create a separate test for each call since
                    # old format supported multiple calls per test
                    calls = test_item["calls"]
                    for call_args in calls:
                        test_copy = Test(name=test_name, filename=test_file)
                        # Store as list to maintain backward compatibility
                        test_copy.parameters = call_args if isinstance(call_args, (list, dict)) else []
                        parsed_tests.append(test_copy)
                    continue  # Skip the append at the end since we already added
                else:
                    # If no 'parameters' or 'calls' are specified, it's a test with no arguments
                    test.parameters = {}

                parsed_tests.append(test)

        return parsed_tests



if __name__ == "__main__":
    criteria_json = {
  "test_library": "essay ai grader",
  "base": {
    "weight": 100,
    "subjects": {
      "foundations": {
        "weight": 60,
        "tests": [
          {
            "file": "essay.txt",
            "name": "thesis_statement"
          },
          {
            "file": "essay.txt",
            "name": "clarity_and_cohesion"
          },
          {
            "file": "essay.txt",
            "name": "grammar_and_spelling"
          }
        ]
      },
      "prompt_adherence": {
        "weight": 40,
        "tests": [
          {
            "file": "essay.txt",
            "name": "adherence_to_prompt",
            "calls": [
              [ "Analyze the primary causes of the Industrial Revolution and its impact on 19th-century society." ]
            ]
          }
        ]
      }
    }
  },
  "bonus": {
    "weight": 30,
    "subjects": {
      "rhetorical_skill": {
        "weight": 70,
        "tests": [
          {
            "file": "essay.txt",
            "name": "counterargument_handling"
          },
          {
            "file": "essay.txt",
            "name": "vocabulary_and_diction"
          },
          {
            "file": "essay.txt",
            "name": "sentence_structure_variety"
          }
        ]
      },
      "deeper_analysis": {
        "weight": 30,
        "tests": [
          {
            "file": "essay.txt",
            "name": "topic_connection",
            "calls": [
              [ "technological innovation", "social inequality" ]
            ]
          }
        ]
      }
    }
  },
  "penalty": {
    "weight": 25,
    "subjects": {
      "logical_integrity": {
        "weight": 100,
        "tests": [
          {
            "file": "essay.txt",
            "name": "logical_fallacy_check"
          },
          {
            "file": "essay.txt",
            "name": "bias_detection"
          },
          {
              "file": "essay.txt",
              "name": "originality_and_plagiarism"
          }
        ]
      }
    }
  }
}
    submission_files = {"essay.txt": """Artificial intelligence (AI) is no longer a concept confined to science fiction; it is a transformative force actively reshaping industries and redefining the nature of work. Its integration into the modern workforce presents a profound duality: on one hand, it offers unprecedented opportunities for productivity and innovation, while on the other, it poses significant challenges related to job displacement and economic inequality. Navigating this transition successfully requires a proactive and nuanced approach from policymakers, businesses, and individuals alike.
The primary benefit of AI in the workplace is its capacity to augment human potential and drive efficiency. AI-powered systems can analyze vast datasets in seconds, automating routine cognitive and manual tasks, which frees human workers to focus on more complex, creative, and strategic endeavors. For instance, in medicine, AI algorithms assist radiologists in detecting tumors with greater accuracy, while in finance, they identify fraudulent transactions far more effectively than any human team. This collaboration between human and machine not only boosts output but also creates new roles centered around AI development, ethics, and system maintenance—jobs that did not exist a decade ago.
However, this technological advancement casts a significant shadow of disruption. The same automation that drives efficiency also leads to job displacement, particularly for roles characterized by repetitive tasks. Assembly line workers, data entry clerks, and even some paralegal roles face a high risk of obsolescence. This creates a widening skills gap, where demand for high-level technical skills soars while demand for traditional skills plummets. Without robust mechanisms for reskilling and upskilling the existing workforce, this gap threatens to exacerbate socio-economic inequality, creating a divide between those who can command AI and those who are displaced by it. There are many gramatical errors in this sentence, for testing purposes.
The most critical challenge, therefore, is not to halt technological progress but to manage its societal impact. A multi-pronged strategy is essential. Governments and educational institutions must collaborate to reform curricula, emphasizing critical thinking, digital literacy, and lifelong learning. Furthermore, corporations have a responsibility to invest in their employees through continuous training programs. Finally, strengthening social safety nets, perhaps through concepts like Universal Basic Income (UBI) or enhanced unemployment benefits, may be necessary to support individuals as they navigate this volatile transition period.
In conclusion, AI is a double-edged sword. Its potential to enhance productivity and create new avenues for growth is undeniable, but so are the risks of displacement and inequality. The future of work will not be a battle of humans versus machines, but rather a story of adaptation. By investing in education, promoting equitable policies, and fostering a culture of continuous learning, we can harness the power of AI to build a more prosperous and inclusive workforce for all."""}
    #tree = CriteriaTree.build_pre_executed_tree(criteria_json, WebDevLibrary(), submission_files)
    tree = CriteriaTree.build_non_executed_tree(criteria_json)
    #tree.print_pre_executed_tree()
    tree.print_tree()