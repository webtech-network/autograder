"""
Criteria Tree Builder Module.

This module provides the CriteriaTree factory class for constructing
hierarchical grading rubrics from configuration dictionaries. The criteria
tree organizes tests into a weighted hierarchy for accurate score
calculation.

Tree Structure:
    Criteria (root)
    ├── Base Category (required, 100 points max)
    │   ├── Subject 1 (weight: 40)
    │   │   ├── Test 1
    │   │   └── Test 2
    │   └── Subject 2 (weight: 60)
    │       ├── Sub-subject 1 (weight: 50)
    │       └── Sub-subject 2 (weight: 50)
    ├── Bonus Category (optional, configurable max)
    │   └── Subject 1 (weight: 100)
    └── Penalty Category (optional, configurable max)
        └── Subject 1 (weight: 100)

Building Strategies:
    1. Pre-executed Tree: Tests are run during tree construction
       - Used for AI-assisted grading where test results inform tree structure
       - Leaves are TestResult objects (already executed)

    2. Non-executed Tree: Tests are defined but not run yet
       - Used for standard grading where execution happens during grading phase
       - Leaves are Test objects (not yet executed)

Weight Balancing:
    Subject weights at each level are automatically normalized to sum to 100,
    ensuring proper proportional scoring regardless of how weights are specified.
"""

from typing import List

from autograder.builder.models.criteria_tree import Criteria, Subject, Test, TestCall
from autograder.builder.models.template import Template
from autograder.context import request_context


