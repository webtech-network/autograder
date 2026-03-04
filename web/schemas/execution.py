"""
Deliberate Code Execution Schemas.

A Deliberate Code Execution is a feature that allows code execution without actually going through
the entire autograder pipeline, it is meant simply for running selected commands on sandboxed code
and returning the output. It does not grade nor generate scores, it is meant for debugging and testing purposes.

As of a first version (2025-03-04), the DCE feature won't support any kind of persistence, it is a 100% stateless
feature. It will not store anything for further queries.
"""
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

from sandbox_manager.models.sandbox_models import ResponseCategory, Language
from web.schemas.submission import SubmissionFileData


class ExecutionStatus(str, Enum):
    """Status of an execution."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DeliberateCodeExecutionRequest(BaseModel):
    """
    Request schema for Deliberate Code Execution.
    """
    language: str = Field(..., description="The programming language of the code to be executed (e.g., python, java, node, cpp).")
    submission_files: List[SubmissionFileData] = Field(..., description="List of files to be executed, including their content.")
    program_command: str = Field(..., description="The command to execute the program (e.g., 'python main.py', 'java Main', 'node app.js', './a.out').")
    inputs: Optional[List[List[str]]] = Field(None, description="Optional list of inputs to be provided to the code during execution, one input may have multiple arguments.")

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


class DeliberateCodeExecutionResponse(BaseModel):
    """
    Response schema for Deliberate Code Execution.
    """
    output: str = Field(..., description="The output of the executed code.")
    category: ResponseCategory = Field(..., description="The category of the execution result (e.g., success, runtime_error, timeout, system_error).")
    error_message: Optional[str] = Field(None, description="Any error that occurred during execution.")
    execution_time: float = Field(..., description="Execution time in seconds.")

