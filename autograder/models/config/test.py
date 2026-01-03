from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParameterConfig(BaseModel):
    """Named parameter for a test function."""

    name: str = Field(..., description="Parameter name")
    value: Any = Field(..., description="Parameter value")

    model_config = {"extra": "forbid"}


class TestConfig(BaseModel):
    """Configuration for a single test execution."""

    name: str = Field(..., description="Name of the test function in the template")
    file: Optional[str] = Field(
        None, description="Target file for the test (if applicable)"
    )
    parameters: Optional[List[ParameterConfig]] = Field(
        default_factory=list, description="Named parameters for the test function"
    )

    model_config = {"extra": "forbid"}

    def get_args_list(self) -> List[Any]:
        """Convert named parameters to positional arguments list."""
        if not self.parameters:
            return []
        return [param.value for param in self.parameters]

    def get_kwargs_dict(self) -> Dict[str, Any]:
        """Convert named parameters to keyword arguments dictionary."""
        if not self.parameters:
            return {}
        return {param.name: param.value for param in self.parameters}
