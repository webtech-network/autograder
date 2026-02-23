from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict
import requests


class Language(Enum):
    PYTHON = ("python", "sandbox-py:latest")
    JAVA = ("java", "sandbox-java:latest")
    NODE = ("node", "sandbox-node:latest")
    CPP = ("cpp", "sandbox-cpp:latest")

    def __new__(cls, value, image):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.image = image
        return obj

class SandboxState(Enum):
    IDLE = "idle"
    BUSY = "busy"
    STOPPED = "stopped"

class ResponseCategory(Enum):
    SUCCESS = "success"             # Program ran and exited with 0
    RUNTIME_ERROR = "runtime_error" # Program crashed (e.g., Exception, Segmentation Fault)
    TIMEOUT = "timeout"             # Program was killed because it took too long
    SYSTEM_ERROR = "system_error"   # Infrastructure failure (e.g., Docker error)
    COMPILATION_ERROR = "compilation_error" # Specific to compiled languages like C++/Java

@dataclass
class CommandResponse:
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    # New field to hold the classification
    category: ResponseCategory = ResponseCategory.SUCCESS

    @property
    def output(self) -> str:
        return self.stdout

    def __str__(self):
        return self.stdout


class HttpResponse:
    """Wrapper for HTTP responses from containerized applications."""

    def __init__(self, response: requests.Response):
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def text(self) -> str:
        return self._response.text

    @property
    def headers(self) -> Dict[str, str]:
        return dict(self._response.headers)

    def json(self) -> Any:
        """Parse response body as JSON."""
        return self._response.json()

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def ok(self) -> bool:
        return self._response.ok

    def __repr__(self):
        return f"<HttpResponse [{self.status_code}]>"


