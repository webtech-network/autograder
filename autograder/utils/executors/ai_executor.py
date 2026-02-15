import json
from typing import List
from openai import OpenAI
from autograder.models.dataclass.test_result import TestResult
from pydantic import BaseModel, Field
from autograder.context import request_context
import dotenv
from autograder.utils.secrets_fetcher import get_secret

dotenv.load_dotenv()  # Load environment variables from .env file

request = request_context.get_request()
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
        # Fixed: Initialized submission_files as an empty dictionary
        self.submission_files = request.submission_files # Dict[filename:str, content:str]
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
            print("No test results to map back.")
            return

        for ai_result in self.test_results:
            # Find the corresponding TestResult reference by matching the test name
            matching_refs = [ref for ref in self.test_result_references if ref.test_name == ai_result.title]
            if matching_refs:
                ref = matching_refs[0]
                print("Found matching TestResult for AI result:",ref)
                ref.score = ai_result.score
                ref.report = ai_result.feedback
                print(f"Mapped AI result '{ai_result.title}' with score {ai_result.score} to TestResult.")
            else:
                print(f"No matching TestResult found for AI result '{ai_result.title}'.")



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

    def stop(self):
        tests = self._create_test_batch()
        submission_files = self._create_submission_files_string()
        system_prompt = f"""
                               Você é um assistente de avaliação de código especialista e rigoroso. Sua tarefa é avaliar os arquivos de uma submissão de usuário em relação a uma lista de testes.
                               Você DEVE responder com um único objeto JSON válido. Este objeto deve conter uma única chave, "results", que é um array de objetos de resultado de teste, um para cada teste fornecido.
                               NÃO inclua nenhum texto, explicação ou formatação fora do objeto JSON principal.
                               O esquema JSON para a sua resposta DEVE ser o seguinte:
                               {AIResponseModel.model_json_schema()}
                               lembre-se: os nomes dos testes devem corresponder exatamente aos nomes fornecidos na lista de testes. não mude a formatação ou a estrutura dos titulos dos tests.
                               """
        user_prompt = f"""
                                Por favor, avalie os arquivos de submissão do usuário abaixo em relação a todos os casos de teste listados.

                                ## ARQUIVOS DE SUBMISSÃO DO USUÁRIO ##
                                {submission_files}

                                ## CASOS DE TESTE PARA AVALIAR ##
                                {tests}
                                lembre-se: os nomes dos testes devem corresponder exatamente aos nomes fornecidos na lista de testes. não mude a formatação ou a estrutura dos titulos dos tests.

                              """
        print("System Prompt:\n", system_prompt)
        print("User Prompt:\n", user_prompt)
        try:
            print("Sending AI engine batch request...\n")
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
                print(f"""{test_result}\n""")
            self.mapback()

        except Exception as e:
            print(f"An error occurred while running the AI tests: {e}")
            return []


ai_executor = AiExecutor()



