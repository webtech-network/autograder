import inspect
import textwrap
from typing import List, Optional, Dict, Any
from fastapi import UploadFile

from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig
import json
from connectors.port import Port
import logging
from autograder.builder.template_library.library import TemplateLibrary
from autograder.context import request_context

class ApiAdapter(Port):

    def export_results(self):
        """
        Prepares the results of the autograding workfow as an API response.
        Also retrieves important data from the request (student_credentiaals)
        """
        if not self.autograder_response:
            raise Exception("No autograder response available. Please run the autograder first.")

        # Prepare the API response
        test_report = self.autograder_response.test_report
        response = {
            "server_status": "Server connection happened successfully",
            "autograding_status": self.autograder_response.status,
            "final_score": self.autograder_response.final_score,
            "feedback": self.autograder_response.feedback,
            "test_report": [test_result.to_dict() for test_result in test_report] if test_report else [],
        }

        return response

    async def create_request(self,
                       submission_files: List[UploadFile],
                       assignment_config: AssignmentConfig,
                       student_name,
                       student_credentials,
                       include_feedback=False,
                       feedback_mode="default"):
        submission_files_dict = {}
        for submission_file in submission_files:
            if ".git" in submission_file.filename:
                continue
            submission_content = await submission_file.read()
            submission_files_dict[submission_file.filename] =  submission_content.decode("utf-8")
        self.autograder_request = AutograderRequest(
            submission_files=submission_files_dict,
            assignment_config=assignment_config,
            student_name=student_name,
            student_credentials=student_credentials,
            include_feedback=include_feedback,
            feedback_mode=feedback_mode,
        )


    async def load_assignment_config(self, template: str, criteria: UploadFile, feedback: UploadFile,
                               setup: Optional[UploadFile] = None, custom_template: Optional[UploadFile] = None) -> AssignmentConfig:
        """
        Loads the assignment configuration based on the provided template preset.
        """
        logger = logging.getLogger(__name__)
        try:
            # Read and parse template name
            template_name = template
            logger.info(f"Template name: {template_name}")

            # Loads the raw json strings (template,criteria,feedback and setup) into dictionaries
            criteria_content = await criteria.read()
            criteria_dict = json.loads(criteria_content.decode("utf-8")) if criteria else None
            logger.info(f"Criteria loaded: {criteria_dict is not None}")

            feedback_content = await feedback.read()
            feedback_dict = json.loads(feedback_content.decode("utf-8")) if feedback else None
            logger.info(f"Feedback config loaded: {feedback_dict is not None}")

            setup_dict = None
            if setup:
                setup_content = await setup.read()
                setup_dict = json.loads(setup_content.decode("utf-8")) if setup else None
                logger.info(f"Setup config loaded: {setup_dict is not None}")
            custom_template_str = None
            if custom_template:
                custom_template_content = await custom_template.read()
                custom_template_str = custom_template_content.decode("utf-8")

            return AssignmentConfig(criteria=criteria_dict, feedback=feedback_dict, setup=setup_dict,
                                    template=template_name, custom_template_str = custom_template_str)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration files: {e}")
            raise ValueError(f"Invalid JSON format in configuration files: {e}")
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error reading configuration files: {e}")
            raise ValueError(f"Unable to decode configuration files: {e}")

    def get_template_info(self,template_name: str) -> Dict[str, Any]:
        """
        Retrieves a dictionary containing all the information of a Template,
        including its name, description, and full details for each test function
        (name, description, parameters, and source code).
        """

        request_context.set_request(AutograderRequest.build_empty_request())
        print("REQUEST_CONTEXT:", request_context.get_request())
        # 1. Retrieve an instance of the template from the library
        return TemplateLibrary.get_template_info(template_name)
        

    

if __name__ == "__main__":
    adapter = ApiAdapter()
    template_info = adapter.get_template_info("web dev")
    print(template_info)

