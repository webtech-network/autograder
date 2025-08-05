import os
import aiofiles
from typing import List
from fastapi import UploadFile
from connectors.models.assignment_files import AssignmentFiles
from connectors.models.autograder_request import AutograderRequest
from autograder.autograder_facade import Autograder
from autograder.core.models.autograder_response import AutograderResponse
from connectors.models.autograder_request import AutograderRequest
from connectors.port import Port


class ApiAdapter(Port):

    # --- CORRECTED PATH ---
    # Dynamically determine the project's root directory from this file's location.
    # __file__ -> connectors/adapters/api/api_adapter.py
    # The project root is three levels up.
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    # Construct the full, correct path to the submission bucket.
    REQUEST_BUCKET_PATH = os.path.join(PROJECT_ROOT, "autograder", "request_bucket", "submission")
    # --- END CORRECTION ---




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

    def create_request(self,submission_files: List[UploadFile],criteria_json,feedback_json,
                       student_name,test_framework,feedback_mode,openai_key=None,
                       redis_url=None,redis_token=None,ai_feedback_json=None):

        submission_files_dict = {}
        for submission_file in submission_files:
            submission_files_dict[submission_file.filename] = submission_file

        assignment_files = AssignmentFiles(
            submission_files=submission_files_dict,
            criteria=criteria_json,
            feedback=feedback_json,
            ai_feedback=ai_feedback_json
        )
        self.autograder_request =  AutograderRequest(
            assignment_files,
            student_name,
            test_framework,
            feedback_mode,
            openai_key,
            redis_url,
            redis_token
        )
        return self
