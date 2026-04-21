"""
Deliberate Code Execution Schemas.

A Deliberate Code Execution is a feature that allows code execution without actually going through
the entire autograder pipeline, it is meant simply for running selected commands on sandboxed code
and returning the output. It does not grade nor generate scores, it is meant for debugging and testing purposes.

As of a first version (2025-03-04), the DCE feature won't support any kind of persistence, it is a 100% stateless
feature. It will not store anything for further queries.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

from autograder.models.config.setup import AssetConfig
from sandbox_manager.models.sandbox_models import ResponseCategory, Language
from web.schemas.submission import SubmissionFileData


class DeliberateCodeExecutionRequest(BaseModel):
    """
    Request schema for Deliberate Code Execution.
    """
    language: str = Field(..., description="The programming language of the code to be executed (e.g., python, java, node, cpp).")
    submission_files: List[SubmissionFileData] = Field(..., description="List of files to be executed, including their content.")
    program_command: str = Field(..., description="The command to execute the program (e.g., 'python main.py', 'java Main', 'node app.js', './a.out').")
    test_cases: Optional[List[List[str]]] = Field(None, description="Optional list of test cases to be evaluated. Each test case is a list of inputs/arguments.")
    assets: Optional[List[AssetConfig]] = Field(default_factory=list, description="Optional list of assets to be injected into the sandbox before execution.")

    @field_validator('language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate that the language is supported."""
        # Normalize to uppercase for comparison
        language_upper = v.upper()

        # Check if language exists in Language enum
        valid_languages = [lang.name for lang in Language]
        if language_upper not in valid_languages:
            valid_languages_lower = [lang.value for lang in Language]
            raise ValueError(
                f"Unsupported language '{v}'. "
                f"Supported languages: {', '.join(valid_languages_lower)}"
            )
        return v


class DeliberateCodeExecutionResult(BaseModel):
    """
    Result of a single code execution block representing a test case.
    """
    output: str = Field(..., description="The output of the executed code.")
    category: ResponseCategory = Field(..., description="The category of the execution result (e.g., success, runtime_error, timeout, system_error).")
    error_message: Optional[str] = Field(None, description="Any error that occurred during execution.")
    execution_time: float = Field(..., description="Execution time in seconds.")


class DeliberateCodeExecutionResponse(BaseModel):
    """
    Response schema for Deliberate Code Execution containing all test cases evaluated.
    """
    results: List[DeliberateCodeExecutionResult] = Field(..., description="A list of execution results corresponding to each test case.")

