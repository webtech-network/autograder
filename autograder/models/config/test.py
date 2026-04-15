from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParameterConfig(BaseModel):
    """Named parameter for a test function."""

    name: str = Field(..., description="Parameter name")
    value: Any = Field(..., description="Parameter value")

    model_config = {"extra": "allow"}


class TestConfig(BaseModel):
    """Configuration for a single test execution."""

    name: str = Field(..., description="Display name of the test")
    type: Optional[str] = Field(
        None, description="Technical type of the test (e.g., expect_output)"
    )
    file: Optional[str] = Field(
        None, description="Target file for the test (if applicable)"
    )
    parameters: Optional[List[ParameterConfig]] = Field(
        None, description="Named parameters for the test function"
    )
    weight: Optional[float] = Field(100.0, ge=0, description="Weight of this test")


    model_config = {"extra": "allow"}


    def get_args_list(self) -> List[Any]:
        """Convert named parameters to positional arguments list."""
        if not self.parameters:
            return []
        return [param.value for param in self.parameters]

    def get_kwargs_dict(self) -> Dict[str, Any]:
        """Convert named parameters to keyword arguments dictionary."""
        kwargs = {}
        if self.parameters:
            kwargs.update({param.name: param.value for param in self.parameters})

        if self.model_extra:
            kwargs.update(self.model_extra)

        return kwargs
