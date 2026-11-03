"""In-memory sandbox manager and a real local HTTP server for control API tests."""
import socket
import threading
import time
from contextlib import contextmanager

import uvicorn

from sandbox_manager.errors import Disposal, SandboxCapacityError, SandboxCleanupError
from autograder.models.process import ProcessResult, ProcessStatus
from sandbox_manager.models.sandbox_models import ExtractedFile, SandboxState


class FakeSandbox:
    def __init__(self, language):
        self.language = language
        self.state = SandboxState.BUSY
        self.files = {}
        self.runs = []

    def prepare_workdir(self, files):
        self.files.update({item.filename: item.content for item in files.values()})

    def inject_assets(self, assets):
        self.files.update({item.target: item.content.decode() for item in assets})

    def run_process(self, request):
        command = " ".join(request.program)
        self.runs.append(command)
        if command == "explode":
            raise RuntimeError("docker exec failed")
        if command == "slow":
            time.sleep(1.5)
        return ProcessResult(ProcessStatus.EXITED, 0, f"ran {command}\n" + request.stdin.decode(), "", duration=0.01)

    def extract_file(self, path, max_bytes=1_048_576):
        name = path.removeprefix("/app/")
        if name not in self.files:
            raise FileNotFoundError(path)
        content = self.files[name].encode()
        return ExtractedFile(path=path, content_bytes=content, size=len(content), content_text=self.files[name])


class FakeManager:
    """Implements the manager lease API without Docker."""

    def __init__(self, *, capacity=10, lease_seconds=60):
        self.capacity = capacity
        self._lease_seconds = lease_seconds
        self.leased = []
        self.dispose_failures = 0
        self.dispose_calls = 0
        self.started = False
        self.shut_down = False

    def start(self):
        self.started = True
        return self

    def shutdown(self):
        self.shut_down = True

    def acquire(self, language):
        if sum(item.state is SandboxState.BUSY for item in self.leased) >= self.capacity:
            raise SandboxCapacityError("full")
        sandbox = FakeSandbox(language)
        self.leased.append(sandbox)
        return sandbox

    def dispose(self, sandbox):
        self.dispose_calls += 1
        if sandbox.state is SandboxState.STOPPED:
            return Disposal.ALREADY_DISPOSED
        if self.dispose_failures:
            self.dispose_failures -= 1
            sandbox.state = SandboxState.CLOSING
            raise SandboxCleanupError("docker remove failed")
        sandbox.state = SandboxState.STOPPED
        return Disposal.DISPOSED

    def lease_seconds(self, language):
        return self._lease_seconds

    def get_pool_stats(self):
        return {"python": {"active": sum(item.state is SandboxState.BUSY for item in self.leased)}}

    def cleanup_problems(self):
        return [{"state": "closing"} for item in self.leased if item.state is SandboxState.CLOSING]


@contextmanager
def serve(app):
    """Run an ASGI app under real uvicorn on a loopback port in a thread."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=30)
        sock.close()
