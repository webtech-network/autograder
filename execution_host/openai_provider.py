import json
import logging
from typing import List, Mapping, Sequence

import httpx
from openai import OpenAI
from autograder.models.execution import AssessmentRequest, ProviderAssessment
from autograder.translations import t
from pydantic import BaseModel, Field
from execution_host.secrets import fetch_secret
from autograder.models.evaluation_error import EvaluationError

logger = logging.getLogger(__name__)

# The one AI request a grading makes is bounded by these waits and never retried
# by the SDK (whose defaults are a 600 s read and two retries). A provider that
# stops responding fails the grading with PROVIDER_ERROR after at most
# CONNECT_TIMEOUT_SECONDS + REQUEST_TIMEOUT_SECONDS; recovery is the host's choice.
REQUEST_TIMEOUT_SECONDS = 180.0
CONNECT_TIMEOUT_SECONDS = 10.0


def openai_client(api_key, *, base_url=None, timeout=REQUEST_TIMEOUT_SECONDS):
    """One reusable client: explicit deadline, zero SDK retries."""
    return OpenAI(api_key=api_key, base_url=base_url, max_retries=0,
                  timeout=httpx.Timeout(timeout, connect=min(CONNECT_TIMEOUT_SECONDS, timeout)))


class TestOutput(BaseModel):
    """One assessment returned by the AI model for one requested criterion."""

    criterion_id: str = Field(..., description="The criterion_id of the assessed test, copied exactly.")
    feedback: str = Field(..., description="Description of why and how this response was achieved, pinpointing specific parts of the prompt that lead you to that conclusion.")
    score: float = Field(..., ge=0, le=100, strict=True, allow_inf_nan=False, description="Assessment from 0 to 100")


class AIResponseModel(BaseModel):
    """Top-level structure of the complete AI response."""

    results: List[TestOutput] = Field(description="A list of test results each test performed following the TestOutput format")


def resolve_api_key(*, api_key, secret_name, region, secret_source=None):
    """Return the configured key, or look it up once in the host's secret store."""
    if api_key is None and secret_name:
        api_key = (secret_source or fetch_secret)(secret_name, "OPENAI_API_KEY", region)
    if not api_key:
        raise ValueError("An assessment credential is required")
    return api_key


class AiExecutor:
    """OpenAI ``AssessmentProvider`` over one reusable client: one request per batch, no retries.

    The engine validates exact criterion-ID coverage and scores of the returned
    assessments; this adapter only translates the model's structured output.
    """

    def __init__(self, client, model) -> None:
        self.client = client
        self.model = model

    def assess(
        self,
        requests: Sequence[AssessmentRequest],
        *,
        context_files: Mapping[str, str],
        locale: str = "en",
    ) -> List[ProviderAssessment]:
        """Send one batch of criteria to the AI model and return its assessments."""
        if not requests:
            return []

        test_batch_str = self._build_test_batch_string(requests)
        files_str = self._build_submission_files_string(context_files)

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
            logger.info("Sending AI engine batch request (%d criteria)…", len(requests))
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=AIResponseModel,
            )
            parsed = response.output_parsed
        except Exception as e:
            logger.error("AI batch request failed: %s", e)
            raise EvaluationError("PROVIDER_ERROR", "The assessment provider could not complete evaluation.", "provider", True) from e
        if parsed is None:
            raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required AI assessment was not returned.", "provider", True)
        return [ProviderAssessment(criterion_id=output.criterion_id, score=output.score, report=output.feedback)
                for output in parsed.results]

    @staticmethod
    def _build_test_batch_string(requests: Sequence[AssessmentRequest]) -> str:
        """Serialise criteria to a JSON string for the user prompt."""
        return json.dumps(
            [{"criterion_id": request.criterion_id, "prompt": request.prompt} for request in requests],
            indent=4,
        )

    @staticmethod
    def _build_submission_files_string(submission_files: Mapping[str, str]) -> str:
        """Format submission files as a readable block for the AI prompt."""
        parts = []
        for filename, content in submission_files.items():
            parts.append(f"{filename}:\n{content}\n{'_' * 30}")
        return "\n".join(parts)
