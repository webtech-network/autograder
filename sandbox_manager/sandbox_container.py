import base64
import io
import os
import tarfile
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING
from docker.models.containers import Container
import requests
from sandbox_manager.models.sandbox_models import Language, SandboxState, CommandResponse, HttpResponse, \
    ResponseCategory, ExtractedFile
from sandbox_manager.utils.classify_output import classify_output

if TYPE_CHECKING:
    from autograder.models.dataclass.asset import ResolvedAsset
    from autograder.models.dataclass.submission import SubmissionFile


class SandboxContainer:
    """
    Manages a Docker container used as a sandbox for code execution.
    Handles file preparation, command execution, and file extraction.
    """
    def __init__(self, language: Language,
                 container_ref: Container,
                 port: int = None
                 ):
        self.language = language
        self.container_ref = container_ref
        self.port = port
        self.state = SandboxState.IDLE
        self.last_updated = datetime.now()
        self.created_at = datetime.now()
        self._workdir_prepared = False

    def pickup(self):
        """Mark sandbox as busy and update timestamp."""
        self.state = SandboxState.BUSY
        self.last_updated = datetime.now()

    def release(self):
        """Mark sandbox as idle and update timestamp."""
        self.state = SandboxState.IDLE
        self.last_updated = datetime.now()

    def prepare_workdir(self, submission_files: Dict[str, 'SubmissionFile']) -> None:
        """
        Copy submission files into the container's /app directory with smart directory structure.

        Files with paths like 'services/service.java' will be placed in /app/services/service.java,
        creating necessary parent directories.

        Args:
            submission_files: Dictionary mapping filenames to SubmissionFile objects

        Raises:
            Exception: If file copying fails
        """
        if not submission_files:
            return


        try:
            for submission_file in submission_files.values():
                file_path = submission_file.filename
                file_content = submission_file.content

                # Get the directory path
                dir_path = os.path.dirname(file_path) if '/' in file_path else ''

                # Create parent directories if needed
                if dir_path:
                    full_dir_path = f"/app/{dir_path}"
                    result = self.container_ref.exec_run(
                        cmd=f"mkdir -p {full_dir_path}",
                        user="sandbox"
                    )
                    if result.exit_code != 0:
                        raise RuntimeError(f"Failed to create directory {full_dir_path}")

                # Encode content as base64 to safely pass through shell
                content_b64 = base64.b64encode(file_content.encode('utf-8')).decode('ascii')

                # Create the file using base64 decode
                full_file_path = f"/app/{file_path}"
                cmd = f"echo '{content_b64}' | base64 -d > {full_file_path}"
                result = self.container_ref.exec_run(
                    cmd=["/bin/sh", "-c", cmd],
                    user="sandbox"
                )

                if result.exit_code != 0:
                    raise RuntimeError(f"Failed to create file {full_file_path}: {result.output}")

            self._workdir_prepared = True

        except Exception as e:
            raise RuntimeError(f"Error preparing workdir: {str(e)}") from e

    def inject_assets(self, resolved_assets: List['ResolvedAsset']) -> None:
        """
        Inject resolved assets into the container under /tmp using base64 and exec_run.
        
        Args:
            resolved_assets: List of ResolvedAsset objects.
            
        Raises:
            Exception: If injection fails.
        """
        if not resolved_assets:
            return

        import base64

        for asset in resolved_assets:
            # Ensure target path starts with /tmp/
            target_path = asset.target
            if not target_path.startswith('/tmp/'):
                target_path = os.path.join('/tmp', target_path.lstrip('/'))
            
            content = asset.content
            
            # Ensure parent directory exists in container and has correct permissions
            parent_dir = os.path.dirname(target_path)
            if parent_dir and parent_dir != '/':
                self.container_ref.exec_run(
                    cmd=f"mkdir -p {parent_dir}",
                    user="root"
                )
                # Ensure world-readable so sandbox user can read injected assets
                self.container_ref.exec_run(
                    cmd=f"chmod 755 {parent_dir}",
                    user="root"
                )
            
            # Encode content as base64 to safely pass through shell
            content_b64 = base64.b64encode(content).decode('ascii')

            # Create the file using base64 decode
            # Using /bin/sh -c to support redirection and pipes
            cmd = f"echo '{content_b64}' | base64 -d > {target_path}"
            result = self.container_ref.exec_run(
                cmd=["/bin/sh", "-c", cmd],
                user="root"
            )

            if result.exit_code != 0:
                output = result.output.decode() if result.output else "No output"
                raise RuntimeError(f"Failed to create asset file {target_path}: {output}")

            # Set file permissions (read-only if requested)
            mode = "444" if asset.read_only else "644"
            self.container_ref.exec_run(
                cmd=f"chmod {mode} {target_path}",
                user="root"
            )

    def _run_with_timeout(self, execute_fn, timeout: int):
        """Helper to run a function in a thread with a timeout."""
        start_time = time.time()
        container = {'result': None, 'exception': None}

        def target():
            try:
                container['result'] = execute_fn()
            except Exception as e:
                container['exception'] = e

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        execution_time = time.time() - start_time
        return container['result'], container['exception'], thread.is_alive(), execution_time

    def run_command(self, command: str, timeout: int = 30, workdir: str = "/app") -> CommandResponse:
        """
        Execute a single command in the sandbox container.
        """
        def execute():
            return self.container_ref.exec_run(
                cmd=["/bin/sh", "-c", command],
                workdir=workdir,
                user="sandbox",
                demux=True,
                stdout=True,
                stderr=True,
                stdin=False
            )

        result, exception, timed_out, exec_time = self._run_with_timeout(execute, timeout)

        if timed_out:
            return CommandResponse(
                stdout='', stderr=f'Execution timed out after {timeout} seconds',
                exit_code=124, execution_time=exec_time, category=ResponseCategory.TIMEOUT
            )

        if exception:
            return CommandResponse(
                stdout='', stderr=f'Command execution failed: {str(exception)}',
                exit_code=-1, execution_time=exec_time, category=ResponseCategory.SYSTEM_ERROR
            )

        if result is None:
            return CommandResponse(
                stdout='', stderr='Command execution failed: no result',
                exit_code=-1, execution_time=exec_time, category=ResponseCategory.SYSTEM_ERROR
            )

        stdout_bytes, stderr_bytes = result.output if result.output else (b'', b'')
        stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
        stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

        return CommandResponse(
            stdout=stdout, stderr=stderr, exit_code=result.exit_code,
            execution_time=exec_time,
            category=classify_output(stdout, stderr, result.exit_code, self.language)
        )


    def run_commands(self, commands: List[str], program_command: str = None, timeout: int = 30, workdir: str = "/app") -> CommandResponse:
        """
        Execute a batch of commands with stdin input streaming for interactive programs.
        """
        def execute():
            stdin_input = '\n'.join(commands)
            if program_command:
                escaped_input = stdin_input.replace("'", "'\\''")
                cmd = f"echo '{escaped_input}' | ( {program_command} )"
                shell_cmd = ["/bin/sh", "-c", cmd]
            else:
                escaped_input = stdin_input.replace("'", "'\\''")
                shell_cmd = ["/bin/sh", "-c", f"echo '{escaped_input}'"]

            return self.container_ref.exec_run(
                cmd=shell_cmd, workdir=workdir, user="sandbox",
                demux=True, stdout=True, stderr=True, stdin=False
            )

        result, exception, timed_out, exec_time = self._run_with_timeout(execute, timeout)

        if timed_out:
            return CommandResponse(
                stdout='', stderr=f'Execution timed out after {timeout} seconds',
                exit_code=124, execution_time=exec_time, category=ResponseCategory.TIMEOUT
            )

        if exception:
            return CommandResponse(
                stdout='', stderr=f'Batch command execution failed: {str(exception)}',
                exit_code=-1, execution_time=exec_time, category=ResponseCategory.SYSTEM_ERROR
            )

        if result is None:
            return CommandResponse(
                stdout='', stderr='Batch command execution failed: no result',
                exit_code=-1, execution_time=exec_time, category=ResponseCategory.SYSTEM_ERROR
            )

        stdout_bytes, stderr_bytes = result.output if result.output else (b'', b'')
        stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
        stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

        return CommandResponse(
            stdout=stdout, stderr=stderr, exit_code=result.exit_code,
            execution_time=exec_time,
            category=classify_output(stdout, stderr, result.exit_code, self.language)
        )


    def extract_file(self, path: str, max_bytes: int = 1_048_576) -> ExtractedFile:
        """
        Extract a single file from the container using Docker get_archive.

        Args:
            path: Absolute path inside the container (e.g. /app/output.txt).
            max_bytes: Maximum allowed file size in bytes (default 1 MB).

        Returns:
            ExtractedFile with content and metadata.

        Raises:
            FileNotFoundError: If the file does not exist in the container.
            ValueError: If the archive contains no regular file or file exceeds max_bytes.
            RuntimeError: If the tar stream cannot be read.
        """

        try:
            bits, _ = self.container_ref.get_archive(path)
        except Exception as e:
            if any(msg in str(e) for msg in ("404", "Not Found", "No such")):
                raise FileNotFoundError(f"File not found in container: {path}") from e
            raise RuntimeError(f"Failed to retrieve archive from container: {e}") from e

        try:
            raw = b"".join(bits)
            with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
                # Find the first regular file in the archive
                member = next((m for m in tar.getmembers() if m.isfile()), None)

                if member is None:
                    raise ValueError(f"No regular file found in archive for path: {path}")

                if member.size > max_bytes:
                    raise ValueError(
                        f"File exceeds maximum size: {member.size} bytes > {max_bytes} bytes"
                    )

                content_bytes = tar.extractfile(member).read()
        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to read tar stream: {e}") from e
        try:
            content_text = content_bytes.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            content_text = content_bytes.decode("latin-1")
            encoding = "latin-1"

        return ExtractedFile(
            path=path,
            content_bytes=content_bytes,
            size=len(content_bytes),
            content_text=content_text,
            encoding=encoding,
        )

    def make_request(self, method: str, endpoint: str, **kwargs) -> HttpResponse:
        """
        Make an HTTP request to a containerized web application.
        """
        if self.port is None:
            raise ValueError("Container port not configured for HTTP requests")

        url = f"http://localhost:{self.port}{endpoint}"
        method = method.upper()
        timeout = kwargs.pop('timeout', 5)

        try:
            # Map methods to requests functions
            method_map = {
                'GET': requests.get,
                'POST': requests.post,
                'PUT': requests.put,
                'DELETE': requests.delete,
                'PATCH': requests.patch,
            }

            if method not in method_map:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Extract any remaining kwargs as request parameters
            response = method_map[method](url, timeout=timeout, **kwargs)
            return HttpResponse(response)

        except requests.RequestException as e:
            raise requests.RequestException(f"HTTP {method} request to {url} failed: {str(e)}") from e

    def __repr__(self):
        name = self.container_ref.name or "unnamed"
        return f"<SandboxContainer lang={self.language.value} state={self.state.value} name={name} id={self.container_ref.id[:12]}>"
