from datetime import datetime
import threading
import uuid
from collections import deque
from typing import Set

from docker.client import DockerClient
from docker.types.containers import Ulimit

from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.sandbox_container import SandboxContainer

# Container label constants for tracking and cleanup
LABEL_APP = "autograder.sandbox.app"
LABEL_VERSION = "autograder.sandbox.version"
LABEL_LANGUAGE = "autograder.sandbox.language"
LABEL_POOL_ID = "autograder.sandbox.pool_id"
LABEL_CREATED_AT = "autograder.sandbox.created_at"
SANDBOX_VERSION = "1.0"


class LanguagePool:
    def __init__(self,
                 language: Language,
                 config: SandboxPoolConfig,
                 client: DockerClient = None
                 ):
        self.language = language
        self.config = config
        self.client = client
        self.pool_id = str(uuid.uuid4())  # Unique identifier for this pool instance

        self.idle_sandboxes : deque[SandboxContainer] = deque()
        self.active_sandboxes : Set[SandboxContainer] = set()

        # Only blocks for this pool, allowing concurrent access to different pools
        self.lock = threading.Lock()

    def acquire(self) -> SandboxContainer:
        with self.lock:
            if self.idle_sandboxes:
                sandbox = self.idle_sandboxes.popleft()
                sandbox.pickup() # Update state and timestamp
                self.active_sandboxes.add(sandbox)
                return sandbox
            else:
                raise ValueError(f"No idle sandboxes available for language: {self.language}")

    def release(self, sandbox: SandboxContainer) -> None:
        with self.lock:
            if sandbox in self.active_sandboxes:
                try:
                    self._destroy_sandbox(sandbox)
                except Exception as e:
                    print(f"Error destroying sandbox: {e}")
                self.active_sandboxes.remove(sandbox)
            else:
                raise ValueError("Sandbox not found in active sandboxes")

        # Call replenish outside the lock to avoid deadlock
        self.replenish()

    def acquire_sandbox(self):
        """
        Context manager for safe sandbox acquisition and guaranteed release.

        Usage:
            with pool.acquire_sandbox() as sandbox:
                sandbox.run_command("python script.py")
            # Sandbox is automatically released even if an exception occurs
        """
        from contextlib import contextmanager

        @contextmanager
        def _sandbox_context():
            sandbox = self.acquire()
            try:
                yield sandbox
            finally:
                self.release(sandbox)

        return _sandbox_context()

    def replenish(self):
        """
        Responsible for creating new sandboxes if the number of idle sandboxes is below the start_amount.
        """
        with self.lock:
            current_total_sandboxes = len(self.active_sandboxes) + len(self.idle_sandboxes)
            while len(self.idle_sandboxes) < self.config.start_amount and current_total_sandboxes < self.config.scale_limit:
                try:
                    new_sandbox = self._create_sandbox()
                    self.idle_sandboxes.append(new_sandbox)
                except Exception as e:
                    print(f"Error creating sandbox: {e}")
                    break

    def check_ttls(self):
        """
        Checks idle sandboxes for idle_timeout and active sandboxes for running_timeout, destroying those that exceed the limits.
        """
        now = datetime.now()

        with self.lock:
            active_snapshot = list(self.active_sandboxes)
            idle_snapshot = list(self.idle_sandboxes)

        # 1. Active TTL (Runtime limit)
        for sandbox in active_snapshot:
            if (now - sandbox.last_updated).total_seconds() > self.config.running_timeout:
                print(f"[{self.language}] Sandbox {sandbox.container_ref.id} exceeded running timeout, destroying...")
                self.release(sandbox)

        # 2. Idle TTL (Scale down)
        # Only scale down if we are above the Minimum Start Amount
        if len(idle_snapshot) > self.config.start_amount:

            for sandbox in idle_snapshot:
                if (now - sandbox.created_at).total_seconds() > self.config.idle_timeout:

                    with self.lock:
                        # Double check inside lock before removing
                        if sandbox in self.idle_sandboxes and len(self.idle_sandboxes) > self.config.start_amount:
                            self.idle_sandboxes.remove(sandbox)
                            self._destroy_sandbox(sandbox)

    def monitor(self):
        """
        Called periodically by the manager to check TTLs and trigger replenishment if needed.
        """
        self.check_ttls()
        self.replenish()

    def _create_sandbox(self) -> SandboxContainer:
        """
        Creates a new sandbox container with security constraints.
        Uses gVisor runtime if available, falls back to default runtime otherwise.

        Containers are kept alive with 'sleep infinity' to allow exec commands.
        """
        # Container labels for tracking and orphan cleanup
        labels = {
            LABEL_APP: "autograder-sandbox",
            LABEL_VERSION: SANDBOX_VERSION,
            LABEL_LANGUAGE: self.language.value,
            LABEL_POOL_ID: self.pool_id,
            LABEL_CREATED_AT: datetime.now().isoformat()
        }

        # Try to use gVisor runtime for enhanced security, fall back to default if not available
        try:
            container = self.client.containers.run(
                image=self.language.image,
                detach=True,
                command="sleep infinity",  # Keep container alive for exec commands
                runtime="runsc",  # gVisor runtime for enhanced isolation
                mem_limit="128m",
                memswap_limit="128m",
                nano_cpus=500000000,  # 0.5 CPU
                pids_limit=64,
                tmpfs={
                    '/tmp': 'rw,size=32m,noexec',
                    '/app': 'rw,size=64m,exec'  # Writable workspace for student code
                },
                network_mode="none",
                cap_drop=["ALL"],
                ulimits=[
                    Ulimit(name='fsize', soft=10000000, hard=10000000),
                ],
                labels=labels
            )
        except Exception as e:
            # If gVisor is not available, use default runtime with same constraints
            if "unknown or invalid runtime name" in str(e).lower() or "runsc" in str(e).lower():
                print(f"[{self.language}] gVisor runtime not available, using default runtime")
                container = self.client.containers.run(
                    image=self.language.image,
                    detach=True,
                    command="sleep infinity",  # Keep container alive for exec commands
                    # No runtime specified = default runc
                    mem_limit="128m",
                    memswap_limit="128m",
                    nano_cpus=500000000,  # 0.5 CPU
                    pids_limit=64,
                    tmpfs={
                        '/tmp': 'rw,size=32m,noexec',
                        '/app': 'rw,size=64m,exec'
                    },
                    network_mode="none",
                    cap_drop=["ALL"],
                    ulimits=[
                        Ulimit(name='fsize', soft=10000000, hard=10000000),
                    ],
                    labels=labels
                )
            else:
                # Re-raise if it's a different error
                raise

        return SandboxContainer(language=self.language, container_ref=container)

    def _destroy_sandbox(self, sandbox: SandboxContainer):
        try:
            sandbox.container_ref.stop(timeout=1)
            sandbox.container_ref.remove()
            print("Sandbox destroyed: ", sandbox)
        except Exception as e:
            print(f"Error stopping/removing container: {e}")

    def shutdown(self):
        """
        Destroy all containers in this pool (both active and idle).
        Called during system shutdown to ensure cleanup.
        """
        print(f"[{self.language}] Shutting down pool, destroying all containers...")

        with self.lock:
            # Copy sets/deques to avoid modification during iteration
            active_snapshot = list(self.active_sandboxes)
            idle_snapshot = list(self.idle_sandboxes)

            # Clear the collections
            self.active_sandboxes.clear()
            self.idle_sandboxes.clear()

        # Destroy all containers
        destroyed_count = 0
        for sandbox in active_snapshot + idle_snapshot:
            try:
                self._destroy_sandbox(sandbox)
                destroyed_count += 1
            except Exception as e:
                print(f"[{self.language}] Error destroying sandbox during shutdown: {e}")

        print(f"[{self.language}] Pool shutdown complete. Destroyed {destroyed_count} containers.")

