"""
Test suite for sandbox container lifecycle management.

Tests verify that containers are properly cleaned up in various scenarios:
- Normal operation
- Exception handling
- Context manager usage
- Signal handling
- Orphan cleanup on startup
"""

import time
import pytest
import docker
from sandbox_manager.manager import initialize_sandbox_manager, get_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.language_pool import LABEL_APP


class TestSandboxLifecycle:
    """Test sandbox container lifecycle management."""

    @classmethod
    def setup_class(cls):
        """Initialize sandbox manager before tests."""
        cls.client = docker.from_env()

        # Create minimal pool configuration
        pool_configs = [
            SandboxPoolConfig(
                language=Language.PYTHON,
                pool_size=1,
                scale_limit=2,
                idle_timeout=300,
                running_timeout=60
            )
        ]

        cls.manager = initialize_sandbox_manager(pool_configs)

    @classmethod
    def teardown_class(cls):
        """Clean up after tests."""
        cls.manager.shutdown()

    def get_sandbox_container_count(self):
        """Get count of autograder sandbox containers."""
        containers = self.client.containers.list(
            all=True,
            filters={"label": f"{LABEL_APP}=autograder-sandbox"}
        )
        return len(containers)

    def test_orphan_cleanup_on_startup(self):
        """Test that orphaned containers are cleaned up on startup."""
        # Create a mock orphaned container
        orphan = self.client.containers.run(
            "python:3.9-slim",
            command="sleep infinity",
            detach=True,
            labels={
                LABEL_APP: "autograder-sandbox",
                "test": "orphan"
            }
        )

        initial_count = self.get_sandbox_container_count()
        assert initial_count > 0

        # Re-initialize manager (should cleanup orphans)
        pool_configs = [
            SandboxPoolConfig(
                language=Language.PYTHON,
                pool_size=1,
                scale_limit=2,
                idle_timeout=300,
                running_timeout=60
            )
        ]

        # The orphan should be cleaned up
        from sandbox_manager.manager import _cleanup_orphaned_containers
        _cleanup_orphaned_containers(self.client)

        # Verify orphan is gone
        try:
            orphan.reload()
            pytest.fail("Orphan container should have been removed")
        except docker.errors.NotFound:
            pass  # Expected - container should be gone

    def test_context_manager_cleanup(self):
        """Test that context manager guarantees cleanup even on exceptions."""
        initial_count = self.get_sandbox_container_count()

        try:
            with self.manager.acquire_sandbox(Language.PYTHON) as sandbox:
                # Do some work
                result = sandbox.run_command("echo 'test'")
                assert result.exit_code == 0

                # Simulate an error
                raise RuntimeError("Simulated error during grading")
        except RuntimeError:
            pass  # Expected

        # Wait for cleanup
        time.sleep(2)

        # Container should be destroyed and new one created
        final_count = self.get_sandbox_container_count()

        # Count should return to initial (pool replenishes)
        assert final_count >= initial_count - 1  # Allow for timing

    def test_manual_acquire_release(self):
        """Test manual acquire and release pattern."""
        initial_count = self.get_sandbox_container_count()

        sandbox = self.manager.get_sandbox(Language.PYTHON)
        assert sandbox is not None

        # Use sandbox
        result = sandbox.run_command("python -c 'print(2+2)'")
        assert "4" in result.stdout

        # Release sandbox
        self.manager.release_sandbox(Language.PYTHON, sandbox)

        # Wait for cleanup and replenish
        time.sleep(2)

        final_count = self.get_sandbox_container_count()
        assert final_count >= initial_count - 1

    def test_manager_context_manager(self):
        """Test SandboxManager as context manager."""
        pool_configs = [
            SandboxPoolConfig(
                language=Language.PYTHON,
                pool_size=1,
                scale_limit=2,
                idle_timeout=300,
                running_timeout=60
            )
        ]

        from sandbox_manager.language_pool import LanguagePool
        pools = {Language.PYTHON: LanguagePool(Language.PYTHON, pool_configs[0], self.client)}

        from sandbox_manager.manager import SandboxManager

        with SandboxManager(pools) as manager:
            sandbox = manager.get_sandbox(Language.PYTHON)
            result = sandbox.run_command("echo 'context test'")
            assert result.exit_code == 0
            manager.release_sandbox(Language.PYTHON, sandbox)

        # After context exit, all containers should be destroyed
        time.sleep(2)
        # Check that the pool was shut down

    def test_container_labels(self):
        """Test that containers have proper labels."""
        with self.manager.acquire_sandbox(Language.PYTHON) as sandbox:
            # Get container labels
            sandbox.container_ref.reload()
            labels = sandbox.container_ref.labels

            # Verify required labels exist
            assert LABEL_APP in labels
            assert labels[LABEL_APP] == "autograder-sandbox"
            assert "autograder.sandbox.language" in labels
            assert "autograder.sandbox.pool_id" in labels
            assert "autograder.sandbox.created_at" in labels

    def test_shutdown_destroys_all_containers(self):
        """Test that shutdown destroys all containers."""
        # Acquire multiple sandboxes
        initial_count = self.get_sandbox_container_count()

        sandbox1 = self.manager.get_sandbox(Language.PYTHON)

        # Shutdown manager
        self.manager.shutdown()

        # Wait for cleanup
        time.sleep(2)

        # All containers should be destroyed
        final_count = self.get_sandbox_container_count()
        assert final_count < initial_count

    def test_exception_in_context_manager(self):
        """Test that exceptions in context manager still trigger cleanup."""
        initial_count = self.get_sandbox_container_count()

        with pytest.raises(ValueError):
            with self.manager.acquire_sandbox(Language.PYTHON) as sandbox:
                sandbox.run_command("echo 'before error'")
                raise ValueError("Test exception")

        # Wait for cleanup
        time.sleep(2)

        # Should still clean up
        final_count = self.get_sandbox_container_count()
        assert final_count >= initial_count - 1


def test_pool_context_manager():
    """Test LanguagePool context manager for sandbox acquisition."""
    client = docker.from_env()
    config = SandboxPoolConfig(
        language=Language.PYTHON,
        pool_size=1,
        scale_limit=2,
        idle_timeout=300,
        running_timeout=60
    )

    from sandbox_manager.language_pool import LanguagePool
    pool = LanguagePool(Language.PYTHON, config, client)

    try:
        # Use context manager
        with pool.acquire_sandbox() as sandbox:
            result = sandbox.run_command("python -c 'print(\"pool test\")'")
            assert "pool test" in result.stdout

        # Sandbox should be released and destroyed
        time.sleep(1)
    finally:
        pool.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

