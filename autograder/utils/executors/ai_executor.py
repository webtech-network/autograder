import json
import logging
from typing import Dict, List
from openai import OpenAI
from autograder.models.dataclass.test_result import TestResult
from autograder.translations import t
from pydantic import BaseModel, Field
import dotenv
from autograder.utils.secrets_fetcher import get_secret
from autograder.models.evaluation_error import EvaluationError

logger = logging.getLogger(__name__)

dotenv.load_dotenv()  # Load environment variables from .env file


class TestInput(BaseModel):
    """Input descriptor for a single AI-evaluated test."""

    test_name: str
    prompt: str


class TestOutput(BaseModel):
    """Structure of a single test result returned by the AI model."""

    title: str = Field(..., description="Title of the test being evaluated.")
    feedback: str = Field(..., description="Description of why and how this response was achieved, pinpointing specific parts of the prompt that lead you to that conclusion.")
    subject: str = Field(..., description="The subject of the test, usually specified at the beginning of its title before a colon")
    score: float = Field(..., ge=0, le=100, strict=True, allow_inf_nan=False, description="Assessment from 0 to 100")


class AIResponseModel(BaseModel):
    """Top-level structure of the complete AI response."""

    results: List[TestOutput] = Field(description="A list of test results each test performed following the TestOutput format")


class AiExecutor:
    """
    Stateless OpenAI communication wrapper.
    """

    def __init__(self) -> None:
        try:
            self.client = OpenAI(api_key=get_secret("OPENAI_API_KEY", "AUTOGRADER_OPENAI_KEY", "us-east-1"))
        except Exception as exc:
            logger.exception("Assessment provider initialization failed")
            raise EvaluationError("PROVIDER_UNAVAILABLE", "The assessment provider is unavailable.", "provider") from exc

    def run(
        self,
        tests: List[TestInput],
        submission_files: Dict[str, str],
        locale: str = "en",
    ) -> Dict[str, TestResult]:
        """ 
        Send a batch of tests to the AI model and return their results.
        """
        if not tests:
            return {}

        test_batch_str = self._build_test_batch_string(tests)
        files_str = self._build_submission_files_string(submission_files)

        system_prompt = t(
            "ai.system_prompt",
            locale=locale,
            json_schema=AIResponseModel.model_json_schema(),
        )
        user_prompt = t(
            "ai.user_prompt",
            locale=locale,
            submission_files=files_str,
            tests=test_batch_str,
        )

        logger.debug("System Prompt:\n%s", system_prompt)
        logger.debug("User Prompt:\n%s", user_prompt)

        try:
            logger.info("Sending AI engine batch request (%d tests)…", len(tests))
            response = self.client.responses.parse(
                model="o4-mini-2025-04-16",
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=AIResponseModel,
            )

            parsed = response.output_parsed
            if parsed is None:
                raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required AI assessment was not returned.", "provider", True)
            ai_outputs: List[TestOutput] = parsed.results
            return self._outputs_to_results(tests, ai_outputs)

        except EvaluationError:
            raise
        except Exception as e:
            logger.error("AI batch request failed: %s", e)
            raise EvaluationError("PROVIDER_ERROR", "The assessment provider could not complete evaluation.", "provider", True) from e


    @staticmethod
    def _build_test_batch_string(tests: List[TestInput]) -> str:
        """Serialise tests to a JSON string for the user prompt."""
        return json.dumps(
            [{"test": t.test_name, "prompt": t.prompt} for t in tests],
            indent=4,
        )

    @staticmethod
    def _build_submission_files_string(submission_files: Dict[str, str]) -> str:
        """Format submission files as a readable block for the AI prompt."""
        parts = []
        for filename, content in submission_files.items():
            parts.append(f"{filename}:\n{content}\n{'_' * 30}")
        return "\n".join(parts)

    @staticmethod
    def _outputs_to_results(
        tests: List[TestInput], outputs: List[TestOutput]
    ) -> Dict[str, TestResult]:
        """Convert AI outputs to TestResult objects, matched by test name."""
        input_names = {t.test_name for t in tests}
        if len(input_names) != len(tests):
            raise EvaluationError("INVALID_DEFINITION", "AI criterion identities must be unique.", "definition")
        results: Dict[str, TestResult] = {}

        for output in outputs:
            logger.debug("AI test result: %s", output)
            if output.title in input_names:
                if output.title in results:
                    raise EvaluationError("INVALID_EVALUATOR_RESULT", "The assessment provider returned duplicate assessments.", "provider", True)
                results[output.title] = TestResult(
                    test_name=output.title,
                    score=output.score,
                    report=output.feedback,
                    subject_name=output.subject,
                    parameters={},
                )
            else:
                raise EvaluationError("INVALID_EVALUATOR_RESULT", "The assessment provider returned an unknown assessment.", "provider", True)

        if set(results) != input_names:
            raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required AI assessment was not returned.", "provider", True)
        return results
