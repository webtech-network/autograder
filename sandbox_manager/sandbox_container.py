import os
import time
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING
from docker.models.containers import Container
import requests
from sandbox_manager.models.sandbox_models import Language, SandboxState, CommandResponse, HttpResponse, \
    ResponseCategory
from sandbox_manager.utils.classify_output import classify_output

if TYPE_CHECKING:
    from autograder.models.dataclass.asset import ResolvedAsset
    from autograder.models.dataclass.submission import SubmissionFile


class SandboxContainer:
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

        import base64

        try:
            for filename, submission_file in submission_files.items():
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
                        raise Exception(f"Failed to create directory {full_dir_path}")

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
                    raise Exception(f"Failed to create file {full_file_path}: {result.output}")

            self._workdir_prepared = True

        except Exception as e:
            raise Exception(f"Error preparing workdir: {str(e)}")

    def inject_assets(self, resolved_assets: List['ResolvedAsset']) -> None:
        """
        Inject resolved assets into the container under /tmp using Docker's put_archive.
        
        Args:
            resolved_assets: List of ResolvedAsset objects.
            
        Raises:
            Exception: If injection fails.
        """
        if not resolved_assets:
            return

        for asset in resolved_assets:
            # Ensure target path starts with /tmp/
            target_path = asset.target
            if not target_path.startswith('/tmp/'):
                target_path = os.path.join('/tmp', target_path.lstrip('/'))
            
            tar_content = asset.tar_content
            
            # Ensure parent directory exists in container
            parent_dir = os.path.dirname(target_path)
            if parent_dir and parent_dir != '/':
                self.container_ref.exec_run(
                    cmd=f"mkdir -p {parent_dir}",
                    user="root"
                )
            
            # Inject tar archive
            # path='/' because the tar content already contains the full target path
            success = self.container_ref.put_archive(
                path='/',
                data=tar_content
            )
            
            if not success:
                raise RuntimeError(f"Failed to inject asset to {target_path}")

    def run_command(self, command: str, timeout: int = 30, workdir: str = "/app") -> CommandResponse:
        """
        Execute a single command in the sandbox container.

        Args:
            command: The command to execute
            timeout: Maximum execution time in seconds (default: 30)
            workdir: Working directory for command execution (default: /app)

        Returns:
            CommandResponse with stdout, stderr, exit_code, and execution_time

        Raises:
            TimeoutError: If command execution exceeds timeout
            Exception: If command execution fails
        """
        import threading

        start_time = time.time()
        result_container = {'result': None, 'exception': None}

        def execute_command():
            try:
                # Wrap command in shell to support shell features like pipes, redirection, etc.
                shell_cmd = ["/bin/sh", "-c", command]

                # Execute command in container
                exec_result = self.container_ref.exec_run(
                    cmd=shell_cmd,
                    workdir=workdir,
                    user="sandbox",
                    demux=True,  # Separate stdout and stderr
                    environment={},
                    stdout=True,
                    stderr=True,
                    stdin=False
                )
                result_container['result'] = exec_result
            except Exception as e:
                result_container['exception'] = e

        # Execute in a thread with timeout
        thread = threading.Thread(target=execute_command)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        execution_time = time.time() - start_time

        # Check if thread is still running (timeout occurred)
        if thread.is_alive():
            # Timeout occurred
            return CommandResponse(
                stdout='',
                stderr=f'Execution timed out after {timeout} seconds',
                exit_code=124,  # Standard timeout exit code
                execution_time=execution_time,
                category=ResponseCategory.TIMEOUT
            )

        # Check if an exception occurred
        if result_container['exception']:
            return CommandResponse(
                stdout='',
                stderr=f'Command execution failed: {str(result_container["exception"])}',
                exit_code=-1,
                execution_time=execution_time,
                category=ResponseCategory.SYSTEM_ERROR
            )

        # Process successful execution
        result = result_container['result']
        if result is None:
            return CommandResponse(
                stdout='',
                stderr='Command execution failed: no result',
                exit_code=-1,
                execution_time=execution_time,
                category=ResponseCategory.SYSTEM_ERROR
            )

        # Demux returns tuple (stdout, stderr) if demux=True
        stdout_bytes, stderr_bytes = result.output if result.output else (b'', b'')

        # Decode output
        stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
        stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

        category = classify_output(stdout, stderr, result.exit_code, self.language)

        return CommandResponse(
            stdout=stdout,
            stderr=stderr,
            exit_code=result.exit_code,
            execution_time=execution_time,
            category=category  # Pass the classification
        )


    def run_commands(self, commands: List[str], program_command: str = None, timeout: int = 30, workdir: str = "/app") -> CommandResponse:
        """
        Execute a batch of commands with stdin input streaming for interactive programs.

        This is designed for programs that expect sequential stdin input, like:
        - Calculator: ["ADD", "10", "20"] -> expects "30"
        - Interactive prompts that read multiple inputs

        Args:
            commands: List of input strings to send to the program
            program_command: The program to run (e.g., "python3 calculator.py"). If None, uses stdin directly
            timeout: Maximum execution time in seconds (default: 30)
            workdir: Working directory for command execution (default: /app)

        Returns:
            CommandResponse with combined output
        """
        import threading

        start_time = time.time()
        result_container = {'result': None, 'exception': None}

        def execute_command():
            try:
                # Join all commands with newlines to create input
                stdin_input = '\n'.join(commands)

                if program_command:
                    # Execute program with stdin piped from echo
                    # This is more reliable than socket-based stdin
                    escaped_input = stdin_input.replace("'", "'\\''")
                    cmd = f"echo '{escaped_input}' | ( {program_command} )"
                    shell_cmd = ["/bin/sh", "-c", cmd]
                else:
                    # Just echo the input (for testing)
                    escaped_input = stdin_input.replace("'", "'\\''")
                    shell_cmd = ["/bin/sh", "-c", f"echo '{escaped_input}'"]

                # Execute command in container
                exec_result = self.container_ref.exec_run(
                    cmd=shell_cmd,
                    workdir=workdir,
                    user="sandbox",
                    demux=True,
                    stdout=True,
                    stderr=True,
                    stdin=False
                )
                result_container['result'] = exec_result
            except Exception as e:
                result_container['exception'] = e

        # Execute in a thread with timeout
        thread = threading.Thread(target=execute_command)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        execution_time = time.time() - start_time

        # Check if thread is still running (timeout occurred)
        if thread.is_alive():
            # Timeout occurred
            return CommandResponse(
                stdout='',
                stderr=f'Execution timed out after {timeout} seconds',
                exit_code=124,  # Standard timeout exit code
                execution_time=execution_time,
                category=ResponseCategory.TIMEOUT
            )

        # Check if an exception occurred
        if result_container['exception']:
            return CommandResponse(
                stdout='',
                stderr=f'Batch command execution failed: {str(result_container["exception"])}',
                exit_code=-1,
                execution_time=execution_time,
                category=ResponseCategory.SYSTEM_ERROR
            )

        # Process successful execution
        result = result_container['result']
        if result is None:
            return CommandResponse(
                stdout='',
                stderr='Batch command execution failed: no result',
                exit_code=-1,
                execution_time=execution_time,
                category=ResponseCategory.SYSTEM_ERROR
            )

        # Demux returns tuple (stdout, stderr) if demux=True
        stdout_bytes, stderr_bytes = result.output if result.output else (b'', b'')

        # Decode output
        stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
        stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''

        category = classify_output(stdout, stderr, result.exit_code, self.language)

        return CommandResponse(
            stdout=stdout,
            stderr=stderr,
            exit_code=result.exit_code,
            execution_time=execution_time,
            category=category
        )


    def make_request(self,
                     request_method: str,
                     endpoint: str,
                     data: Optional[dict] = None,
                     json_data: Optional[dict] = None,
                     headers: Optional[dict] = None,
                     timeout: int = 5) -> HttpResponse:
        """
        Make an HTTP request to a containerized web application.

        Args:
            request_method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path (e.g., '/api/users')
            data: Form data to send (for POST/PUT)
            json_data: JSON data to send (for POST/PUT)
            headers: Additional HTTP headers
            timeout: Request timeout in seconds (default: 5)

        Returns:
            HttpResponse wrapping the requests.Response

        Raises:
            ValueError: If port is not configured for this container
            requests.RequestException: If request fails
        """
        if self.port is None:
            raise ValueError("Container port not configured for HTTP requests")

        # Construct URL
        url = f"http://localhost:{self.port}{endpoint}"

        # Prepare headers
        request_headers = headers or {}

        # Make request based on method
        method = request_method.upper()

        try:
            if method == 'GET':
                response = requests.get(url, headers=request_headers, timeout=timeout)
            elif method == 'POST':
                if json_data:
                    response = requests.post(url, json=json_data, headers=request_headers, timeout=timeout)
                else:
                    response = requests.post(url, data=data, headers=request_headers, timeout=timeout)
            elif method == 'PUT':
                if json_data:
                    response = requests.put(url, json=json_data, headers=request_headers, timeout=timeout)
                else:
                    response = requests.put(url, data=data, headers=request_headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=request_headers, timeout=timeout)
            elif method == 'PATCH':
                if json_data:
                    response = requests.patch(url, json=json_data, headers=request_headers, timeout=timeout)
                else:
                    response = requests.patch(url, data=data, headers=request_headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            return HttpResponse(response)

        except requests.RequestException as e:
            # Re-raise with more context
            raise requests.RequestException(f"HTTP {method} request to {url} failed: {str(e)}")

    def __repr__(self):
        name = self.container_ref.name or "unnamed"
        return f"<SandboxContainer lang={self.language.value} state={self.state.value} name={name} id={self.container_ref.id[:12]}>"
