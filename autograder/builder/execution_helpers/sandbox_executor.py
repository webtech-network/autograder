import docker
import tarfile
import io
import time
from autograder.context import request_context


class SandboxExecutor:
    """
    Manages a secure, isolated Docker container for executing student code,
    using dynamic port mapping for API testing.
    """

    def __init__(self, config: dict):
        self.config = config
        self.image = self.config.get("runtime_image")
        if not self.image:
            raise ValueError("The 'runtime_image' must be specified in setup.json.")

        self.client = docker.from_env()
        self.container = None

    @classmethod
    def start(cls):
        """
        A class method to create and start a SandboxExecutor instance based on
        the globally available autograder request.
        """
        request = request_context.get_request()
        setup_config = request.assignment_config.setup
        if not setup_config:
            raise ValueError("setup.json configuration is missing for this assignment.")

        executor = cls(config=setup_config)
        executor._start_container()
        return executor

    def _start_container(self):
        """
        Starts the Docker container, dynamically mapping the container port to a
        random, available host port.
        """
        container_port = self.config.get("container_port")
        ports_to_map = None

        if container_port:
            # By setting the host port to None, we tell Docker to pick a random one.
            ports_to_map = {f"{container_port}/tcp": None}
            print(f"Configuring dynamic port mapping for container port: {container_port}")

        try:
            print(f"Starting sandbox container with image: {self.image}...")
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
            print(f"Sandbox container {self.container.short_id} started successfully.")

        except Exception as e:
            print(f"Failed to start sandbox container: {e}")
            self.stop()
            raise

    def get_mapped_port(self, container_port: int) -> str:
        """
        Retrieves the dynamically assigned host port for a given container port.
        """
        if not self.container:
            raise Exception("Container is not running.")

        port_key = f"{container_port}/tcp"
        self.container.reload()  # Refresh container data to get network settings
        port_data = self.container.ports.get(port_key)

        if not port_data or 'HostPort' not in port_data[0]:
            raise RuntimeError(f"Port {port_key} is not mapped or visible.")

        return port_data[0]['HostPort']

    def _place_submission_files(self):
        """
        Packages in-memory submission files into a tar archive and copies them
        into the running container's /home/user directory.
        """
        if not self.container:
            raise Exception("Container is not running.")

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
        print("Student submission files placed in container at /home/user/.")

    def run_command(self, command: str, in_background=False):
        """
        Executes a command inside the container.
        """
        if not self.container:
            raise Exception("Container is not running.")

        print(f"Executing command: '{command}' (Background: {in_background})")

        if in_background:
            self.container.exec_run(cmd=f"sh -c '{command}'", detach=True, workdir="/home/user")
            return None
        else:  # This block runs for foreground commands
            exit_code, (stdout, stderr) = self.container.exec_run(
                cmd=f"sh -c '{command}'",
                demux=True,
                workdir="/home/user"
            )
            stdout_str = stdout.decode('utf-8').strip() if stdout else ""
            stderr_str = stderr.decode('utf-8').strip() if stderr else ""

            # ... it prints the logs ...

            # And here it returns the logs to the caller
            return exit_code, stdout_str, stderr_str

    def stop(self):
        """Stops and removes the container to ensure a clean state."""
        if self.container:
            try:
                print(f"Stopping sandbox container {self.container.short_id}...")
                self.container.remove(force=True)
                print("Sandbox container stopped and removed.")
            except docker.errors.NotFound:
                print("Sandbox container was already removed.")
            except Exception as e:
                print(f"An error occurred during container cleanup: {e}")
            finally:
                self.container = None

