import json
import logging
from typing import List, Dict
from openai import OpenAI
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from pydantic import BaseModel, Field
import dotenv
from autograder.utils.secrets_fetcher import get_secret

logger = logging.getLogger(__name__)

dotenv.load_dotenv()  # Load environment variables from .env file

class TestInput(BaseModel):
    """
    This class represents the input of a single test to be sent to the AI model, defined using Pydantic.
    """
    test_name: str
    prompt: str


class TestOutput(BaseModel):
    """
    Defines the structure of a single test output from the AI model.
    """
    title: str = Field(..., description="Title of the test being evaluated.")
    feedback: str = Field(..., description="Description of why and how this response was achieved, pinpointing specific parts of the prompt that lead you to that conclusion.")
    subject: str = Field(..., description="The subject of the test, usually specified at the beginning of its title before a colon")
    score: float = Field(..., description="Based on whether the submission follows this correction criterion and how well it does, grade it from 0 to 100")


class AIResponseModel(BaseModel):
    """
    Defines the structure of the complete AI response, which contains a list of test results.
    """
    results: List[TestOutput] = Field(description="A list of test results each test performed following the TestOutput format")


class AiExecutor:
    """
    This class is responsible for encapsulating the OpenAI communication logic.
    It handles sending prompts to the AI model and receiving responses.
    The orientations toward the desired response format are also managed here.
    """

    def __init__(self):
        self.tests = []  # List[TestInput]
        self.test_result_references = []  # List[TestResult]
        self.submission_files: Dict[str, str] = {}  # Dict[filename:str, content:str]
        self.test_results = None  # The raw json response from the AI model.
        self.client = OpenAI(api_key=get_secret("OPENAI_API_KEY", "AUTOGRADER_OPENAI_KEY", "us-east-1"))

    def send_submission_files(self,submission_files):
        """Sets the submission files to be analyzed."""
        self.submission_files = submission_files
    def add_test(self, test_name: str,test_prompt: str):
        """Creates a Pydantic TestInput model and adds it to the test list."""
        test_input_model = TestInput(
            test_name=test_name,
            prompt=test_prompt
        )
        self.tests.append(test_input_model)
        empty_test_result = TestResult(
            test_name=test_name,
            score=0,
            report="",
            subject_name="",
            parameters={}
        )
        self.test_result_references.append(empty_test_result)
        return empty_test_result

    def mapback(self):
        """
        Maps each test result from the Ai response back to the corresponding TestResult reference in self.test_result_references.
           It finds the corresponding TestResult by matching the test name.
        """
        if not self.test_results:
            logger.warning("No test results to map back.")
            return

        for ai_result in self.test_results:
            # Find the corresponding TestResult reference by matching the test name
            matching_refs = [ref for ref in self.test_result_references if ref.test_name == ai_result.title]
            if matching_refs:
                ref = matching_refs[0]
                logger.debug("Found matching TestResult for AI result: %s", ref)
                ref.score = ai_result.score
                ref.report = ai_result.feedback
                logger.info("Mapped AI result '%s' with score %s to TestResult.", ai_result.title, ai_result.score)
            else:
                logger.warning("No matching TestResult found for AI result '%s'.", ai_result.title)



    def _create_test_batch(self):
        """
        Parses the added tests into a JSON string.

        The format for the JSON list is as follows:
        [
            {
                "test": "test_title",
                "prompt": "prompt with test instructions"
            },
            ...
        ]
        """
        # Create a list of dictionaries, one for each test
        test_batch_list = [
            {
                "test": test.test_name,
                "prompt": test.prompt
            }
            for test in self.tests
        ]

        # Convert the list of dictionaries to a JSON formatted string
        return json.dumps(test_batch_list, indent=4)

    def _create_submission_files_string(self):
        """
        Creates a string with all submission files and their content in the following format:
        filename:
        file content
        ____________________________
        filename2:
        .....
        """
        submission_files_str = ""
        for filename, content in self.submission_files.items():
            submission_files_str += f"{filename}:\n{content}\n{'_' * 30}\n"
        return submission_files_str

    def stop(self, locale: str = "en"):
        tests = self._create_test_batch()
        submission_files = self._create_submission_files_string()
        
        system_prompt = t("ai.system_prompt", locale=locale, json_schema=AIResponseModel.model_json_schema())
        user_prompt = t("ai.user_prompt", locale=locale, submission_files=submission_files, tests=tests)

        logger.debug("System Prompt:\n%s", system_prompt)
        logger.debug("User Prompt:\n%s", user_prompt)
        try:
            logger.info("Sending AI engine batch request...")
            response = self.client.responses.parse(
                model="o4-mini-2025-04-16",
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                text_format=AIResponseModel
            )

            # Extracts and logs the results
            self.test_results = response.output[1].content[0].parsed.results
            for test_result in self.test_results:
                logger.debug("AI test result: %s", test_result)
            self.mapback()
            return self.test_result_references

        except Exception as e:
            logger.error("An error occurred while running the AI tests: %s", e)
            return []


ai_executor = AiExecutor()
