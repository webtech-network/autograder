from typing import List, Dict, Optional

from autograder.context import request_context
from autograder.builder.tree_builder import *
from autograder.core.models.result import Result
from autograder.core.models.test_result import TestResult


class Grader:
    """
    Traverses a Criteria tree, executes tests, and calculates a weighted score.
    Only includes scores from categories (base, bonus, penalty) that contain tests.
    """

    def __init__(self, criteria_tree: 'Criteria', test_library: object):
        self.criteria = criteria_tree
        self.test_library = test_library
        self.base_results: List['TestResult'] = []
        self.bonus_results: List['TestResult'] = []
        self.penalty_results: List['TestResult'] = []

    def run(self) -> 'Result':
        request = request_context.get_request()
        submission_files = request.submission_files
        author_name = request.student_name
        final_score = self._run(submission_files)
        return Result(final_score, author_name, submission_files, self.base_results, self.bonus_results,self.penalty_results)

    def _run(self, submission_files: Dict) -> float:
        """
        Runs the entire grading process and returns the final calculated score.
        """
        print("\n--- STARTING GRADING PROCESS ---")
        # Step 1: Grade categories. The methods will return None if no tests exist.
        ## CHANGED: Coalesce None to 0.0 to signify that an empty category contributes nothing to the score.
        base_score = self._grade_subject_or_category(self.criteria.base, submission_files, self.base_results) or 0.0
        bonus_score = self._grade_subject_or_category(self.criteria.bonus, submission_files, self.bonus_results) or 0.0
        penalty_percentage = self._calculate_penalty_points(self.criteria.penalty, submission_files,
                                                        self.penalty_results) or 0.0
        ## CHANGED: Switched the name of the variable "penalty_points" to "penalty_percentage" for further calcu 

        # Step 3: Apply the final scoring logic
        final_score = self._calculate_final_score(base_score, bonus_score, penalty_percentage)

        ## ADDED: Added calculations to the actual penalty points for accurate description
        penalty_weight = self.criteria.penalty.max_score
        penalty_points_to_subtract = (penalty_percentage / 100) * penalty_weight

        print("\n--- GRADING COMPLETE ---")
        print(f"Aggregated Base Score: {base_score:.2f}")
        print(f"Aggregated Bonus Score: {bonus_score:.2f}")
        print(f"Total Penalty Points to Subtract: {penalty_points_to_subtract:.2f}")
        print("-" * 25)
        print(f"Final Calculated Score: {final_score:.2f}")
        print("-" * 25)

        return final_score

    def _grade_subject_or_category(self, current_node: 'Subject' or 'TestCategory', submission_files: Dict,
                                   results_list: List['TestResult'], depth=0) -> Optional[float]:
        """
        Recursively grades a subject or category, returning a weighted score or None if no tests are found.
        """
        prefix = "    " * depth

        # Base case: Node is a leaf with tests
        if hasattr(current_node, 'tests') and current_node.tests:
            print(f"\n{prefix}📘 Grading {current_node.name}...")
            subject_test_results = []
            for test in current_node.tests:
                test_results = test.get_result(self.test_library, submission_files, current_node.name)
                subject_test_results.extend(test_results)

            if not subject_test_results:
                return None  # No tests were actually run

            results_list.extend(subject_test_results)
            scores = [res.score for res in subject_test_results]
            average_score = sum(scores) / len(scores)
            print(f"{prefix}  -> Average score: {average_score:.2f}")
            return average_score

        # Recursive case: Node is a branch (category or subject with sub-subjects)
        child_subjects = getattr(current_node, 'subjects', {}).values()
        if not child_subjects:
            return None  # No tests and no children means this branch is empty

        print(f"\n{prefix}📘 Grading {current_node.name}...")

        child_scores_map = {sub.name: self._grade_subject_or_category(sub, submission_files, results_list, depth + 1)
                            for sub in child_subjects}

        # Filter out children that had no tests (returned None)
        valid_children = [sub for sub in child_subjects if child_scores_map[sub.name] is not None]

        if not valid_children:
            return None  # No children in this branch contained any tests

        total_weight = sum(sub.weight for sub in valid_children)

        # If weights are 0, calculate a simple average of the valid children
        if total_weight == 0:
            scores = [child_scores_map[sub.name] for sub in valid_children]
            return sum(scores) / len(scores)

        # Otherwise, calculate the weighted score based only on valid children
        weighted_score = 0
        for sub in valid_children:
            child_score = child_scores_map[sub.name]
            weighted_score += child_score * (sub.weight / total_weight)

        print(f"\n{prefix}  -> Weighted score for '{current_node.name}': {weighted_score:.2f}")
        return weighted_score

    def _calculate_penalty_points(self, penalty_category: 'TestCategory', submission_files: Dict,
                                  results_list: List['TestResult']) -> Optional[float]:
        """
        Calculates the total penalty points. Returns None if no penalty tests exist.
        """
        print(f"\n Penalizing {penalty_category.name}...")

        # This is a simplified entry point; the main logic is in _calculate_subject_penalty
        # We treat the main penalty category like a subject to start the recursion.
        return self._calculate_subject_penalty(penalty_category, submission_files, results_list, depth=0)

    def _calculate_subject_penalty(self, subject: 'Subject', submission_files: Dict, results_list: List['TestResult'],
                                   depth=0) -> Optional[float]:
        """
        Helper to calculate penalty for a single subject or category.
        Returns penalty points (0-100) or None if no tests are found.
        """
        prefix = "    " * depth

        # Base Case: This node is a leaf with tests
        if hasattr(subject, 'tests') and subject.tests:
            test_penalties = []
            for test in subject.tests:
                test_results = test.get_result(self.test_library, submission_files, subject.name)
                if not test_results:
                    continue
                results_list.extend(test_results)
                # Penalty incurred = 100 - score
                penalty_incurred = (100 - sum(res.score for res in test_results) / len(test_results))
                test_penalties.append(penalty_incurred)

            if not test_penalties:
                return None  # No tests were actually run

            avg_penalty_for_subject = sum(test_penalties) / len(test_penalties)
            print(f"{prefix}  -> Average penalty for '{subject.name}': {avg_penalty_for_subject:.2f}")
            return avg_penalty_for_subject

        # Recursive Case: This node is a branch with children
        child_subjects = getattr(subject, 'subjects', {}).values()
        if not child_subjects:
            return None  # No tests and no children

        child_penalties_map = {sub.name: self._calculate_subject_penalty(sub, submission_files, results_list, depth + 1)
                               for sub in child_subjects}

        valid_children = [sub for sub in child_subjects if child_penalties_map[sub.name] is not None]

        if not valid_children:
            return None  # No children had penalty tests

        total_weight = sum(sub.weight for sub in valid_children)
        if total_weight == 0:
            penalties = [child_penalties_map[sub.name] for sub in valid_children]
            return sum(penalties) / len(penalties)  # Average of valid penalties

        weighted_penalty = 0
        for sub in valid_children:
            child_penalty = child_penalties_map[sub.name]
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