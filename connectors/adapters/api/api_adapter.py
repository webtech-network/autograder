from autograder.core.models.autograder_response import AutograderResponse
from connectors.port import Port


class ApiAdapter(Port):

    def export_results(self):
        """
        Prepares the results of the autograding workfow as an API response.
        Also retrieves important data from the request (student_credentiaals)
        """
        if not self.autograder_response:
            raise Exception("No autograder response available. Please run the autograder first.")

        # Prepare the API response
        response = {
            "status": "success",
            "student_name": self.student_name,
            "student_credentials": self.student_credentials,
            "final_score": self.autograder_response.final_score,
            "feedback": self.autograder_response.feedback
        }

        return response

    def run_autograder(self):
        """
        Runs the autograder workflow.
        This method should be implemented by the concrete Port classes.
        """
        # Here we would typically call the Autograder core logic
        # For now, we simulate a successful grading response
        self.autograder_response = AutograderResponse(100, "Your submission is perfect!")
        return self

    def get_configuration_files(self):
        print("Getting configuration files for the API adapter.")

    def get_submission_files(self):
        print("Getting submission files for the API adapter.")
    @classmethod
    def create(cls,test_framework,grading_preset,student_name,student_credentials,feedback_type,openai_key=None,redis_url=None,redis_token=None):
        """
        Factory method to create an instance of ApiAdapter.
        """
        return cls(
            test_framework=test_framework,
            student_name=student_name,
            grading_preset=grading_preset,
            feedback_type=feedback_type,
            student_credentials=student_credentials,
            openai_key=openai_key,
            redis_url=redis_url,
            redis_token=redis_token
        )