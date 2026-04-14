from datetime import datetime
import logging
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

# Create module-level logger
logger = logging.getLogger(__name__)


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
        self._sandbox_seq = 0  # Per-pool creation sequence counter

        self.idle_sandboxes : deque[SandboxContainer] = deque()
        self.active_sandboxes : Set[SandboxContainer] = set()

        # Only blocks for this pool, allowing concurrent access to different pools
        self.lock = threading.Lock()

        logger.info("[%s] POOL INITIALIZED - pool_size: %s, scale_limit: %s, pool_id: %s",
                    language, config.pool_size, config.scale_limit, self.pool_id[:8])

    def acquire(self) -> SandboxContainer:
        with self.lock:
            current_total = len(self.active_sandboxes) + len(self.idle_sandboxes)
            current_idle = len(self.idle_sandboxes)
            current_active = len(self.active_sandboxes)

            logger.debug("[%s] ACQUIRE REQUEST - idle: %s, active: %s, total: %s/%s",
                         self.language, current_idle, current_active, current_total, self.config.scale_limit)

            # Try to get an idle sandbox first
            if self.idle_sandboxes:
                sandbox = self.idle_sandboxes.popleft()
                sandbox.pickup() # Update state and timestamp
                self.active_sandboxes.add(sandbox)
                logger.info("[%s] ACQUIRED from idle pool - sandbox_id: %s",
                            self.language, sandbox.container_ref.id[:12])
                return sandbox

            # No idle sandboxes - check if we can scale up
            if current_total < self.config.scale_limit:
                # We can create a new sandbox on-demand
                logger.info("[%s] NO IDLE SANDBOXES - Attempting scale-up...", self.language)
                try:
                    new_sandbox = self._create_sandbox()
                    new_sandbox.pickup()
                    self.active_sandboxes.add(new_sandbox)
                    logger.info("[%s] SCALE-UP SUCCESS - created sandbox_id: %s",
                                self.language, new_sandbox.container_ref.id[:12])
                    return new_sandbox
                except Exception as e:
                    logger.exception("[%s] SCALE-UP FAILED - Error: %s", self.language, e)
                    raise ValueError(f"Failed to create sandbox for language {self.language}: {e}")

            # At scale limit and all busy - fail
            logger.warning("[%s] BOTTLENECK DETECTED - All %s sandboxes are BUSY (scale_limit: %s)",
                           self.language, current_total, self.config.scale_limit)
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

                # Reuse if below scale_limit, otherwise destroy to scale down
                if current_total <= self.config.scale_limit:
                    # Return to idle pool for reuse
                    sandbox.last_updated = datetime.now()  # Reset timestamp
                    self.idle_sandboxes.append(sandbox)
                    logger.info("[%s] RELEASE - sandbox_id: %s returned to idle pool",
                                self.language, sandbox_id)
                else:
                    # Above scale_limit, destroy to scale down
                    try:
                        self._destroy_sandbox(sandbox)
                        logger.info("[%s] SCALE-DOWN - destroyed sandbox_id: %s",
                                    self.language, sandbox_id)
                    except Exception as e:
                        logger.exception("[%s] Error destroying sandbox during scale-down: %s",
                                     self.language, e)
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
                logger.debug("[%s] REPLENISH CHECK - idle: %s/%s (need %s more), total: %s/%s",
                             self.language, current_idle, self.config.pool_size, needed,
                             current_total_sandboxes, self.config.scale_limit)

            # Maintain minimum pool_size of idle sandboxes
            while len(self.idle_sandboxes) < self.config.pool_size and current_total_sandboxes < self.config.scale_limit:
                try:
                    new_sandbox = self._create_sandbox()
                    self.idle_sandboxes.append(new_sandbox)
                    current_total_sandboxes += 1
                    logger.info("[%s] REPLENISH SUCCESS - sandbox_id: %s",
                                self.language, new_sandbox.container_ref.id[:12])
                except Exception as e:
                    logger.exception("[%s] REPLENISH FAILED - Error: %s", self.language, e)
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
                logger.warning("[%s] Sandbox %s exceeded running timeout, destroying...",
                              self.language, sandbox.container_ref.id)
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
        # Only logs when there's active operations
        if not hasattr(self, '_monitor_counter'):
            self._monitor_counter = 0

        self._monitor_counter += 1
        if self._monitor_counter >= 10:
            self._monitor_counter = 0
            stats = self.get_stats()
            utilization = stats['utilization']

            # Log with appropriate warning level based on utilization
            if utilization >= 90:
                logger.warning("[%s] HIGH LOAD - idle: %s, active: %s, total: %s/%s, utilization: %.1f%%",
                              self.language, stats['idle'], stats['active'],
                              stats['total'], stats['scale_limit'], utilization)
            elif utilization >= 70:
                logger.info("[%s] MODERATE LOAD - idle: %s, active: %s, total: %s/%s, utilization: %.1f%%",
                            self.language, stats['idle'], stats['active'],
                            stats['total'], stats['scale_limit'], utilization)
            elif stats['active'] > 0:
                logger.debug("[%s] STATS - idle: %s, active: %s, total: %s/%s, utilization: %.1f%%",
                             self.language, stats['idle'], stats['active'],
                             stats['total'], stats['scale_limit'], utilization)

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
        container_name = self._build_container_name()
        logger.info("[%s] CREATE SANDBOX - Starting container creation (%s)...",
                    self.language, container_name)

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
            logger.debug("[%s] Attempting to create with gVisor runtime (runsc)...", self.language)
            container = self.client.containers.run(
                image=self.language.image,
                name=container_name,
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
            logger.info("[%s] Container created with gVisor - %s (%s)",
                        self.language, container_name, container.id[:12])
        except Exception as e:
            # If gVisor is not available, use default runtime with same constraints
            if "unknown or invalid runtime name" in str(e).lower() or "runsc" in str(e).lower():
                logger.info("[%s] gVisor runtime not available, falling back to default runtime", self.language)
                container = self.client.containers.run(
                    image=self.language.image,
                    name=container_name,
                    detach=True,
                    command="sleep infinity",  # Keep container alive for exec commands
                    # No runtime specified = default runc
                    mem_limit="128m",
                    memswap_limit="128m",
                    nano_cpus=500000000,  # 0.5 CPU
                    pids_limit=64,
                    tmpfs={
                        '/tmp': 'rw,size=32m,noexec',
                        # Note: /app intentionally NOT in tmpfs — see above.
                    },
                    network_mode="none",
                    cap_drop=["ALL"],
                    ulimits=[
                        Ulimit(name='fsize', soft=10000000, hard=10000000),
                    ],
                    labels=labels
                )
                logger.info("[%s] Container created with default runtime - %s (%s)",
                            self.language, container_name, container.id[:12])
            else:
                # Re-raise if it's a different error
                logger.exception("[%s] Container creation failed: %s", self.language, e)
                raise


        sandbox = SandboxContainer(language=self.language, container_ref=container)
        logger.info("[%s] SANDBOX CREATED SUCCESSFULLY - %s (%s)",
                    self.language, container_name, container.id[:12])
        return sandbox

    def _build_container_name(self) -> str:
        """Build deterministic container name: ag-sbx-{lang}-{pool8}-{seq4}"""
        self._sandbox_seq += 1
        return f"ag-sbx-{self.language.value}-{self.pool_id[:8]}-{self._sandbox_seq:04d}"

    def destroy_sandbox(self, sandbox: SandboxContainer) -> None:
        """
        Destroy a sandbox immediately without releasing it back to the pool.
        Use this for sandboxes that timeout or encounter fatal errors.

        Args:
            sandbox: The sandbox to destroy
        """
        with self.lock:
            if sandbox in self.active_sandboxes:
                sandbox_id = sandbox.container_ref.id[:12]
                self.active_sandboxes.remove(sandbox)
                logger.info("[%s] REMOVE FROM ACTIVE - sandbox_id: %s", self.language, sandbox_id)
            else:
                raise ValueError("Sandbox not found in active sandboxes")

        # Destroy outside the lock
        self._destroy_sandbox(sandbox)

        # Replenish pool to maintain minimum size
        self.replenish()

    def _destroy_sandbox(self, sandbox: SandboxContainer):
        sandbox_id = sandbox.container_ref.id[:12]
        logger.info("[%s] DESTROY SANDBOX - container_id: %s", self.language, sandbox_id)
        try:
            sandbox.container_ref.stop(timeout=1)
            sandbox.container_ref.remove()
            logger.info("[%s] SANDBOX DESTROYED - container_id: %s", self.language, sandbox_id)
        except Exception as e:
            logger.exception("[%s] Error destroying sandbox %s: %s", self.language, sandbox_id, e)

    def shutdown(self):
        """
        Destroy all containers in this pool (both active and idle).
        Called during system shutdown to ensure cleanup.
        """
        logger.info("[%s] Shutting down pool, destroying all containers...", self.language)

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
                logger.exception("[%s] Error destroying sandbox during shutdown: %s", self.language, e)

        logger.info("[%s] Pool shutdown complete. Destroyed %s containers.", self.language, destroyed_count)
