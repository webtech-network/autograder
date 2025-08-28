from abc import ABC, abstractmethod


class BaseReporter(ABC):
    """Abstract base class for reporting test results."""
    def __init__(self,result,feedback: FeedbackPreferences):
        self.result = result
        self.feedback_json = feedback
    @abstractmethod
    def generate_feedback(self):
        """Generate feedback based on the test results."""
        pass

    @classmethod
    def create(cls,result):
        response = cls(result)
        return response



