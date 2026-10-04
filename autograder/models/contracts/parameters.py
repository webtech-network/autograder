"""Strict authoring parameters for evaluators implemented with **kwargs."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Nonempty = Annotated[str, Field(min_length=1)]
LanguageId = Literal["python", "java", "node", "cpp", "c"]
Command = Nonempty | dict[LanguageId, Nonempty]


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ExpectOutputParameters(Parameters):
    inputs: list[str] = Field(default_factory=list)
    expected_output: str
    program_command: Command
    normalization: bool = True


class DontFailParameters(Parameters):
    user_input: str = ""
    program_command: Command


class ArtifactParameters(Parameters):
    inputs: list[str] = Field(default_factory=list)
    program_command: Command
    artifact_path: Nonempty
    expected_content: str
    match_mode: Literal["exact", "contains", "regex"] = "exact"
    normalization: bool = True

    @model_validator(mode="after")
    def validate_artifact(self):
        import re
        from pathlib import PurePosixPath
        if (self.artifact_path.startswith('/') or self.artifact_path == '.'
                or str(PurePosixPath(self.artifact_path)) != self.artifact_path
                or '..' in PurePosixPath(self.artifact_path).parts
                or '\\' in self.artifact_path or '\x00' in self.artifact_path):
            raise ValueError("artifact_path must be a normalized relative path without traversal or control characters")
        if self.match_mode == "regex":
            try:
                re.compile(self.expected_content)
            except re.error as exc:
                raise ValueError("expected_content must be a valid regular expression") from exc
        return self
