"""
Integration tests for Sandbox Manager.

Tests the complete integration of sandbox manager with the autograder pipeline,
including pool management, container lifecycle, and execution.

These tests require Docker to be running and sandbox images to be built.
"""

import unittest
import time
from tests.integration.sandbox_support import current_test_manager, start_test_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import SandboxState
from autograder.models.language import Language
from autograder.models.process import ProcessRequest, ProcessStatus, lines_to_stdin
from tests.sandbox_profiles import TEST_IMAGES
from autograder.models.dataclass.submission import SubmissionFile


class TestSandboxManagerIntegration(unittest.TestCase):
    """Integration tests for the complete Sandbox Manager system."""

    @classmethod
    def setUpClass(cls):
        """Initialize sandbox manager with test configuration."""
        pool_configs = [
            SandboxPoolConfig(
                language=Language.PYTHON,
                image=TEST_IMAGES[Language.PYTHON],
                pool_size=2,
                scale_limit=5,
                idle_timeout=300,
                running_timeout=60
            ),
            SandboxPoolConfig(
                language=Language.JAVA,
                image=TEST_IMAGES[Language.JAVA],
                pool_size=1,
                scale_limit=3,
                idle_timeout=300,
                running_timeout=60
            ),
            SandboxPoolConfig(
                language=Language.NODE,
                image=TEST_IMAGES[Language.NODE],
                pool_size=1,
                scale_limit=3,
                idle_timeout=300,
                running_timeout=60
            ),
            SandboxPoolConfig(
                language=Language.CPP,
                image=TEST_IMAGES[Language.CPP],
                pool_size=1,
                scale_limit=3,
                idle_timeout=300,
                running_timeout=60
            )
        ]
        cls.manager = start_test_manager(pool_configs)
        # Give containers time to start
        time.sleep(2)

    def test_01_manager_initialization(self):
        """Test that manager initializes all language pools correctly."""
        manager = current_test_manager()
        self.assertIsNotNone(manager)
        self.assertEqual(len(manager.language_pools), 4)
        self.assertIn(Language.PYTHON, manager.language_pools)
        self.assertIn(Language.JAVA, manager.language_pools)
        self.assertIn(Language.NODE, manager.language_pools)
        self.assertIn(Language.CPP, manager.language_pools)

    def test_02_pool_initial_state(self):
        """Test that pools are initialized with correct number of containers."""
        manager = current_test_manager()

        # Python pool should have 2 idle sandboxes
        py_pool = manager.language_pools[Language.PYTHON]
        self.assertEqual(len(py_pool.idle_sandboxes), 2)
        self.assertEqual(len(py_pool.active_sandboxes), 0)

        # Java pool should have 1 idle sandbox
        java_pool = manager.language_pools[Language.JAVA]
        self.assertEqual(len(java_pool.idle_sandboxes), 1)
        self.assertEqual(len(java_pool.active_sandboxes), 0)

    def test_03_acquire_and_release_python(self):
        """Test acquiring and releasing a Python sandbox."""
        manager = current_test_manager()

        # Acquire a sandbox
        sandbox = manager.acquire(Language.PYTHON)
        self.assertIsNotNone(sandbox)
        self.assertEqual(sandbox.language, Language.PYTHON)
        self.assertEqual(sandbox.state, SandboxState.BUSY)

        # Check pool state
        py_pool = manager.language_pools[Language.PYTHON]
        self.assertEqual(len(py_pool.active_sandboxes), 1)
        self.assertIn(sandbox, py_pool.active_sandboxes)

        # Release the sandbox
        manager.dispose(sandbox)

        # Give time for replenishment
        time.sleep(1)

        # Check that pool replenished
        self.assertEqual(len(py_pool.idle_sandboxes), 2)
        self.assertEqual(len(py_pool.active_sandboxes), 0)

    def test_04_python_hello_world(self):
        """Test executing a simple Python program."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.PYTHON)

        try:
            # Prepare a simple hello world program
            files = {
                "hello.py": SubmissionFile("hello.py", "print('Hello, World!')")
            }
            sandbox.prepare_workdir(files)

            # Run the program
            response = sandbox.run_process(ProcessRequest.command("python3 hello.py"))

            self.assertEqual(response.exit_code, 0)
            self.assertIn("Hello, World!", response.stdout)
            self.assertEqual(response.stderr, "")

        finally:
            manager.dispose(sandbox)

    def test_05_python_calculator_interactive(self):
        """Test Python interactive program with multiple inputs."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.PYTHON)

        try:
            # Create a simple calculator that reads operation and two numbers
            calculator_code = """
operation = input()
a = int(input())
b = int(input())

if operation == 'ADD':
    print(a + b)
elif operation == 'SUB':
    print(a - b)
elif operation == 'MUL':
    print(a * b)
elif operation == 'DIV':
    print(a // b)
"""
            files = {
                "calc.py": SubmissionFile("calc.py", calculator_code)
            }
            sandbox.prepare_workdir(files)

            # Test addition
            response = sandbox.run_process(ProcessRequest.command(
                "python3 calc.py", stdin=lines_to_stdin(["ADD", "10", "20"])))

            self.assertEqual(response.exit_code, 0)
            self.assertIn("30", response.stdout)

        finally:
            manager.dispose(sandbox)

    def test_06_python_with_directory_structure(self):
        """Test Python program with nested directory structure."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.PYTHON)

        try:
            # Create files with directory structure
            files = {
                "main.py": SubmissionFile("main.py", """
