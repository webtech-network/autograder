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
            "server_status": "Sever connection happened successfully",
            "autograding_status": self.autograder_response.status,
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
            if ".git" in submission_file.filename:
                continue
            submission_content = await submission_file.read()
            submission_files_dict[submission_file.filename] =  submission_content.decode("utf-8")
        self.autograder_request =  AutograderRequest(
            submission_files_dict,
            assignment_config,
            student_name,
            feedback_mode=feedback_mode,
            openai_key=openai_key,
            redis_url=redis_url,
            redis_token=redis_token
        )


    async def load_assignment_config(self, template: str, criteria: UploadFile, feedback: UploadFile,
                               setup: Optional[UploadFile] = None) -> AssignmentConfig:
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

            return AssignmentConfig(criteria=criteria_dict, feedback=feedback_dict, setup=setup_dict,
                                    template=template_name)

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
        # 1. Retrieve an instance of the template from the library
        template_instance = TemplateLibrary.get_template(template_name)
        if not template_instance:
            raise ValueError(f"Template '{template_name}' not found.")

        # 2. Prepare the main dictionary with basic template info
        template_data = {
            "template_name": template_instance.template_name,
            "template_description": template_instance.template_description,
            "tests": []
        }

        # 3. Iterate through each test function in the template
        for test_name, test_instance in template_instance.get_tests().items():
            try:
                # 4. Use 'inspect' to get the source code of the 'execute' method
                source_code = inspect.getsource(test_instance.execute)
                # Use 'textwrap.dedent' to remove common leading whitespace
                cleaned_code = textwrap.dedent(source_code)
            except (TypeError, OSError):
                # Fallback in case the source code is not available
                cleaned_code = "Source code could not be retrieved."

            # 5. Build a dictionary for the current test function
            test_info = {
                "name": test_instance.name,
                "description": test_instance.description,
                "parameter_description": test_instance.parameter_description,
                "code": cleaned_code
            }
            template_data["tests"].append(test_info)

        return template_data


if __name__ == "__main__":
    adapter = ApiAdapter()
    template_info = adapter.get_template_info("web dev")
    print(template_info)

