from abc import ABC, abstractmethod
from typing import List, Dict

# Assuming these classes are in their respective, importable files
# from autograder.core.models.feedback_preferences import FeedbackPreferences
# from autograder.core.models.result import Result
# from autograder.builder.tree_builder import TestResult

class BaseReporter(ABC):
    """Abstract base class for reporting test results."""
    def __init__(self, result: 'Result', feedback: 'FeedbackPreferences'):
        self.result = result
        self.feedback = feedback
        # A map to quickly find learning resources for a given test name
        self._content_map = self._build_content_map()

    def _build_content_map(self) -> Dict[str, 'FeedbackPreferences.LearningResource']:
        """
        Creates a dictionary for fast lookups of learning resources by test name.
        This is a shared utility for any reporter.
        """
        content_map = {}
        for resource in self.feedback.general.online_content:
            for test_name in resource.linked_tests:
                content_map[test_name] = resource
        return content_map

    def _group_results_by_subject(self, results: List['TestResult']) -> Dict[str, List['TestResult']]:
        """
        Groups a flat list of TestResult objects into a dictionary keyed by subject name.
        This is a shared utility for any reporter.
        """
        grouped = {}
        for result in results:
            if result.subject_name not in grouped:
                grouped[result.subject_name] = []
            grouped[result.subject_name].append(result)
        return grouped

    @abstractmethod
    def generate_feedback(self):
        """Generate feedback based on the test results."""
        pass

    @classmethod
    def create(cls, result: 'Result', feedback: 'FeedbackPreferences'):
        response = cls(result, feedback)
        return response