class CriteriaTree:
    """
    Factory class for building criteria trees from configuration dictionaries.

    This class provides static methods to construct hierarchical grading rubrics
    that organize tests into weighted categories and subjects. It supports two
    building strategies based on when tests should be executed.

    Design Pattern:
        Factory pattern - Creates complex object trees from simple configuration

    Key Responsibilities:
        1. Parse configuration dictionaries into tree structures
        2. Create and link Subject and Test nodes
        3. Balance weights across sibling subjects
        4. Execute tests (pre-executed strategy only)
        5. Validate tree structure

    Usage:
        >>> # Pre-executed tree (tests run during build)
        >>> tree = CriteriaTree.build_pre_executed_tree(template)
        >>>
        >>> # Non-executed tree (tests run during grading)
        >>> tree = CriteriaTree.build_non_executed_tree()
    """

    @staticmethod
    def build_pre_executed_tree(template: Template) -> Criteria:
        """
        Build a criteria tree with all tests pre-executed.

        This strategy runs all tests during tree construction, storing TestResult
        objects as leaves. This is useful when:
        - Using AI to analyze test results before grading
        - Need test results to inform tree structure
        - Want to cache test execution results

        Process:
            1. Parse configuration from request context
            2. Create category nodes (base, bonus, penalty)
            3. Recursively build subjects with their tests
            4. Execute each test and store results
            5. Balance weights at each tree level

        Args:
            template (Template): Test template defining how to run tests
                Must provide test execution methods

        Returns:
            Criteria: Root node of the criteria tree with pre-executed tests

        Note:
            Test results are stored as TestResult objects at leaf nodes.
            The tree structure is finalized - no further test execution needed.

        Example:
            >>> from autograder.builder.template_library.library import TemplateLibrary
            >>> template = TemplateLibrary.get_template("web_dev")
            >>> tree = CriteriaTree.build_pre_executed_tree(template)
            >>> tree.print_pre_executed_tree()  # Shows test results
        """
        # Get request data from global context
        request = request_context.get_request()
        config_dict = request.assignment_config.criteria
        submission_files = request.submission_files

        # Create root criteria node
        criteria = Criteria()

        # Process each category (base, bonus, penalty) if defined
        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                # Get reference to the category object
                category = getattr(criteria, category_name)
                category_data = config_dict[category_name]

                # Set maximum score for this category
                # Base is always 100, bonus/penalty can be configured
                if "weight" in category_data:
                    category.max_score = category_data.get("weight", 100)

                # Build and attach subjects if defined
                if "subjects" in category_data:
                    subjects = [
                        CriteriaTree._parse_and_execute_subject(
                            s_name, s_data, template, submission_files
                        )
                        for s_name, s_data in category_data["subjects"].items()
                    ]
                    # Normalize weights to sum to 100
                    CriteriaTree._balance_subject_weights(subjects)

                    # Add subjects to category
                    for subject in subjects:
                        category.add_subject(subject)

        return criteria

    @staticmethod
    def build_non_executed_tree() -> Criteria:
        """
        Build a criteria tree without executing tests.

        This strategy creates the tree structure but doesn't run tests yet.
        Tests are stored as Test objects (not TestResult) and will be executed
        later during the grading phase.

        Use this when:
        - Following standard grading workflow
        - Don't need test results until grading time
        - Want to defer test execution for performance

        Process:
            1. Parse configuration from request context
            2. Create category nodes (base, bonus, penalty)
            3. Recursively build subjects with test definitions
            4. Balance weights at each tree level
            5. Return tree ready for execution

        Returns:
            Criteria: Root node of criteria tree with unexecuted tests

        Note:
            Tests are stored as Test objects at leaf nodes.
            Call grader.run() to execute tests and calculate scores.

        Example:
            >>> tree = CriteriaTree.build_non_executed_tree()
            >>> grader = Grader(tree, template)
            >>> result = grader.run()  # Tests executed here
        """
        # Create root criteria node
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
        """
        Parse a subject and balance the weights of its children.

        Recursively processes subject configuration from the criteria tree,
        creating Subject objects with nested tests or sub-subjects.
        """
        if "tests" in subject_data and "subjects" in subject_data:
            msg = (
                f"Config error: Subject '{subject_name}' cannot have "
                f"both 'tests' and 'subjects'."
            )
            raise ValueError(msg)

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
    def _parse_and_execute_subject(
        subject_name: str,
        subject_data: dict,
        template: Template,
        submission_files: dict,
    ) -> Subject:
        """
        Parse a subject, execute tests, and balance children weights.

        Recursively processes and executes all tests within the subject tree,
        returning a fully populated Subject with executed test results.
        """
        if "tests" in subject_data and "subjects" in subject_data:
            msg = (
                f"Config error: Subject '{subject_name}' cannot have "
                f"both 'tests' and 'subjects'."
            )
            raise ValueError(msg)

        subject = Subject(subject_name, subject_data.get("weight", 0))

        if "tests" in subject_data:
            parsed_tests = CriteriaTree._parse_tests(subject_data["tests"])
            executed_tests = []
            for test in parsed_tests:
                # Run method executes test, returns list of TestResult objs
                test_results = test.get_result(template, submission_files, subject_name)
                executed_tests.extend(test_results)
            # Store TestResult objects instead of Test objects
            subject.tests = executed_tests
        elif "subjects" in subject_data:
            child_subjects = [
                CriteriaTree._parse_and_execute_subject(
                    sub_name, sub_data, template, submission_files
                )
                for sub_name, sub_data in subject_data["subjects"].items()
            ]
            CriteriaTree._balance_subject_weights(child_subjects)
            subject.subjects = {s.name: s for s in child_subjects}
        else:
            subject.tests = []
        return subject

    @staticmethod
    def _parse_tests(test_data: list) -> List[Test]:
        """Parse a list of test definitions from the configuration."""
        parsed_tests = []
        for test_item in test_data:
            if isinstance(test_item, str):
                # Handle simple test names (e.g., "check_no_unclosed_tags")
                test = Test(name=test_item)  # Default file
                test.add_call(TestCall(args=[]))
                parsed_tests.append(test)

            elif isinstance(test_item, dict):
                # Handle complex test definitions
                test_name = test_item.get("name")
                test_file = test_item.get("file")
                if not test_name:
                    raise ValueError(f"Test definition is missing 'name': {test_item}")

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
        "test_library": "essay ai grader",
        "base": {
            "weight": 100,
            "subjects": {
                "foundations": {
                    "weight": 60,
                    "tests": [
                        {"file": "essay.txt", "name": "thesis_statement"},
                        {"file": "essay.txt", "name": "clarity_and_cohesion"},
                        {"file": "essay.txt", "name": "grammar_and_spelling"},
                    ],
                },
                "prompt_adherence": {
                    "weight": 40,
                    "tests": [
                        {
                            "file": "essay.txt",
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
                        {"file": "essay.txt", "name": "counterargument_handling"},
                        {"file": "essay.txt", "name": "vocabulary_and_diction"},
                        {"file": "essay.txt", "name": "sentence_structure_variety"},
                    ],
                },
                "deeper_analysis": {
                    "weight": 30,
                    "tests": [
                        {
                            "file": "essay.txt",
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
                        {"file": "essay.txt", "name": "logical_fallacy_check"},
                        {"file": "essay.txt", "name": "bias_detection"},
                        {"file": "essay.txt", "name": "originality_and_plagiarism"},
                    ],
                }
            },
        },
    }
    submission_files = {
        "essay.txt": """Artificial intelligence (AI) is no longer a concept
confined to science fiction; it is a transformative force actively reshaping
industries and redefining the nature of work. Its integration into the modern
workforce presents a profound duality: on one hand, it offers unprecedented
opportunities for productivity and innovation, while on the other, it poses
significant challenges related to job displacement and economic inequality.
Navigating this transition successfully requires a proactive and nuanced
approach from policymakers, businesses, and individuals alike.
The primary benefit of AI in the workplace is its capacity to augment human
potential and drive efficiency. AI-powered systems can analyze vast datasets
in seconds, automating routine cognitive and manual tasks, which frees human
workers to focus on more complex, creative, and strategic endeavors. For
instance, in medicine, AI algorithms assist radiologists in detecting tumors
with greater accuracy, while in finance, they identify fraudulent transactions
far more effectively than any human team. This collaboration between human and
machine not only boosts output but also creates new roles centered around AI
development, ethics, and system maintenance—jobs that did not exist a decade
ago.
However, this technological advancement casts a significant shadow of
disruption. The same automation that drives efficiency also leads to job
displacement, particularly for roles characterized by repetitive tasks.
Assembly line workers, data entry clerks, and even some paralegal roles face a
high risk of obsolescence. This creates a widening skills gap, where demand
for high-level technical skills soars while demand for traditional skills
plummets. Without robust mechanisms for reskilling and upskilling the existing
workforce, this gap threatens to exacerbate socio-economic inequality, creating
a divide between those who can command AI and those who are displaced by it.
There are many gramatical errors in this sentence, for testing purposes.
The most critical challenge, therefore, is not to halt technological progress
but to manage its societal impact. A multi-pronged strategy is essential.
Governments and educational institutions must collaborate to reform curricula,
emphasizing critical thinking, digital literacy, and lifelong learning.
Furthermore, corporations have a responsibility to invest in their employees
through continuous training programs. Finally, strengthening social safety
nets, perhaps through concepts like Universal Basic Income (UBI) or enhanced
unemployment benefits, may be necessary to support individuals as they navigate
this volatile transition period.
In conclusion, AI is a double-edged sword. Its potential to enhance
productivity and create new avenues for growth is undeniable, but so are the
risks of displacement and inequality. The future of work will not be a battle
of humans versus machines, but rather a story of adaptation. By investing in
education, promoting equitable policies, and fostering a culture of continuous
learning, we can harness the power of AI to build a more prosperous and
inclusive workforce for all."""
    }
    # tree = CriteriaTree.build_pre_executed_tree(
    #     criteria_json, WebDevLibrary(), submission_files
    # )
    tree = CriteriaTree.build_non_executed_tree(criteria_json)
    # tree.print_pre_executed_tree()
    tree.print_tree()
