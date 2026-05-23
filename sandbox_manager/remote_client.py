import base64
from typing import Dict, List, TYPE_CHECKING
import requests
from contextlib import contextmanager

if TYPE_CHECKING:
    from autograder.models.dataclass.asset import ResolvedAsset
    from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.models.sandbox_models import (
    Language,
    CommandResponse,
    ExtractedFile,
    ResponseCategory,
    HttpResponse
)


class RemoteSandboxContainer:
    """
    Client wrapper for a remote SandboxContainer communicating via HTTP.
    Matches the interface of SandboxContainer.
    """
    def __init__(self, sandbox_id: str, language: Language, api_url: str):
        self.sandbox_id = sandbox_id
        self.language = language
        self.api_url = api_url.rstrip('/')
        self._session = requests.Session()

    def close(self):
        """Closes the HTTP session to prevent connection leaks."""
        self._session.close()

    def prepare_workdir(self, submission_files: Dict[str, 'SubmissionFile']) -> None:
        """Uploads submission files to the remote sandbox."""
        url = f"{self.api_url}/sandboxes/{self.sandbox_id}/prepare"
        files_data = {
            name: {
                "filename": sf.filename,
                "content": sf.content
            } for name, sf in submission_files.items()
        }
        response = self._session.post(url, json={"submission_files": files_data}, timeout=30)
        response.raise_for_status()

    def inject_assets(self, resolved_assets: List['ResolvedAsset']) -> None:
        """Injects resolved assets into the remote sandbox."""
        url = f"{self.api_url}/sandboxes/{self.sandbox_id}/inject"
        assets_data = [
            {
                "target": asset.target,
                "content": base64.b64encode(asset.content).decode('ascii'),
                "read_only": asset.read_only
            } for asset in resolved_assets
        ]
        response = self._session.post(url, json={"resolved_assets": assets_data}, timeout=30)
        response.raise_for_status()

    def run_command(self, command: str, timeout: int = 30, workdir: str = "/app") -> CommandResponse:
        """Executes a single command in the remote sandbox."""
        url = f"{self.api_url}/sandboxes/{self.sandbox_id}/run"
        payload = {
            "command": command,
            "timeout": timeout,
            "workdir": workdir
        }
        response = self._session.post(url, json=payload, timeout=timeout + 5)
        response.raise_for_status()
        data = response.json()
        return CommandResponse(
            stdout=data["stdout"],
            stderr=data["stderr"],
            exit_code=data["exit_code"],
            execution_time=data["execution_time"],
            category=ResponseCategory(data["category"])
        )

    def run_commands(self, commands: List[str], program_command: str = None, timeout: int = 30, workdir: str = "/app") -> CommandResponse:
        """Executes a batch of commands in the remote sandbox."""
        url = f"{self.api_url}/sandboxes/{self.sandbox_id}/run-batch"
        payload = {
            "commands": commands,
            "program_command": program_command,
            "timeout": timeout,
            "workdir": workdir
        }
        response = self._session.post(url, json=payload, timeout=timeout + 5)
        response.raise_for_status()
        data = response.json()
        return CommandResponse(
            stdout=data["stdout"],
            stderr=data["stderr"],
            exit_code=data["exit_code"],
            execution_time=data["execution_time"],
            category=ResponseCategory(data["category"])
        )

    def extract_file(self, path: str, max_bytes: int = 1_048_576) -> ExtractedFile:
        """Extracts a file from the remote sandbox."""
        url = f"{self.api_url}/sandboxes/{self.sandbox_id}/files"
        response = self._session.get(url, params={"path": path, "max_bytes": max_bytes}, timeout=30)
        if response.status_code == 404:
            raise FileNotFoundError(f"File not found in container: {path}")
        response.raise_for_status()
        data = response.json()
        
        content_bytes = base64.b64decode(data["content_bytes"])
        
        return ExtractedFile(
            path=data["path"],
            content_bytes=content_bytes,
            size=data["size"],
            content_text=data["content_text"],
            encoding=data["encoding"]
        )

    def make_request(self, method: str, endpoint: str, **kwargs) -> HttpResponse:
        """Sends an HTTP request to the remote sandbox."""
        url = f"{self.api_url}/sandboxes/{self.sandbox_id}/request"
        payload = {
            "method": method,
            "endpoint": endpoint,
            "kwargs": kwargs
        }
        timeout = kwargs.get("timeout", 30)
        if timeout is None:
            timeout = 30
        response = self._session.post(url, json=payload, timeout=timeout + 5)
        response.raise_for_status()
        data = response.json()
        
        # Build a dummy requests.Response object
        dummy_resp = requests.Response()
        dummy_resp.status_code = data["status_code"]
        dummy_resp._content = base64.b64decode(data["content"])
        dummy_resp.headers = data["headers"]
        # Setting a dummy url because requests uses it for things
        dummy_resp.url = f"http://dummy_remote_container{endpoint}"
        return HttpResponse(dummy_resp)


class RemoteSandboxManager:
    """
    Client wrapper for the SandboxManager communicating via HTTP.
    Matches the interface of SandboxManager.
    """
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip('/')
        self._session = requests.Session()

    def get_sandbox(self, lang: Language) -> RemoteSandboxContainer:
        """Acquires a sandbox from the remote pool."""
        url = f"{self.api_url}/sandboxes/{lang.value}"
        response = self._session.post(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return RemoteSandboxContainer(
            sandbox_id=data["sandbox_id"],
            language=lang,
            api_url=self.api_url
        )

    def release_sandbox(self, lang: Language, sandbox: RemoteSandboxContainer):
        """Releases the remote sandbox."""
        _ = lang  # unused but part of the interface
        url = f"{self.api_url}/sandboxes/{sandbox.sandbox_id}"
        response = self._session.delete(url, timeout=15)
        response.raise_for_status()
        sandbox.close()

    def destroy_sandbox(self, lang: Language, sandbox: RemoteSandboxContainer):
        """Destroys the remote sandbox immediately."""
        _ = lang  # unused but part of the interface
        url = f"{self.api_url}/sandboxes/{sandbox.sandbox_id}/destroy"
        response = self._session.delete(url, timeout=15)
        response.raise_for_status()
        sandbox.close()

    @contextmanager
    def acquire_sandbox(self, lang: Language):
        """Context manager for safe sandbox acquisition."""
        sandbox = self.get_sandbox(lang)
        try:
            yield sandbox
        finally:
            self.release_sandbox(lang, sandbox)

    def shutdown(self):
        """Shuts down the client session."""
        self._session.close()

    def get_pool_stats(self) -> dict:
        """Gets pool statistics from the remote API."""
        url = f"{self.api_url}/stats"
        response = self._session.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False
