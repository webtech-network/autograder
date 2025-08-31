# Assuming the data structure classes (TestResult, Criteria, etc.)
# and the test library are defined in other files as previously discussed.
from autograder.builder.models.criteria_tree import TestCategory
from autograder.builder.tree_builder import *
from autograder.builder.template_library.templates.web_dev import WebDevLibrary
from autograder.builder.tree_builder import custom_tree
from autograder.core.models.result import Result
from autograder.core.models.test_result import TestResult


class Grader:
    """
    Traverses a Criteria tree, executes tests, and calculates a weighted score.
    """

    def __init__(self, criteria_tree: 'Criteria', test_library: object):
        self.criteria = criteria_tree
        self.test_library = test_library
        # These lists will be populated with all individual test results
        self.base_results: List['TestResult'] = []
        self.bonus_results: List['TestResult'] = []
        self.penalty_results: List['TestResult'] = []

    def _run(self, submission_files: Dict) -> float:
        """
        Runs the entire grading process and returns the final calculated score.
        """
        print("\n--- STARTING GRADING PROCESS ---")
        # Step 1: Recursively grade each category to get their weighted scores (0-100)
        base_score = self._grade_subject_or_category(self.criteria.base, submission_files, self.base_results)
        bonus_score = self._grade_subject_or_category(self.criteria.bonus, submission_files, self.bonus_results)

        # Special handling for penalties. An empty penalty category should result in a score of 0.
        if not self.criteria.penalty.subjects:
            penalty_score = 0.0
        else:
            # If subjects exist, calculate the score, which represents the magnitude of the penalty.
            # A score of 100 means 100% of the penalty weight should be applied.
            penalty_score = self._grade_subject_or_category(self.criteria.penalty, submission_files, self.penalty_results)

        # Step 2: Apply the final scoring logic based on category outcomes
        final_score = self._calculate_final_score(base_score, bonus_score, penalty_score)

        print("\n--- GRADING COMPLETE ---")
        print(f"Aggregated Base Score: {base_score:.2f}")
        print(f"Aggregated Bonus Score: {bonus_score:.2f}")
        print(f"Aggregated Penalty Score: {penalty_score:.2f}")
        print("-" * 25)
        print(f"Final Calculated Score: {final_score:.2f}")
        print("-" * 25)

        return final_score

    def run(self, submission_files: Dict, author_name) -> 'Result':
        final_score = self._run(submission_files)
        return Result(final_score, author_name, submission_files, self.base_results, self.bonus_results, self.penalty_results)

    def _grade_subject_or_category(self, current_node: 'Subject' or 'TestCategory', submission_files: Dict,
                                   results_list: List['TestResult'], depth=0) -> float:
        """
        Recursively grades a subject or a category, calculating a weighted score.
        """
        prefix = "    " * depth
        print(f"\n{prefix}📘 Grading {current_node.name}...")

        # --- Base Case: This is a leaf-subject containing tests ---
        if hasattr(current_node, 'tests') and current_node.tests is not None:
            subject_test_results = []
            for test in current_node.tests:
                test_results = test.execute(self.test_library, submission_files, current_node.name)
                subject_test_results.extend(test_results)

            results_list.extend(subject_test_results)

            if not subject_test_results:
                print(f"{prefix}  -> No tests found. Score: 100.00")
                return 100.0

            # --- Pretty Print Test Score Averaging ---
            scores = [res.score for res in subject_test_results]
            average_score = sum(scores) / len(scores) if scores else 0.0
            calculation_str = " + ".join(map(str, scores))
            print(f"{prefix}  -> Calculating average of test scores:")
            print(f"{prefix}     ({calculation_str}) / {len(scores) if scores else 1} = {average_score:.2f}")
            return average_score

        # --- Recursive Step: This is a branch with sub-subjects ---
        child_subjects = current_node.subjects.values()
        if not child_subjects:
            print(f"{prefix}  -> No sub-subjects found. Score: 0.00")
            return 0.0

        total_weight = sum(sub.weight for sub in child_subjects)

        child_scores_map = {sub.name: self._grade_subject_or_category(sub, submission_files, results_list, depth + 1)
                            for sub in child_subjects}

        if total_weight == 0:
            # --- Pretty Print Simple Average for Unweighted Subjects ---
            scores = list(child_scores_map.values())
            average_score = sum(scores) / len(scores) if scores else 0.0
            calculation_str = " + ".join([f"{score:.2f}" for score in scores])
            print(f"\n{prefix}  -> Calculating simple average for unweighted subjects in '{current_node.name}':")
            print(f"{prefix}     ({calculation_str}) / {len(scores) if scores else 1} = {average_score:.2f}")
            return average_score

        # --- Pretty Print Weighted Score Calculation ---
        weighted_score = 0
        calculation_steps = []
        for sub in child_subjects:
            child_score = child_scores_map[sub.name]
            contribution = child_score * (sub.weight / total_weight)
            weighted_score += contribution
            calculation_steps.append(f"({child_score:.2f} * {sub.weight}/{total_weight})")

        calculation_str = " + ".join(calculation_steps)
        print(f"\n{prefix}  -> Calculating weighted score for '{current_node.name}':")
        print(f"{prefix}     {calculation_str} = {weighted_score:.2f}")
        return weighted_score

    def _calculate_final_score(self, base_score: float, bonus_score: float, penalty_score: float) -> float:
        """
        Applies the final scoring logic, mirroring your Scorer class.
        """
        bonus_weight = self.criteria.bonus.max_score
        penalty_weight = self.criteria.penalty.max_score

        final_score = base_score

        if final_score < 100:
            bonus_points_earned = (bonus_score / 100) * bonus_weight
            final_score += bonus_points_earned
            print(f"\nApplying Bonus: {base_score:.2f} + ({bonus_score:.2f}/100 * {bonus_weight}) = {final_score:.2f}")

        final_score = min(100.0, final_score)
        if final_score >= 100:
            print(f"Score capped at 100.00")
        penalty_points_to_subtract = (penalty_score / 100) * penalty_weight
        final_score -= penalty_points_to_subtract
        print(
            f"Applying Penalty: {min(100.0, base_score + (bonus_score / 100) * bonus_weight):.2f} - ({penalty_score:.2f}/100 * {penalty_weight}) = {final_score:.2f}")

        return max(0.0, final_score)
