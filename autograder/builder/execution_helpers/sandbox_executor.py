import docker
import tarfile
import io
import logging
import os
import time
import requests
from requests.exceptions import ConnectionError
from autograder.context import request_context
from autograder.builder.execution_helpers.base import ExecutionHelper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SandboxExecutor(ExecutionHelper):
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self.target_host = os.getenv("TARGET_HOST")
        self.target_port = os.getenv("TARGET_AGENT_PORT", "8080")
        
        if self.target_host:
            self.mode = "PROXY"
            self.base_url = f"http://{self.target_host}:{self.target_port}"
        else:
            self.mode = "LOCAL"
            self.image = config.get("runtime_image")
            if not self.image:
                raise ValueError("'runtime_image' must be specified in setup.json for LOCAL mode")
            self.client = docker.from_env()
            self.container = None
            self.mapped_ports = {}

    @classmethod
    def start(cls, **config):
        if not config:
            request = request_context.get_request()
            config = request.assignment_config.setup
            if not config:
                raise ValueError("setup.json configuration is missing")
        
        instance = cls(config)
        
        if instance.mode == "PROXY":
            print(f"[SandboxExecutor] Connecting to Student container at {instance.base_url}...")
            instance._wait_for_agent_startup()
            print("[SandboxExecutor] Connected.")
        elif instance.mode == "LOCAL":
            instance._start_container()
            
        return instance

    def stop(self):
        if self.mode == "LOCAL" and self.container:
            try:
                self.logger.info(f"Stopping container {self.container.short_id}...")
                self.container.remove(force=True)
                self.logger.info("Container stopped and removed")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
            finally:
                self.container = None

    def _wait_for_agent_startup(self, timeout=30):
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                requests.get(self.base_url, timeout=1)
                return
            except ConnectionError:
                time.sleep(1)
        
        raise TimeoutError(f"Agent at {self.base_url} did not start within {timeout}s")

    def _start_container(self):
        container_port = self.config.get("container_port")
        ports_to_map = None

        if container_port:
            ports_to_map = {f"{container_port}/tcp": None}
            self.logger.info(f"Configuring dynamic port mapping for container port: {container_port}")

        try:
            self.logger.info(f"Starting container with image: {self.image}...")
            self.container = self.client.containers.run(
                self.image,
                command="sleep infinity",
                detach=True,
                network_mode="bridge",
                ports=ports_to_map,
                security_opt=["no-new-privileges"],
                user="root"
            )

            self.container.exec_run("mkdir -p /home/user")
            self._place_submission_files()
            
            if container_port:
                self.container.reload()
                port_data = self.container.ports.get(f"{container_port}/tcp")
                if port_data and 'HostPort' in port_data[0]:
                    self.mapped_ports[container_port] = port_data[0]['HostPort']
            
            self.logger.info(f"Container {self.container.short_id} started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start container: {e}")
            self.stop()
            raise

    def _place_submission_files(self):
        if not self.container:
            raise Exception("Container is not running")

        request = request_context.get_request()
        submission_files = request.submission_files

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            for filename, content in submission_files.items():
                file_data = content.encode('utf-8')
                tarinfo = tarfile.TarInfo(name=filename)
                tarinfo.size = len(file_data)
                tar.addfile(tarinfo, io.BytesIO(file_data))

        tar_stream.seek(0)
        self.container.put_archive(path='/home/user/', data=tar_stream)
        self.logger.info("Submission files placed in container at /home/user/")

    def run_command(self, command: str, in_background=False):
        if self.mode == "LOCAL":
            return self._run_local_command(command, in_background)
        elif self.mode == "PROXY":
            return self._run_proxy_command(command, in_background)

    def _run_local_command(self, command: str, in_background=False):
        if not self.container:
            raise Exception("Container is not running")

        self.logger.info(f"Executing: '{command}' (Background: {in_background})")

        if in_background:
            self.container.exec_run(cmd=f"sh -c '{command}'", detach=True, workdir="/home/user")
            return None
        else:
            exit_code, (stdout, stderr) = self.container.exec_run(
                cmd=f"sh -c '{command}'",
                demux=True,
                workdir="/home/user"
            )
            stdout_str = stdout.decode('utf-8').strip() if stdout else ""
            stderr_str = stderr.decode('utf-8').strip() if stderr else ""
            return exit_code, stdout_str, stderr_str

    def _run_proxy_command(self, command: str, in_background=False):
        url = f"{self.base_url}/exec"
        try:
            response = requests.post(
                url, 
                json={"cmd": command, "background": in_background},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data['exit_code'], data['stdout'], data['stderr']
        except requests.exceptions.Timeout:
            return -1, "", "Request timeout"
        except Exception as e:
            return -1, "", f"Communication Error: {e}"

    def get_mapped_port(self, container_port: int) -> str:
        """
        Get the host port that maps to the specified container port.
        
        Args:
            container_port: The internal container port
            
        Returns:
            The host port (string) that maps to the container port
        """
        if self.mode == "PROXY":
            # In proxy mode, use the container port directly
            return str(container_port)
        else:
            # In local mode, return the mapped port
            mapped_port = self.mapped_ports.get(container_port)
            if not mapped_port:
                raise RuntimeError(f"Port {container_port} not mapped. Available ports: {list(self.mapped_ports.keys())}")
            return mapped_port

    def get_address(self) -> str:
        container_port = self.config.get("container_port")
        
        if self.mode == "PROXY":
            return f"http://{self.target_host}:{container_port}"
        else:
            if not container_port:
                raise ValueError("container_port not specified in config")
            mapped_port = self.mapped_ports.get(container_port)
            if not mapped_port:
                raise RuntimeError(f"Port {container_port} not mapped")
            return f"http://localhost:{mapped_port}"
