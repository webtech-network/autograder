import os
import aiofiles
from typing import List
from fastapi import UploadFile

from autograder.autograder_facade import Autograder
from autograder.core.models.autograder_response import AutograderResponse
from connectors.port import Port


class ApiAdapter(Port):


    REQUEST_BUCKET_PATH = "home/autograder/request_bucket/submission"


    async def export_submission_files(self,submission_files:List[UploadFile]):
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
            "student_name": self.student_name,
            "student_credentials": self.student_credentials,
            "final_score": self.autograder_response.final_score,
            "feedback": self.autograder_response.feedback
        }

        return response


    def get_configuration_files(self):
        print("Getting configuration files for the API adapter.")

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