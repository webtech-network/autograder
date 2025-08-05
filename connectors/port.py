from abc import ABC, abstractmethod

from connectors.models.assignment_config import Preset
from models.autograder_request import AutograderRequest
from autograder.autograder_facade import Autograder


class Port(ABC):
    """
    Abstract Port class that defines the accepted interface for the core system communication.
    """
    def __init__(self):
        self.autograder_request = None
        self.autograder_response = None
    async def run_autograder(self):
        try:
            response = await Autograder.grade(self.autograder_request)
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
    def create_request(self, submission_files, preset: Preset,
                       student_name, test_framework, feedback_mode, openai_key=None,
                       redis_url=None, redis_token=None, ai_feedback_json=None) -> AutograderRequest:
        """
        Abstract method to create an AutograderRequest object.
        This method should be implemented by the concrete Port classes.
        """
        pass
