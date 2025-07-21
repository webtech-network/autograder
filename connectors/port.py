from abc import ABC, abstractmethod
from autograder.core.autograder_facade import Autograder

import os
import shutil
class Port(ABC):

    """
    Abstract Port class that defines the accepted interface for the core system communication.
    """
    def __init__(self,test_framework,grading_preset,student_name,student_credentials,feedback_type,openai_key=None,redis_url=None,redis_token=None):
        self.test_framework = test_framework
        self.grading_preset = grading_preset
        self.student_name = student_name
        self.student_credentials = student_credentials
        self.feedback_type = feedback_type
        self.openai_key = openai_key
        self.redis_url = redis_url
        self.redis_token = redis_token
        self.autograder_response = None

    @abstractmethod
    def get_submission_files(self):
        """
        Abstract method to get the submission files from the student.
        This method should be implemented by the concrete Port classes.
        """
        pass

    @abstractmethod
    def get_configuration_files(self):
        """
        Abstract method to get the configuration files for the autograder.
        This method should be implemented by the concrete Port classes.
        """
        pass

    def send_configuration_files(self):
        self.get_configuration_files()
        pass
    def send_submission_files(self):
        self.get_submission_files()
        pass

    def run_autograder(self):
        try:
            response = Autograder.grade(
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

if __name__ == "__main__":
    Port.import_preset("html-css-js")
