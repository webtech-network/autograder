from pydantic import BaseModel, Field
from typing import List, Literal
from openai import OpenAI
from autograder.core.test_engine.engine_port import EnginePort
import os
import json
from pypdf import PdfReader
from pypdf.errors import PdfReadError

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
    score: float = Field(..., description="Based on whether the submission follows this correction criterion and how well it does, grade it from 0 to 100")

class AIResponseModel(BaseModel):
    """Defines the structure of a complete AI response"""
    results: List[TestOutput] = Field(description="A list of test results each test performed following the TestOutput format")


def fetch_pdf_text_content(file_path: str) -> str:
    """
    Receives the path to a pdf file and extracts all of its text content.

    This function opens a PDF file, iterates through all of its pages,
    and extracts the text from each page, concatenating it into a single string.

    :param file_path: The absolute or relative path to the PDF file.
    :return: A string containing all the text extracted from the PDF.
             Returns an error message if the file is not found or is not a valid PDF.
    """
    try:
        with open(file_path, 'rb') as file:
            reader = PdfReader(file)
            full_text = ""

            # Iterate through each page in the PDF and extracts its text
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text

            cleaned_full_text = full_text.replace("\n", "")
            return cleaned_full_text

    except FileNotFoundError:
        return f"Error: The file at '{file_path}' was not found."
    except PdfReadError:
        return f"Error: The file at '{file_path}' could not be read. It may be corrupted or not a valid PDF."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

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


    def run_tests(self) -> List[TestOutput]:
        """
        Runs all specified tests in the JSON test files in the following format:

        {
            'test': 'test_title',
            'prompt': 'prompt with test instructions'
        }

        Returns the AI strucutured output of the AI response

        :return: List[TestOutput]
        """


        # Fetches the tests files, opens them and adds their content to the all_tests List
        print("\nFetching test files...\n\n")
        all_tests: List[TestInput] = []
        for test_file in self.TEST_FILES:
            file_path = os.path.join(self.VALIDATION_DIR, test_file)
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

        # Converts all tests to a single string then logs it
        tests_json_string = json.dumps([t.model_dump() for t in all_tests], indent=2)
        print(f"""{tests_json_string}\n\n""")

        # Fetches user submission content by listing all files in the directory, opening them and adding their content to submission_content
        print("Fetching user submission content...\n\n")
        submission_content = ""
        if os.path.exists(self.SUBMISSION_DIR):
            submission_files = os.listdir(self.SUBMISSION_DIR)
            if submission_files:
                for filename in submission_files:
                    file_path = os.path.join("./submission", filename)
                    if os.path.isfile(file_path):
                        #Text content for that specific submission file.
                        #Checks if the file is a PDF and acts accordingly
                        submission_content += f"--- START OF FILE: {filename} ---\n"

                        _, file_extension = os.path.splitext(file_path)
                        if file_extension.lower() == '.pdf':
                            submission_content += fetch_pdf_text_content(file_path)
                        else:
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    submission_content += f.read()
                            except (UnicodeDecodeError, IOError) as e:
                                submission_content += f"Could not read file. Error: {e}\n"

                        submission_content += f"\n--- END OF FILE: {filename} ---\n\n"
        # Logs the submission content separated by file
        print(submission_content)


        api_key = os.getenv("OPENAI_KEY")
        client = OpenAI(api_key=api_key)

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

        # o4-mini was used as the model here due to it being a lightweight and relatively low cost, reasoning model.
        # It is a logical, fine-tuning prone model which is very open about its thought process, which is imperative
        # when providing complex reports containing reasons behind the decisions as we are doing.
        try:
            print("Sending AI engine batch request...\n")
            response = client.responses.parse(
                model="o4-mini-2025-04-16",
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user","content": user_prompt}
                ],
                text_format=AIResponseModel
            )

            # Extracts and logs the results
            test_results = response.output[1].content[0].parsed.results
            for test_result in test_results:
                print(f"""{test_result}\n""")

            return test_results

        except Exception as e:
            print(f"An error occurred while running the AI tests: {e}")
            return []

    def normalize_output(self):
        pass

