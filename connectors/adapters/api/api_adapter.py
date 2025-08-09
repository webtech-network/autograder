from typing import List
from fastapi import UploadFile
from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig
from connectors.models.test_files import TestFiles
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
            #"student_name": self.student_name,
            #"student_credentials": self.student_credentials,
            "final_score": self.autograder_response.final_score,
            "feedback": self.autograder_response.feedback
        }

        return response

    async def create_request(self,
                       submission_files: List[UploadFile],
                       assignment_config: AssignmentConfig,
                       student_name,
                       student_credentials,
                       feedback_mode="default",
                       openai_key=None,
                       redis_url=None,
                       redis_token=None):

        submission_files_dict = {}
        for submission_file in submission_files:
            submission_content = await submission_file.read()
            submission_files_dict[submission_file.filename] =  submission_content.decode("utf-8")

        print(f"Creating AutograderRequest with {feedback_mode} feedback mode")
        self.autograder_request =  AutograderRequest(
            submission_files_dict,
            assignment_config,
            student_name,
            feedback_mode=feedback_mode,
            openai_key=openai_key,
            redis_url=redis_url,
            redis_token=redis_token
        )
        print(f"AutograderRequest created with {self.autograder_request.feedback_mode} feedback mode")
    async def create_custom_assignment_config(self,
                                       test_files: List[UploadFile],
                                       criteria,
                                       feedback,
                                       preset="custom",
                                       ai_feedback=None,
                                       setup=None,
                                       test_framework="pytest"):
        files = TestFiles()
        for file in test_files:
            if file.filename.startswith("base_tests"):
                base_content = await file.read()
                files.test_base = base_content.decode("utf-8")
            elif file.filename.startswith("bonus_tests"):
                bonus_content = await file.read()
                files.test_bonus = bonus_content.decode("utf-8")
            elif file.filename.startswith("penalty_tests"):
                penalty_content = await file.read()
                files.test_penalty = penalty_content.decode("utf-8")
            elif file.filename.startswith("fatal_analysis"):
                fatal_content = await file.read()
                files.test_fatal_analysis = fatal_content.decode("utf-8")
            else:
                other_files_content = await file.read()
                files.other_files[file.filename] = other_files_content.decode("utf-8")
        return AssignmentConfig.load_custom(files,criteria,feedback,ai_feedback=ai_feedback,setup=setup,test_framework=test_framework)
