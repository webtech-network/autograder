"""
Deliberate Code Execution Schemas.

A Deliberate Code Execution is a feature that allows code execution without actually going through
the entire autograder pipeline, it is meant simply for running selected commands on sandboxed code
and returning the output. It does not grade nor generate scores, it is meant for debugging and testing purposes.

As of a first version (2026-02-23), the DCE feature won't support any kind of persistence, it is a 100% stateless
feature. It will not store anything for further queries.
"""

from pydantic import BaseModel, Field
from typing import List, Optional

from sandbox_manager.models.sandbox_models import ResponseCategory


class DeliberateCodeExecutionRequest(BaseModel):
    """
    Request schema for Deliberate Code Execution.
    """
    language: str = Field(..., description="The programming language of the code to be executed (e.g., python, java, node, cpp).")
    code: str = Field(..., description="The code to be executed.") # Change to submission files
    inputs: Optional[List[str]] = Field(None, description="Optional list of inputs to be provided to the code during execution.")

class DeliberateCodeExecutionResponse(BaseModel):
    """
    Response schema for Deliberate Code Execution.
    """
    output: str = Field(..., description="The output of the executed code.") #Outputs?
    category: ResponseCategory = Field(..., description="The category of the execution result (e.g., success, runtime_error, timeout, system_error).")
    error_message: Optional[str] = Field(None, description="Any error that occurred during execution.")