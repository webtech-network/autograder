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

        print(f"[{self.language}] 🚀 POOL INITIALIZED - pool_size: {config.pool_size}, scale_limit: {config.scale_limit}, pool_id: {self.pool_id[:8]}")

    def acquire(self) -> SandboxContainer:
        with self.lock:
            current_total = len(self.active_sandboxes) + len(self.idle_sandboxes)
            current_idle = len(self.idle_sandboxes)
            current_active = len(self.active_sandboxes)

            print(f"[{self.language}] 🔍 ACQUIRE REQUEST - idle: {current_idle}, active: {current_active}, total: {current_total}/{self.config.scale_limit}")

            # Try to get an idle sandbox first
            if self.idle_sandboxes:
                sandbox = self.idle_sandboxes.popleft()
                sandbox.pickup() # Update state and timestamp
                self.active_sandboxes.add(sandbox)
                print(f"[{self.language}] ✅ ACQUIRED from idle pool - sandbox_id: {sandbox.container_ref.id[:12]}")
                print(f"[{self.language}] 📊 AFTER ACQUIRE - idle: {len(self.idle_sandboxes)}, active: {len(self.active_sandboxes)}")
                return sandbox

            # No idle sandboxes - check if we can scale up
            if current_total < self.config.scale_limit:
                # We can create a new sandbox on-demand
                print(f"[{self.language}] ⚠️ NO IDLE SANDBOXES - Attempting scale-up...")
                print(f"[{self.language}] 🔄 SCALING UP: creating sandbox #{current_total + 1} (limit: {self.config.scale_limit})")
                try:
                    new_sandbox = self._create_sandbox()
                    new_sandbox.pickup()
                    self.active_sandboxes.add(new_sandbox)
                    print(f"[{self.language}] ✅ SCALE-UP SUCCESS - created sandbox_id: {new_sandbox.container_ref.id[:12]}")
                    print(f"[{self.language}] 📊 AFTER SCALE-UP - idle: {len(self.idle_sandboxes)}, active: {len(self.active_sandboxes)}, total: {len(self.active_sandboxes) + len(self.idle_sandboxes)}/{self.config.scale_limit}")
                    return new_sandbox
                except Exception as e:
                    print(f"[{self.language}] ❌ SCALE-UP FAILED - Error: {e}")
                    raise ValueError(f"Failed to create sandbox for language {self.language}: {e}")

            # At scale limit and all busy - fail
            print(f"[{self.language}] 🚨 BOTTLENECK DETECTED!")
            print(f"[{self.language}] 🚨 All {current_total} sandboxes are BUSY (idle: 0, active: {current_active})")
            print(f"[{self.language}] 🚨 Scale limit reached: {self.config.scale_limit}")
            print(f"[{self.language}] 🚨 Cannot scale further - BLOCKING REQUEST")
            raise ValueError(
                f"No idle sandboxes available for language {self.language}. "
                f"All {current_total} sandboxes are busy (scale_limit: {self.config.scale_limit})"
            )

    def release(self, sandbox: SandboxContainer) -> None:
        with self.lock:
            if sandbox in self.active_sandboxes:
                sandbox_id = sandbox.container_ref.id[:12]
                self.active_sandboxes.remove(sandbox)

                # Check if we should reuse or destroy
                current_total = len(self.active_sandboxes) + len(self.idle_sandboxes)

                print(f"[{self.language}] 🔓 RELEASE - sandbox_id: {sandbox_id}")
                print(f"[{self.language}] 📊 BEFORE RELEASE - idle: {len(self.idle_sandboxes)}, active: {len(self.active_sandboxes) + 1}, total: {current_total + 1}/{self.config.scale_limit}")

                # Reuse if below scale_limit, otherwise destroy to scale down
                if current_total <= self.config.scale_limit:
                    # Return to idle pool for reuse
                    sandbox.last_updated = datetime.now()  # Reset timestamp
                    self.idle_sandboxes.append(sandbox)
                    print(f"[{self.language}] ♻️ REUSE - returned to idle pool")
                    print(f"[{self.language}] 📊 AFTER RELEASE - idle: {len(self.idle_sandboxes)}, active: {len(self.active_sandboxes)}, total: {current_total}/{self.config.scale_limit}")
                else:
                    # Above scale_limit, destroy to scale down
                    try:
                        self._destroy_sandbox(sandbox)
                        print(f"[{self.language}] 🔽 SCALE-DOWN - destroyed sandbox_id: {sandbox_id}")
                        print(f"[{self.language}] 📊 AFTER SCALE-DOWN - idle: {len(self.idle_sandboxes)}, active: {len(self.active_sandboxes)}, total: {current_total - 1}/{self.config.scale_limit}")
                    except Exception as e:
                        print(f"[{self.language}] ❌ Error destroying sandbox during scale-down: {e}")
            else:
                raise ValueError("Sandbox not found in active sandboxes")

        # Call replenish outside the lock to avoid deadlock
        # This ensures we maintain minimum pool_size
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
        Responsible for maintaining minimum pool_size of idle sandboxes.
        Only creates sandboxes if:
        1. Idle count is below pool_size (minimum)
        2. Total sandboxes (active + idle) is below scale_limit (maximum)
        """
        with self.lock:
            current_total_sandboxes = len(self.active_sandboxes) + len(self.idle_sandboxes)
            current_idle = len(self.idle_sandboxes)
            needed = self.config.pool_size - current_idle

            if needed > 0:
                print(f"[{self.language}] 🔄 REPLENISH CHECK - idle: {current_idle}/{self.config.pool_size} (need {needed} more), total: {current_total_sandboxes}/{self.config.scale_limit}")

            # Maintain minimum pool_size of idle sandboxes
            while len(self.idle_sandboxes) < self.config.pool_size and current_total_sandboxes < self.config.scale_limit:
                try:
                    print(f"[{self.language}] ➕ REPLENISH: Creating sandbox #{current_total_sandboxes + 1}...")
                    new_sandbox = self._create_sandbox()
                    self.idle_sandboxes.append(new_sandbox)
                    current_total_sandboxes += 1
                    print(f"[{self.language}] ✅ REPLENISH SUCCESS - sandbox_id: {new_sandbox.container_ref.id[:12]}")
                    print(f"[{self.language}] 📊 AFTER REPLENISH - idle: {len(self.idle_sandboxes)}/{self.config.pool_size}, total: {current_total_sandboxes}/{self.config.scale_limit}")
                except Exception as e:
                    print(f"[{self.language}] ❌ REPLENISH FAILED - Error: {e}")
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
        # Only scale down if we are above the Minimum Pool Size
        if len(idle_snapshot) > self.config.pool_size:

            for sandbox in idle_snapshot:
                if (now - sandbox.created_at).total_seconds() > self.config.idle_timeout:

                    with self.lock:
                        # Double check inside lock before removing
                        if sandbox in self.idle_sandboxes and len(self.idle_sandboxes) > self.config.pool_size:
                            self.idle_sandboxes.remove(sandbox)
                            self._destroy_sandbox(sandbox)

    def monitor(self):
        """
        Called periodically by the manager to check TTLs and trigger replenishment if needed.
        """
        self.check_ttls()
        self.replenish()

        # Periodic stats logging every ~10 calls (assuming 1 second intervals = ~10 seconds)
        if not hasattr(self, '_monitor_counter'):
            self._monitor_counter = 0

        self._monitor_counter += 1
        if self._monitor_counter >= 10:
            self._monitor_counter = 0
            stats = self.get_stats()
            utilization = stats['utilization']

            # Log with appropriate warning level based on utilization
            if utilization >= 90:
                print(f"[{self.language}] 🚨 HIGH LOAD - idle: {stats['idle']}, active: {stats['active']}, total: {stats['total']}/{stats['scale_limit']}, utilization: {utilization:.1f}%")
            elif utilization >= 70:
                print(f"[{self.language}] ⚠️ MODERATE LOAD - idle: {stats['idle']}, active: {stats['active']}, total: {stats['total']}/{stats['scale_limit']}, utilization: {utilization:.1f}%")
            elif stats['total'] > 0:
                print(f"[{self.language}] 📊 STATS - idle: {stats['idle']}, active: {stats['active']}, total: {stats['total']}/{stats['scale_limit']}, utilization: {utilization:.1f}%")

    def get_stats(self) -> dict:
        """
        Get current pool statistics for monitoring and debugging.
        """
        with self.lock:
            return {
                "language": self.language.value,
                "idle": len(self.idle_sandboxes),
                "active": len(self.active_sandboxes),
                "total": len(self.idle_sandboxes) + len(self.active_sandboxes),
                "pool_size": self.config.pool_size,
                "scale_limit": self.config.scale_limit,
                "utilization": len(self.active_sandboxes) / (len(self.idle_sandboxes) + len(self.active_sandboxes)) * 100 if (len(self.idle_sandboxes) + len(self.active_sandboxes)) > 0 else 0
            }

    def _create_sandbox(self) -> SandboxContainer:
        """
        Creates a new sandbox container with security constraints.
        Uses gVisor runtime if available, falls back to default runtime otherwise.

        Containers are kept alive with 'sleep infinity' to allow exec commands.
        """
        print(f"[{self.language}] 🏗️ CREATE SANDBOX - Starting container creation...")

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
            print(f"[{self.language}] 🔒 Attempting to create with gVisor runtime (runsc)...")
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
            print(f"[{self.language}] ✅ Container created with gVisor - container_id: {container.id[:12]}")
        except Exception as e:
            # If gVisor is not available, use default runtime with same constraints
            if "unknown or invalid runtime name" in str(e).lower() or "runsc" in str(e).lower():
                print(f"[{self.language}] ⚠️ gVisor runtime not available, falling back to default runtime")
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
                print(f"[{self.language}] ✅ Container created with default runtime - container_id: {container.id[:12]}")
            else:
                # Re-raise if it's a different error
                print(f"[{self.language}] ❌ Container creation failed: {e}")
                raise

        sandbox = SandboxContainer(language=self.language, container_ref=container)
        print(f"[{self.language}] 🎉 SANDBOX CREATED SUCCESSFULLY - container_id: {container.id[:12]}")
        return sandbox

    def _destroy_sandbox(self, sandbox: SandboxContainer):
        sandbox_id = sandbox.container_ref.id[:12]
        print(f"[{self.language}] 🗑️ DESTROY SANDBOX - container_id: {sandbox_id}")
        try:
            sandbox.container_ref.stop(timeout=1)
            sandbox.container_ref.remove()
            print(f"[{self.language}] ✅ SANDBOX DESTROYED - container_id: {sandbox_id}")
        except Exception as e:
            print(f"[{self.language}] ❌ Error destroying sandbox {sandbox_id}: {e}")

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