from services.user_service import UserService

service = UserService()
print(service.get_message())
"""),
                "services/user_service.py": SubmissionFile(
                    "services/user_service.py",
                    """
class UserService:
    def get_message(self):
        return "Service working!"
"""
                ),
                "services/__init__.py": SubmissionFile("services/__init__.py", "")
            }
            sandbox.prepare_workdir(files)

            # Run the program
            response = sandbox.run_process(ProcessRequest.command("python3 main.py"))

            self.assertEqual(response.exit_code, 0)
            self.assertIn("Service working!", response.stdout)

        finally:
            manager.dispose(sandbox)

    def test_07_java_hello_world(self):
        """Test executing a simple Java program."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.JAVA)

        try:
            # Create a simple Java program
            java_code = """
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello from Java!");
    }
}
"""
            files = {
                "Hello.java": SubmissionFile("Hello.java", java_code)
            }
            sandbox.prepare_workdir(files)

            # Compile
            compile_response = sandbox.run_process(ProcessRequest.command("javac Hello.java"))
            self.assertEqual(compile_response.exit_code, 0)

            # Run
            run_response = sandbox.run_process(ProcessRequest.command("java Hello"))
            self.assertEqual(run_response.exit_code, 0)
            self.assertIn("Hello from Java!", run_response.stdout)

        finally:
            manager.dispose(sandbox)

    def test_08_javascript_hello_world(self):
        """Test executing a simple JavaScript program."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.NODE)

        try:
            # Create a simple Node.js program
            js_code = "console.log('Hello from Node.js!');"
            files = {
                "hello.js": SubmissionFile("hello.js", js_code)
            }
            sandbox.prepare_workdir(files)

            # Run
            response = sandbox.run_process(ProcessRequest.command("node hello.js"))

            self.assertEqual(response.exit_code, 0)
            self.assertIn("Hello from Node.js!", response.stdout)

        finally:
            manager.dispose(sandbox)

    def test_09_cpp_hello_world(self):
        """Test compiling and executing a simple C++ program."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.CPP)

        try:
            # Create a simple C++ program
            cpp_code = """
#include <iostream>

int main() {
    std::cout << "Hello from C++!" << std::endl;
    return 0;
}
"""
            files = {
                "hello.cpp": SubmissionFile("hello.cpp", cpp_code)
            }
            sandbox.prepare_workdir(files)

            # Compile
            compile_response = sandbox.run_process(ProcessRequest.command("g++ hello.cpp -o hello"))
            self.assertEqual(compile_response.exit_code, 0)

            # Run
            run_response = sandbox.run_process(ProcessRequest.command("./hello"))
            self.assertEqual(run_response.exit_code, 0)
            self.assertIn("Hello from C++!", run_response.stdout)

        finally:
            manager.dispose(sandbox)

    def test_10_concurrent_sandbox_acquisition(self):
        """Test acquiring multiple sandboxes concurrently."""
        manager = current_test_manager()

        # Acquire two Python sandboxes
        sandbox1 = manager.acquire(Language.PYTHON)
        sandbox2 = manager.acquire(Language.PYTHON)

        try:
            self.assertIsNotNone(sandbox1)
            self.assertIsNotNone(sandbox2)
            self.assertNotEqual(sandbox1.container_ref.id, sandbox2.container_ref.id)

            # Both should be in BUSY state
            self.assertEqual(sandbox1.state, SandboxState.BUSY)
            self.assertEqual(sandbox2.state, SandboxState.BUSY)

            # Pool should have 2 active sandboxes
            py_pool = manager.language_pools[Language.PYTHON]
            self.assertEqual(len(py_pool.active_sandboxes), 2)

        finally:
            manager.dispose(sandbox1)
            manager.dispose(sandbox2)

    def test_11_error_handling_invalid_code(self):
        """Test that sandbox handles invalid code gracefully."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.PYTHON)

        try:
            # Create invalid Python code
            files = {
                "bad.py": SubmissionFile("bad.py", "this is not valid python code!")
            }
            sandbox.prepare_workdir(files)

            # Run the program
            response = sandbox.run_process(ProcessRequest.command("python3 bad.py"))

            # Should have non-zero exit code
            self.assertNotEqual(response.exit_code, 0)
            self.assertNotEqual(response.stderr, "")

        finally:
            manager.dispose(sandbox)

    def test_12_timeout_handling(self):
        """Test that execution respects timeout."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.PYTHON)

        try:
            # Create program that sleeps
            files = {
                "sleep.py": SubmissionFile("sleep.py", "import time; time.sleep(5); print('Done')")
            }
            sandbox.prepare_workdir(files)

            # The deadline stops the process; no output after the deadline exists.
            start_time = time.time()
            response = sandbox.run_process(ProcessRequest.command("python3 sleep.py", timeout=1))
            elapsed = time.time() - start_time

            self.assertIs(response.status, ProcessStatus.TIMED_OUT)
            self.assertIsNone(response.exit_code)
            self.assertNotIn("Done", response.stdout)
            self.assertLess(elapsed, 5)

        finally:
            manager.dispose(sandbox)

    def test_13_resource_isolation(self):
        """Test that sandboxes are isolated from each other."""
        manager = current_test_manager()
        sandbox1 = manager.acquire(Language.PYTHON)

        try:
            # Create a file in sandbox1
            files1 = {
                "data.txt": SubmissionFile("data.txt", "secret data")
            }
            sandbox1.prepare_workdir(files1)

            # Verify file exists in sandbox1
            response1 = sandbox1.run_process(ProcessRequest.command("cat data.txt"))
            self.assertIn("secret data", response1.stdout)

        finally:
            manager.dispose(sandbox1)

        # Get a new sandbox (could be the same container after cleanup)
        sandbox2 = manager.acquire(Language.PYTHON)

        try:
            # The new sandbox should NOT have the file from before
            # (because we destroy and recreate containers on release)
            response2 = sandbox2.run_process(ProcessRequest.command("ls /app"))
            # /app should be empty in a fresh container
            self.assertEqual(response2.stdout.strip(), "")

        finally:
            manager.dispose(sandbox2)

    def test_14_pool_replenishment(self):
        """Test that pools automatically replenish after releases."""
        manager = current_test_manager()
        py_pool = manager.language_pools[Language.PYTHON]

        initial_idle = len(py_pool.idle_sandboxes)

        # Acquire and release a sandbox
        sandbox = manager.acquire(Language.PYTHON)
        manager.dispose(sandbox)

        # Wait for replenishment
        time.sleep(2)

        # Pool should be back to initial state
        self.assertEqual(len(py_pool.idle_sandboxes), initial_idle)

    def test_15_multiple_files_execution(self):
        """Test executing programs with multiple interdependent files."""
        manager = current_test_manager()
        sandbox = manager.acquire(Language.PYTHON)

        try:
            # Create a multi-file Python project
            files = {
                "main.py": SubmissionFile("main.py", """
from utils.math_ops import add, multiply

result1 = add(5, 3)
result2 = multiply(4, 7)
print(f"Add: {result1}, Multiply: {result2}")
"""),
                "utils/math_ops.py": SubmissionFile("utils/math_ops.py", """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""),
                "utils/__init__.py": SubmissionFile("utils/__init__.py", "")
            }
            sandbox.prepare_workdir(files)

            # Run the program
            response = sandbox.run_process(ProcessRequest.command("python3 main.py"))

            self.assertEqual(response.exit_code, 0)
            self.assertIn("Add: 8", response.stdout)
            self.assertIn("Multiply: 28", response.stdout)

        finally:
            manager.dispose(sandbox)


class TestSandboxSecurityConstraints(unittest.TestCase):
    """Test that security constraints are enforced in sandboxes."""

    @classmethod
    def setUpClass(cls):
        """Get the already initialized sandbox manager."""
        cls.manager = current_test_manager()

    def test_network_isolation(self):
        """Test that sandboxes cannot access the network."""
        sandbox = self.manager.acquire(Language.PYTHON)

        try:
            # Try to create a network socket (should fail due to network_mode="none")
            files = {
                "test_network.py": SubmissionFile("test_network.py", """
import socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('8.8.8.8', 53))
    print('Network available')
    sock.close()
except Exception as e:
    print(f'Network blocked: {type(e).__name__}')
""")
            }
            sandbox.prepare_workdir(files)

            response = sandbox.run_process(ProcessRequest.command("python3 test_network.py"))

            # Should indicate network is blocked
            self.assertIn("Network blocked", response.stdout)

        finally:
            self.manager.dispose(sandbox)

    def test_file_system_limits(self):
        """Test that file system has size limits."""
        sandbox = self.manager.acquire(Language.PYTHON)

        try:
            # Try to create a very large file
            # This should be constrained by tmpfs size limits
            files = {
                "test.py": SubmissionFile("test.py", """
try:
    chunk = 'x' * (1024 * 1024)
    with open('large.txt', 'w') as f:
        # Try to write 100MB in 1MB chunks (the file size and tmpfs limits stop it).
        # One 100MB string would instead exhaust the 128MB memory limit and kill
        # the whole container, which is a different limit (see test_process_contract).
        for _ in range(100):
            f.write(chunk)
    print('SUCCESS')
except Exception as e:
    print(f'FAILED: {type(e).__name__}')
""")
            }
            sandbox.prepare_workdir(files)

            response = sandbox.run_process(ProcessRequest.command("python3 test.py"))

            # Should fail due to space constraints
            # Either OSError or system limit reached
            self.assertTrue(
                "FAILED" in response.stdout or response.exit_code != 0,
                "Large file creation should be constrained"
            )

        finally:
            self.manager.dispose(sandbox)

    def test_process_isolation(self):
        """Test that processes run as non-root user."""
        sandbox = self.manager.acquire(Language.PYTHON)

        try:
            # Check current user
            response = sandbox.run_process(ProcessRequest.command("whoami"))

            self.assertEqual(response.exit_code, 0)
            self.assertIn("sandbox", response.stdout)
            self.assertNotIn("root", response.stdout)

        finally:
            self.manager.dispose(sandbox)


if __name__ == '__main__':
    unittest.main()

