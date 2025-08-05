import os
import aiofiles
from typing import List
from fastapi import UploadFile
from connectors.models.autograder_request import AutograderRequest
from autograder.autograder_facade import Autograder
from autograder.core.models.autograder_response import AutograderResponse
from connectors.models.autograder_request import AutograderRequest
from connectors.models.preset import Preset
from connectors.models.test_files import TestFiles
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



    async def export_submission_files(self, submission_files: List[UploadFile]):
        """
        Saves the uploaded files to the request bucket.
        :param submission_files:
        :return:
        """
        os.makedirs(self.REQUEST_BUCKET_PATH, exist_ok=True)
        for file in submission_files:
            destination_path = os.path.join(self.REQUEST_BUCKET_PATH, file.filename)
            try:
                async with aiofiles.open(destination_path, 'wb') as out_file:
                    content = await file.read()
                    await out_file.write(content)
                print(f" - Saved {file.filename} to {destination_path}")
            except Exception as e:
                print(f"Error saving file {file.filename}: {e}")
            finally:
                await file.close()


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
            #"student_name": self.student_name,
            #"student_credentials": self.student_credentials,
            "final_score": self.autograder_response.final_score,
            "feedback": self.autograder_response.feedback
        }

        return response

    def create_request(self,submission_files: List[UploadFile],preset: Preset,
                       student_name,test_framework,feedback_mode,openai_key=None,
                       redis_url=None,redis_token=None,ai_feedback_json=None) -> AutograderRequest:

        submission_files_dict = {}
        for submission_file in submission_files:
            submission_files_dict[submission_file.filename] = submission_file


        return AutograderRequest(
            submission_files_dict,
            preset,
            student_name,
            test_framework,
            feedback_mode,
            openai_key,
            redis_url,
            redis_token
        )
