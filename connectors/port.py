from abc import ABC, abstractmethod

from connectors.models.assignment_config import AssignmentConfig
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
    def create_request(self,
                       submission_files,
                       assignment_config: AssignmentConfig,
                       student_name,
                       student_credentials,
                       feedback_mode="default",
                       openai_key=None,
                       redis_url=None,
                       redis_token=None):
        """
        Abstract method to create an AutograderRequest object.
        This method should be implemented by the concrete Port classes.
        """
        pass

    @abstractmethod
    def create_custom_assignment_config(self, test_files,
                                       criteria,
                                       feedback,
                                       preset="custom",
                                       ai_feedback=None,
                                       test_framework="pytest"):
        """
        Abstract method to create an AssignmentConfig object.
        This method should be implemented by the concrete Port classes.
        """
        pass
