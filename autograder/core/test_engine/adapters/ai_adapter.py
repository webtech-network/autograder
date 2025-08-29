import asyncio
from pydantic import BaseModel, Field
from typing import List, Literal
from openai import OpenAI
from autograder.core.test_engine.engine_port import EnginePort
import os
import json

# Pydantic models to better structure the AI's input and output

class TestInput(BaseModel):
    """Defines the structure of a single test case from the JSON files."""
    test: str
    prompt: str

class TestOutput(BaseModel):
    """Defines the structure of a single test output"""
    title: str = Field(..., description="Title of the test being evaluated.")
    status: Literal["passed", "failed"] = Field(..., description="Result of the test.")
    message: str = Field(..., description="Description of why and how this response was achieved, pinpointing specific parts of the prompt that lead you to that conclusion.")
    subject: str = Field(..., description="The subject of the test, usually specified at the beginning of its title before a colon")

class AIResponseModel(BaseModel):
    """Defines the structure of a complete AI response"""
    results: List[TestOutput]

class AiEngine(EnginePort):
    """
    Adapter for the AI test engine, which performs text processing and prompt driven tests.
    """
    TEST_FILES = ["test_base.json", "test_bonus.json", "test_penalty.json"]

    # Pathing logic from the PytestAdapter for consistency.
    _THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE_DIR)))
    VALIDATION_DIR = os.path.join(_PROJECT_ROOT, 'validation') #I am assuming this is the DIR with the tests (I forgot which one it should come from, so it will probably change soon)
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

    async def run_tests(self) -> List[TestOutput]:
        """
        Runs all specified tests in the JSON test files in the following format:

        {
            'test': 'test_title',
            'prompt': 'prompt with test instructions'
        }

        Returns the AI strucutured output of the AI response

        :return: List[TestOutput]
        """

        # Start by installing the openai dependencies (although it seems to not be recommended, I followed the pattern of other adapters
        await self._install_openai_dependency()

        # Fetches the tests files, opens them and adds their content to the all_tests List (**still have to separate everything by file)
        all_tests: List[TestInput] = []
        for test_file in self.TEST_FILES:
            file_path = os.path.join(self.VALIDATION_DIR, test_file) # Change the usage of VALIDATION_DIR once the folder containing the tests is defined
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    tests_data = json.load(f)
                    all_tests.extend([TestInput(**test) for test in tests_data])
            except FileNotFoundError:
                print(f"Warning: Test file not found at {file_path}, skipping.")
            except Exception as e:
                print(f"Error reading or parsing {file_path}: {e}")

        if not all_tests:
            print("No test cases found. Aborting...")
            return []

        # Converts all tests to a single string
        tests_json_string = json.dumps([t.model_dump() for t in all_tests], indent=2)

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

        system_prompt = f"""
                Você é um assistente de avaliação de código especialista e rigoroso. Sua tarefa é avaliar os arquivos de uma submissão de usuário em relação a uma lista de testes.
                Você DEVE responder com um único objeto JSON válido. Este objeto deve conter uma única chave, "results", que é um array de objetos de resultado de teste, um para cada teste fornecido.
                NÃO inclua nenhum texto, explicação ou formatação fora do objeto JSON principal.
                O esquema JSON para a sua resposta DEVE ser o seguinte:
                {AIResponseModel.model_json_schema()}
                """

        user_prompt = f"""
                Por favor, avalie os arquivos de submissão do usuário abaixo em relação a todos os casos de teste listados.

                ## ARQUIVOS DE SUBMISSÃO DO USUÁRIO ##
                {submission_content}

                ## CASOS DE TESTE PARA AVALIAR ##
                {tests_json_string}
                """

        try:
            print("Sending AI engine batch request...")
            response = client.responses.create(
                model="gpt-4.1-mini", # Still have to do some research on the best model for this job. gpt-4o seems promising
                input=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                text_format={"type": "json_object"}
            )
            test_results = response.choices[0].message.content

            validated_output = AIResponseModel.model_validate_json(test_results)
            print("Successfully received and validated test results")

            return validated_output.results

        except Exception as e:
            print(f"An error occurred while running the AI tests: {e}")
            return []

    def normalize_output(self):
        pass
