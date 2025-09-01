from typing import List, Dict

# Assuming the data structure classes (TestResult, Criteria, etc.)
# and the test library are defined in other files as previously discussed.
from autograder.builder.tree_builder import *
from template_library.web_dev import WebDevLibrary
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
        self.base_results: List['TestResult'] = []
        self.bonus_results: List['TestResult'] = []
        self.penalty_results: List['TestResult'] = []

    def run(self, submission_files: Dict, author_name) -> 'Result':
        final_score = self._run(submission_files)
        return Result(final_score, author_name, submission_files, self.base_results, self.bonus_results,
                      self.penalty_results)

    def _run(self, submission_files: Dict) -> float:
        """
        Runs the entire grading process and returns the final calculated score.
        """
        print("\n--- STARTING GRADING PROCESS ---")
        # Step 1: Grade base and bonus categories to get their scores (0-100)
        base_score = self._grade_subject_or_category(self.criteria.base, submission_files, self.base_results)
        bonus_score = self._grade_subject_or_category(self.criteria.bonus, submission_files, self.bonus_results)

        # Step 2: Calculate the total penalty points incurred
        penalty_points = self._calculate_penalty_points(self.criteria.penalty, submission_files, self.penalty_results)

        # Step 3: Apply the final scoring logic
        final_score = self._calculate_final_score(base_score, bonus_score, penalty_points)

        print("\n--- GRADING COMPLETE ---")
        print(f"Aggregated Base Score: {base_score:.2f}")
        print(f"Aggregated Bonus Score: {bonus_score:.2f}")
        print(f"Total Penalty Points to Subtract: {penalty_points:.2f}")
        print("-" * 25)
        print(f"Final Calculated Score: {final_score:.2f}")
        print("-" * 25)

        return final_score

    def _grade_subject_or_category(self, current_node: 'Subject' or 'TestCategory', submission_files: Dict,
                                   results_list: List['TestResult'], depth=0) -> float:
        """
        Recursively grades a subject or category for BASE and BONUS, calculating a weighted score.
        """
        prefix = "    " * depth
        print(f"\n{prefix}📘 Grading {current_node.name}...")

        if hasattr(current_node, 'tests') and current_node.tests is not None:
            # ... (rest of the function is the same as before)
            subject_test_results = []
            for test in current_node.tests:
                test_results = test.execute(self.test_library, submission_files, current_node.name)
                subject_test_results.extend(test_results)
            results_list.extend(subject_test_results)
            if not subject_test_results: return 100.0
            scores = [res.score for res in subject_test_results]
            average_score = sum(scores) / len(scores) if scores else 0.0
            print(f"{prefix}  -> Average score: {average_score:.2f}")
            return average_score

        child_subjects = current_node.subjects.values()
        if not child_subjects: return 100.0

        total_weight = sum(sub.weight for sub in child_subjects)
        child_scores_map = {sub.name: self._grade_subject_or_category(sub, submission_files, results_list, depth + 1)
                            for sub in child_subjects}

        if total_weight == 0:
            scores = list(child_scores_map.values())
            return sum(scores) / len(scores) if scores else 0.0

        weighted_score = 0
        for sub in child_subjects:
            child_score = child_scores_map[sub.name]
            weighted_score += child_score * (sub.weight / total_weight)
        print(f"\n{prefix}  -> Weighted score for '{current_node.name}': {weighted_score:.2f}")
        return weighted_score

    def _calculate_penalty_points(self, penalty_category: 'TestCategory', submission_files: Dict,
                                  results_list: List['TestResult'], depth=0) -> float:
        """
        Recursively calculates the total penalty points incurred for the penalty category.
        """
        prefix = "    " * depth
        print(f"\n{prefix} Penalizing {penalty_category.name}...")

        child_subjects = penalty_category.subjects.values()
        if not child_subjects:
            return 0.0

        total_penalty = 0
        for subject in child_subjects:
            # The penalty for a subject is its weighted contribution to the total penalty
            subject_penalty = self._calculate_subject_penalty(subject, submission_files, results_list, depth + 1)
            total_penalty += subject_penalty

        return total_penalty

    def _calculate_subject_penalty(self, subject: 'Subject', submission_files: Dict, results_list: List['TestResult'],
                                   depth=0) -> float:
        """Helper to calculate penalty for a single subject."""
        prefix = "    " * depth

        if hasattr(subject, 'tests') and subject.tests is not None:
            # This is a leaf subject, calculate penalty from its tests
            test_penalties = []
            for test in subject.tests:
                test_results = test.execute(self.test_library, submission_files, subject.name)
                results_list.extend(test_results)
                # Penalty incurred = 100 - score. If score is 0, penalty is 100. If score is 100, penalty is 0.
                penalty_incurred = sum(100 - res.score for res in test_results) / len(test_results)
                test_penalties.append(penalty_incurred)

            if not test_penalties: return 0.0

            avg_penalty_for_subject = sum(test_penalties) / len(test_penalties)
            print(f"{prefix}  -> Average penalty for subject '{subject.name}': {avg_penalty_for_subject:.2f}")
            return avg_penalty_for_subject

        # This is a branch subject, calculate penalty from its children
        child_subjects = subject.subjects.values()
        if not child_subjects: return 0.0

        total_weight = sum(sub.weight for sub in child_subjects)
        if total_weight == 0: return 0.0

        weighted_penalty = 0
        for sub in child_subjects:
            child_penalty = self._calculate_subject_penalty(sub, submission_files, results_list, depth + 1)
            weighted_penalty += child_penalty * (sub.weight / total_weight)

        print(f"\n{prefix}  -> Weighted penalty for '{subject.name}': {weighted_penalty:.2f}")
        return weighted_penalty

    def _calculate_final_score(self, base_score: float, bonus_score: float, penalty_points: float) -> float:
        """
        Applies the final scoring logic with the corrected penalty calculation.
        """
        bonus_weight = self.criteria.bonus.max_score
        penalty_weight = self.criteria.penalty.max_score

        final_score = base_score

        if final_score < 100:
            bonus_points_earned = (bonus_score / 100) * bonus_weight
            final_score += bonus_points_earned

        final_score = min(100.0, final_score)

        # The penalty_points now represents the percentage of the total penalty to apply
        penalty_points_to_subtract = (penalty_points / 100) * penalty_weight
        final_score -= penalty_points_to_subtract

        print(f"\nApplying Final Calculations:")
        print(f"  Base Score: {base_score:.2f}")
        print(f"  Bonus Points Added: {(bonus_score / 100) * bonus_weight:.2f}")
        print(f"  Score Before Penalty: {min(100.0, final_score + penalty_points_to_subtract):.2f}")
        print(f"  Penalty Points Subtracted: {penalty_points_to_subtract:.2f}")

        return max(0.0, final_score)