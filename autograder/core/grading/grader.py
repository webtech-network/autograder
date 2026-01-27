import logging
from typing import List, Dict, Optional

from autograder.context import request_context
from autograder.builder.tree_builder import *
from autograder.core.models.result import Result
from autograder.core.models.test_result import TestResult

from autograder.core.models.result_tree import ResultNode, NodeType


logger = logging.getLogger(__name__)


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
        """
        Main entry point for grading.
        Returns a Result object with final_score and result_tree.
        """
        request = request_context.get_request()
        submission_files = request.submission_files
        author_name = request.student_name
        
        # Execute grading and build tree
        final_score, result_tree = self._run(submission_files)
        
        return Result(
            final_score=final_score,
            author=author_name,
            submission_files=submission_files,
            base_results=self.base_results,
            bonus_results=self.bonus_results,
            penalty_results=self.penalty_results,
            result_tree=result_tree
        )

    
    def _run(self, submission_files: Dict) -> Tuple[float, ResultNode]:
        """
        Runs the entire grading process and returns (final_score, result_tree).
        """
        logger.info("STARTING GRADING PROCESS")
        # Step 1: Grade categories. The methods will return None if no tests exist.
        ## CHANGED: Coalesce None to 0.0 to signify that an empty category contributes nothing to the score.
        base_score = self._grade_subject_or_category(self.criteria.base, submission_files, self.base_results) or 0.0
        bonus_score = self._grade_subject_or_category(self.criteria.bonus, submission_files, self.bonus_results) or 0.0
        penalty_points = self._calculate_penalty_points(self.criteria.penalty, submission_files,
                                                        self.penalty_results) or 0.0

        # Step 3: Apply the final scoring logic
        final_score = self._calculate_final_score(base_score, bonus_score, penalty_points)
        
        # Step 5: Update root node with final values
        root_node.weighted_score = final_score
        root_node.total_tests = (
            (base_node.total_tests if base_node else 0) +
            (bonus_node.total_tests if bonus_node else 0) +
            (penalty_node.total_tests if penalty_node else 0)
        )

        if root_node.children:
            print("Children:")
            for child in root_node.children:
                print(f"  - {child.name}: score={child.weighted_score}, tests={child.total_tests}")
        print("====================================\n")

        logger.info("GRADING COMPLETE")
        logger.info(f"Aggregated Base Score: {base_score:.2f}")
        logger.info(f"Aggregated Bonus Score: {bonus_score:.2f}")
        logger.info(f"Total Penalty Points to Subtract: {penalty_points:.2f}")
        logger.info(f"Final Calculated Score: {final_score:.2f}")

        return final_score, root_node
    
    def _grade_and_build(self,current_node, submission_files, result_list, node_name, node_type, depth=0) -> Tuple[Optional[float], Optional[ResultNode]]:
        


        result_node = ResultNode(
            node_type=node_type,
            name=node_name,
            weight=getattr(current_node, 'weight', 0.0),
            max_score=getattr(current_node, 'max_score', None)
        )

        prefix = "    " * depth

        if hasattr(current_node, 'tests') and current_node.tests:
            logger.debug(f"Grading {current_node.name}...")
            subject_test_results = []

            for test in current_node.tests:
                test_results = test.get_result(self.test_library, submission_files, current_node.name)
                subject_test_results.extend(test_results)

            if not subject_test_results:
                return None, None  # No tests were actually run

            result_list.extend(subject_test_results)
            result_node.test_results= subject_test_results
            result_node.total_tests= len(subject_test_results)

            #Calculate score
            scores = [res.score for res in subject_test_results]
            average_score = sum(scores) / len(scores)
            result_node.unweighted_score = average_score
            result_node.weighted_score = average_score
           

            print(f"{prefix}  -> Average score: {average_score:.2f}")
            print(f"{prefix} Built leaf node: {node_name} with {len(subject_test_results)} tests")

            return average_score, result_node


        child_subjects = getattr(current_node, 'subjects', {}).values()
        if not child_subjects:  
            return None, None

        print(f"\n{prefix}📘 Grading {current_node.name}...")

        child_results = []
        total_tests = 0
        valid_children = []

        for sub in child_subjects:
            child_score, child_node = self._grade_and_build(
                sub, submission_files, result_list, sub.name, NodeType.SUBJECT, depth + 1
            )

            if child_score is not None and child_node is not None:
                child_results.append((sub,child_score,child_node))
                total_tests += child_node.total_tests
                valid_children.append(child_node)

        if not valid_children:
            return None, None

        for _, _, child_node in child_results:
            result_node.add_child(child_node)

        result_node.total_tests = total_tests  


        total_weight = sum(sub.weight for sub, _, _ in child_results)

        if total_weight == 0:
            weighted_score = sum(score for _, score, _ in child_results) / len(child_results)

            unweighted_score = weighted_score

        else:
            weighted_score = 0
            unweighted_scores = []

            for sub, child_score, _ in child_results:
                weighted_score += child_score * (sub.weight / total_weight)
                unweighted_scores.append(child_score)

            unweighted_score = sum(unweighted_scores) / len(unweighted_scores)

        result_node.weighted_score = weighted_score
        result_node.unweighted_score = unweighted_score

        print(f"\n{prefix}  -> Weighted score for '{current_node.name}': {weighted_score:.2f}d")
        print(f"{prefix} Built branch node: {node_name} with {len(valid_children)} children, {total_tests} total tests")

        return weighted_score, result_node
    

    def _calculate_penalty_and_build(self,penalty_category, submission_files, result_list, node_name, node_type) -> Tuple[Optional[float], Optional[ResultNode]]:


        print(f"\n Penalizing {node_name}...")
        return self._calculate_subject_penalty_and_build(self, penalty_category, submission_files, result_list, node_name, node_type, depth=0)
        
    def _calculate_subject_penalty_and_build(self, subject, submission_files, result_list, node_name, node_type, depth=0) -> Tuple[Optional[float], Optional[ResultNode]]:
                            
        """ Helper method for calculating penalty while building result nodes"""

        result_node = ResultNode(
            node_type=node_type,
            name=node_name,
            weight=getattr(subject, 'weight', 0.0),
            max_score=getattr(subject, 'max_score', None)
        )

        prefix = "    " * depth

        if hasattr(subject, 'tests') and subject.tests:
            test_penalties = []
            test_results_all = []

            for test in subject.tests:
                test_results = test.get_result(self.test_library, submission_files, subject.name)

                if not test_results:
                    continue

                test_results_all.extend(test_results)
                result_list.extend(test_results)

                penalty_incurred = (100 - sum(res.score for res in test_results) / len(test_results))
                test_penalties.append(penalty_incurred)

               
            if not test_penalties:
                 return None, None  # Case when no test were actuallty run
                
            result_node.test_results = test_results_all
            result_node.total_tests = len(test_results_all)
          
            avg_penalty_for_subject = sum(test_penalties) / len(test_penalties)
            result_node.unweighted_score = avg_penalty_for_subject
            result_node.weighted_score = avg_penalty_for_subject


            print(f"{prefix}  -> Average penalty for '{subject.name}': {avg_penalty_for_subject:.2f}")
            print(f"{prefix}  Built penalty leaf node: {node_name} with {len(test_results_all)} tests")
            return avg_penalty_for_subject, result_node
        

        child_subjects_classes = getattr(subject, 'subjects', {})
        if not child_subjects_classes:
            return None, None  # No tests and no children
        
        child_subjects = child_subjects_classes.values()

        child_results = []
        total_tests = 0
        valid_children = []

        for sub in child_subjects:
            child_penalty, child_node = self._calculate_subject_penalty_and_build(
                sub, submission_files, result_list, sub.name, NodeType.SUBJECT, depth + 1
            )

            if child_penalty is not None and child_node is not None:
                child_results.append((sub,child_penalty,child_node))
                total_tests += child_node.total_tests
                valid_children.append(child_node)

        if not valid_children:
            return None, None  # No children had penalty tests
        
        for _, _, child_node in child_results:
            result_node.add_child(child_node)
        
        result_node.total_tests = total_tests

 
        total_weight = sum(sub.weight for sub, _, _ in child_results)

        if total_weight == 0:
            weighted_penalty = sum(penalty for _, penalty, _ in child_results) / len(child_results)

            unweighted_penalty = weighted_penalty

        else:
            weighted_penalty = 0
            unweighted_penalties = []

            for sub, child_penalty, _ in child_results:
                weighted_penalty += child_penalty * (sub.weight / total_weight)
                unweighted_penalties.append(child_penalty)

            unweighted_penalty = sum(unweighted_penalties) / len(unweighted_penalties)      

        result_node.weighted_score = weighted_penalty
        result_node.unweighted_score = unweighted_penalty

        print(f"\n{prefix}  -> Weighted penalty for '{subject.name}': {weighted_penalty:.2f}")
        print(f"{prefix}  Built penalty branch node: {node_name} with {len(valid_children)} children, {total_tests} total tests")
        return weighted_penalty, result_node


            


            

    
    
        




        

    ##def _grade_subject_or_category(self, current_node: 'Subject' or 'TestCategory', submission_files: Dict,
                                   results_list: List['TestResult'], depth=0) -> Optional[float]:
        """
        Recursively grades a subject or category, returning a weighted score or None if no tests are found.
        """
        prefix = "    " * depth

        # Base case: Node is a leaf with testss
        if hasattr(subject, 'tests') and subject.tests:
            print(f"\n{prefix}📘 Grading {subject.name}...")
            subject_test_results = []
            for test in subject.tests:
                test_results = test.get_result(self.test_library, submission_files, subject.name)
                subject_test_results.extend(test_results)

            if not subject_test_results:
                return None  # No tests were actually run

            result_list.extend(subject_test_results)
            scores = [res.score for res in subject_test_results]
            average_score = sum(scores) / len(scores)
            logger.debug(f"Average score: {average_score:.2f}")
            return average_score

        # Recursive case: Node is a branch (category or subject with sub-subjects)
        child_subjects_classes = getattr(current_node, 'subjects', {})
        if not child_subjects_classes:
            return None  # No tests and no children means this branch is empty
        child_subjects = child_subjects_classes.values()
        if not child_subjects:
            return None
        logger.debug(f"Grading {current_node.name}...")

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

        logger.debug(f"Weighted score for '{current_node.name}': {weighted_score:.2f}")
        return weighted_score

    def _calculate_penalty_points(self, penalty_category: 'TestCategory', submission_files: Dict,
                                  results_list: List['TestResult']) -> Optional[float]:
        """
        Calculates the total penalty points. Returns None if no penalty tests exist.
        """
        logger.debug(f"Penalizing {penalty_category.name}...")

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
            logger.debug(f"Average penalty for '{subject.name}': {avg_penalty_for_subject:.2f}")
            return avg_penalty_for_subject

        # Recursive Case: This node is a branch with children
        child_subjects_classes = getattr(subject, 'subjects', {})
        if not child_subjects_classes:
            return None  # No tests and no children
        child_subjects = child_subjects_classes.values()
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

        logger.debug(f"Weighted penalty for '{subject.name}': {weighted_penalty:.2f}")
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

        logger.debug("Applying Final Calculations:")
        logger.debug(f"  Base Score: {base_score:.2f}")
        logger.debug(f"  Bonus Points Added: {(bonus_score / 100) * bonus_weight:.2f}")
        logger.debug(f"  Score Before Penalty: {min(100.0, final_score + penalty_points_to_subtract):.2f}")
        logger.debug(f"  Penalty Points Subtracted: {penalty_points_to_subtract:.2f}")

        return max(0.0, final_score)
    
    def _build_result_node(
        self,
        criteria_node: 'Subject' or 'TestCategory',
        node_name: str,
        results_list: List['TestResult'],
        depth: int = 0
    ) -> Optional[ResultNode]:
        """
        Recursively builds the ResultNode tree from the criteria tree.
        """
        if depth == 0:
            node_type = NodeType.CATEGORY
        else:
            node_type = NodeType.SUBJECT
        
        result_node = ResultNode(
            node_type=node_type,
            name=node_name,
            weight=getattr(criteria_node, 'weight', 0.0),
            max_score=getattr(criteria_node, 'max_score', None)
        )
        
        # Base case: Leaf node with tests   
        if hasattr(criteria_node, 'tests') and criteria_node.tests:
            # Filter test results for this subject/category
            subject_tests = [
                tr for tr in results_list 
                if tr.subject_name == node_name
            ]
            
            if not subject_tests:
                return None
            
            result_node.test_results = subject_tests
            result_node.total_tests = len(subject_tests)
            
            # Calculate score(tests averages)
            scores = [tr.score for tr in subject_tests]
            avg_score = sum(scores) / len(scores)
            result_node.unweighted_score = avg_score
            result_node.weighted_score = avg_score
            
            print(f"{'    '*depth}Built leaf node: {node_name} with {len(subject_tests)} tests (avg: {avg_score:.2f})")
            return result_node
        
        child_subjects = getattr(criteria_node, 'subjects', {})
        
        if not child_subjects:
            return None
        
        
        total_tests = 0
        valid_children = []
        
        for sub_name, sub_node in child_subjects.items():
            child_result_node = self._build_result_node(
                sub_node,
                sub_name,
                results_list,
                depth + 1
            )
            
            if child_result_node: # Only add a children if it has tests 
                result_node.add_child(child_result_node)
                total_tests += child_result_node.total_tests
                valid_children.append(child_result_node)
        
        if not valid_children:
            return None
        
        result_node.total_tests = total_tests

        # Calculate weighted and unweighted scores
        total_weight = sum(child.weight for child in valid_children)
        
        if total_weight == 0:
            avg = sum(child.weighted_score for child in valid_children) / len(valid_children)
            result_node.weighted_score = avg
            result_node.unweighted_score = avg
        else:
            weighted = sum(
                child.weighted_score * (child.weight / total_weight)
                for child in valid_children
            )
            result_node.weighted_score = weighted
            result_node.unweighted_score = weighted
        
        print(f"{'    '*depth}Built branch node: {node_name} with {len(valid_children)} children, {total_tests} total tests")
        return result_node