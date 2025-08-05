from abc import ABC, abstractmethod
from models.autograder_request import AutograderRequest
from autograder.autograder_facade import Autograder


class Port(ABC):

    """
    Abstract Port class that defines the accepted interface for the core system communication.
    """
    def __init__(self):
        self.autograder_request = None
    async def run_autograder(self):
        try:
            response = await Autograder.grade(
                test_framework=self.test_framework,
                student_name=self.student_name,
                student_credentials=self.student_credentials,
                feedback_type=self.feedback_type,
                openai_key=self.openai_key,
                redis_url=self.redis_url,
                redis_token=self.redis_token
            )
            self.autograder_response = response
            return self
        except Exception as e:
            raise Exception(f"Error running autograder: {e}") from e


    @abstractmethod
    def export_results(self):
        """
        Abstract method to export the results of the autograder.
        This method should be implemented by the concrete Port classes.
        """
        pass

    @abstractmethod
    def create_request(self, submission_files, criteria_json, feedback_json, student_name,
                       test_framework, feedback_mode, openai_key=None, redis_url=None, redis_token=None,
                       ai_feedback_json=None) -> AutograderRequest:
        """
        Abstract method to create an AutograderRequest object.
        This method should be implemented by the concrete Port classes.
        """
        pass
