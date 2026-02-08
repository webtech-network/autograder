from datetime import datetime
from docker.models.containers import Container
from sandbox_manager.models.sandbox_models import Language,SandboxState

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

    def pickup(self):
        self.state = SandboxState.BUSY
        self.last_updated = datetime.now()

    def run_command(self, command: str) -> str:
        # This method would use the container_ref to execute the command inside the container
        # and return the output. The actual implementation would depend on how you want to handle
        # command execution and output retrieval.
        pass

    def make_request(self, request_method: str, endpoint: str, data: dict = None):
        # This method would make an HTTP request to the specified endpoint on the container.
        # The implementation would depend on how your container is set up to receive requests.
        pass
