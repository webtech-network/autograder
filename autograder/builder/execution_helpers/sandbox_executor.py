import docker
import tarfile
import io
from autograder.context import request_context


class SandboxExecutor:
    """
    Manages a secure, isolated Docker container for executing student code.

    This class handles the entire lifecycle: creating a container, mapping a
    container port to a fixed host port (9090) for API testing, copying
    submission files, executing commands, and ensuring complete cleanup.
    """

    def __init__(self, config: dict):
        """
        Initializes the executor with assignment-specific configuration.
        The container is not started here. Call the start() factory method.

        Args:
            config (dict): The setup configuration from setup.json.
        """
        self.config = config
        self.image = self.config.get("runtime_image")
        if not self.image:
            raise ValueError("The 'runtime_image' must be specified in setup.json.")

        self.client = docker.from_env()
        self.container = None
        self.HOST_PORT = 9090  # The fixed port for the host machine

    @classmethod
    def start(cls):
        """
        Factory method to create, configure, and start the SandboxExecutor.
        This is the primary entry point for templates.
        """
        request = request_context.get_request()
        setup_config = request.assignment_config.setup

        executor = cls(config=setup_config)
        executor._start_container()
        return executor

    def _start_container(self):
        """
        Starts a secure, isolated container, maps a single container port to the
        fixed host port (9090) if specified, and places student files inside.
        """
        container_port = self.config.get("container_port")
        ports_to_map = None

        if container_port:
            # Create the mapping dictionary, binding the container's port
            # to the fixed host port.
            ports_to_map = {f"{container_port}/tcp": self.HOST_PORT}
            print(f"Configured to map container port {container_port}/tcp to fixed host port {self.HOST_PORT}.")

        try:
            print(f"Starting sandbox container with image: {self.image}...")
            self.container = self.client.containers.run(
                self.image,
                command="sleep infinity",  # Keeps the container alive
                detach=True,
                network_mode="bridge",
                ports=ports_to_map,
                security_opt=["no-new-privileges"],
                user="root"  # Start as root for potential package installs
            )
            self._place_submission_files()
            print(f"Sandbox container {self.container.short_id} started successfully.")

        except Exception as e:
            # Provide a more helpful error message for port conflicts
            if "port is already allocated" in str(e):
                print(
                    f"ERROR: Host port {self.HOST_PORT} is already in use. Please stop the conflicting process and try again.")
            else:
                print(f"Failed to start sandbox container: {e}")
            self.stop()  # Ensure cleanup on failure
            raise

    def _place_submission_files(self):
        """
        Packages in-memory submission files into a tar archive and copies them
        into the running container's /submission directory.
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
        self.container.put_archive(path='/submission/', data=tar_stream)

    def run_command(self, command: str, in_background=False):
        """
        Executes a shell command inside the container.

        Args:
            command (str): The command to execute (e.g., "npm install").
            in_background (bool): If True, runs the command as a detached process.

        Returns:
            A tuple of (exit_code, stdout, stderr).
        """
        if not self.container:
            raise Exception("Container is not running.")

        print(f"Running command: '{command}' in /submission directory...")
        exec_result = self.container.exec_run(
            cmd=f"sh -c '{command}'",
            workdir="/submission",
            detach=in_background,
            user="nobody"  # Drop privileges to a non-root user for execution
        )

        if in_background:
            return (0, "Command running in background.", "")

        exit_code = exec_result.exit_code
        output = exec_result.output.decode('utf-8', errors='ignore')

        print(f"Command finished with exit code {exit_code}")
        print(f"Output:\n{output}")

        return (exit_code, output, "")

    def stop(self):
        """
        Stops and removes the container, ensuring complete cleanup of resources.
        """
        if self.container:
            try:
                print(f"Stopping sandbox container {self.container.short_id}...")
                self.container.remove(force=True)
                print("Sandbox container stopped and removed.")
            except docker.errors.NotFound:
                pass
            except Exception as e:
                print(f"An error occurred during container cleanup: {e}")
            finally:
                self.container = None

