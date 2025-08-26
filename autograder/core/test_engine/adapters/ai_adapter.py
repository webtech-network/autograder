import asyncio
from pydantic import BaseModel
from openai import OpenAI
from autograder.core.test_engine.engine_port import EnginePort
import os


class TestOutput(BaseModel):
    title: str
    status: str
    message: str
    subject: str

class AiEngine(EnginePort):
    """
    Adapter for the AI test engine, which performs text processing and prompt driven tests.
    """
    TEST_FILES = ["test_base.json", "test_bonus.json", "test_penalty.json"]

    # Pathing logic from the PytestAdapter for consistency.
    _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE_DIR)))
    VALIDATION_DIR = os.path.join(_PROJECT_ROOT, 'validation')
    REQUEST_BUCKET_DIR = os.path.join(_PROJECT_ROOT, 'request_bucket')
    RESULTS_DIR = os.path.join(VALIDATION_DIR, 'tests', 'results')
    SUBMISSION_DIR = os.path.join(REQUEST_BUCKET_DIR, 'submission')

    def __init__(self, openai_key=None):
        super().__init__()
        self.client = OpenAI(api_key=openai_key)

    async def _install_openai_dependency(self):
        """
        Installs the OpenAI Python library asynchronously if it's not already installed.
        """
        print("Checking and installing OpenAI dependency...")
        try:
            # Check if the openai library is installed using pip show
            check_proc = await asyncio.create_subprocess_exec(
                "pip", "show", "openai",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await check_proc.wait()

            if check_proc.returncode == 0:
                print("OpenAI library is already installed.")
            else:
                # If 'pip show' returns a non-zero code, the package is not installed.
                print("OpenAI library not found. Installing...")
                installer_proc = await asyncio.create_subprocess_exec(
                    "pip", "install", "openai",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await installer_proc.communicate()

                if installer_proc.returncode == 0:
                    print("OpenAI library installed successfully.")
                else:
                    print("Failed to install OpenAI library.")
                    print(f"STDERR: {stderr.decode().strip()}")
        except FileNotFoundError:
            # This would happen if 'pip' is not in the system's PATH.
            print("Error: 'pip' command not found. Please ensure Python and pip are installed correctly.")
        except Exception as e:
            print(f"An unexpected error occurred while installing OpenAI dependency: {e}")

    async def run_tests(self):
        """
        void -> str

        Runs all specified tests in the JSON test files in the following format:

        {
            'test': 'test_title',
            'prompt': 'prompt with test instructions'
        }

        Returns the AI prompt containing the results to all tests simultaneously in a batch

        :return: str
        """
        await self._install_openai_dependency()

        # Fetches user submission content by listing all files in the directory, opening them and adding their content to submission_content
        submission_content = ""
        if os.path.exists(self.SUBMISSION_DIR):
            submission_files = os.listdir(self.SUBMISSION_DIR)
            if submission_files:
                for filename in submission_files:
                    file_path = os.path.join(self.SUBMISSION_DIR, filename)
                    if os.path.isfile(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            submission_content += f"--- START OF FILE: {filename} ---\n"
                            submission_content += f.read()
                            submission_content += f"\n--- END OF FILE: {filename} ---\n\n"

        client = OpenAI()
        instructions = "Você é um corretor. Você receberá "
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                reasoning={"effort": "high"},
                instructions= instructions,
                input=[
                    {
                        "role": "system",
                        "content": instructions
                    },
                    {
                        "role": "tool",
                        "content": ""
                    }
                ],
                text_format=TestOutput
            )
            test_results = response.choices[0].message.content
            return test_results
        except Exception as e:
            print("")

    def normalize_output(self, report_paths: str):
        """
        str -> List[Dict[str]]

        Takes is the results from the test results given by the AI
        and puts them into the TestOutput format:

        {
           'title': 'test_title',
           'status': 'passed or failed',
           'message': 'short message about the test',
           'subject': 'test_subject'
        }

        The message should contain a short explanation on how and why the AI got that result, pinpointing specific
        sections of the submission. The other fields are self-explanatory

        :return:
        """
