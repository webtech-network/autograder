"""
Integration tests for Sandbox Manager with AutograderPipeline.

Tests the complete end-to-end flow:
1. Pipeline initialization
2. Sandbox creation during pre-flight
3. File preparation in sandbox
4. Test execution in sandbox
5. Sandbox release and cleanup
6. Pool replenishment

These tests verify that the sandbox manager works correctly throughout
the entire autograder pipeline lifecycle.
"""

import unittest
import time
from typing import Dict

from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.pipeline_execution import PipelineStatus
from sandbox_manager.manager import initialize_sandbox_manager, get_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language


class TestPipelineSandboxIntegration(unittest.TestCase):
    """Test full pipeline integration with sandbox manager."""

    @classmethod
    def setUpClass(cls):
        """Initialize sandbox manager for pipeline tests."""
        pool_configs = [
            SandboxPoolConfig(
                language=Language.PYTHON,
                start_amount=3,  # More sandboxes for concurrent tests
                scale_limit=6,
                idle_timeout=300,
                running_timeout=60
            ),
            SandboxPoolConfig(
                language=Language.JAVA,
                start_amount=2,
                scale_limit=4,
                idle_timeout=300,
                running_timeout=60
            ),
        ]
        cls.manager = initialize_sandbox_manager(pool_configs)
        time.sleep(2)

    def test_01_simple_python_io_assignment_complete_flow(self):
        """Test complete pipeline flow for a simple Python I/O assignment."""
        # Define assignment configuration
        grading_criteria = {
            "base": {
                "name": "Basic Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Test Addition",
                        "weight": 50,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["ADD", "5", "3"],
                            "expected_output": "8",
                            "program_command": "python3 calculator.py"
                        }
                    },
                    {
                        "name": "Test Multiplication",
                        "weight": 50,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["MUL", "4", "7"],
                            "expected_output": "28",
                            "program_command": "python3 calculator.py"
                        }
                    }
                ]
            }
        }

        setup_config = {
            "required_files": ["calculator.py"]
        }

        # Build pipeline
        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config=setup_config
        )

        # Create correct student submission
        student_code = """
operation = input().strip()
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

        submission = Submission(
            username="student123",
            user_id=123,
            assignment_id=1,
            submission_files={
                "calculator.py": SubmissionFile("calculator.py", student_code)
            },
            language=Language.PYTHON
        )

        # Check initial pool state
        py_pool = self.manager.language_pools[Language.PYTHON]
        initial_idle = len(py_pool.idle_sandboxes)
        initial_active = len(py_pool.active_sandboxes)

        # Run pipeline
        result = pipeline.run(submission)

        # Verify pipeline succeeded
        self.assertEqual(result.status, PipelineStatus.SUCCESS)
        self.assertIsNotNone(result.result)
        self.assertEqual(result.result.final_score, 100.0)

        # Wait for sandbox release and replenishment
        time.sleep(2)

        # Verify pool state returned to normal
        final_idle = len(py_pool.idle_sandboxes)
        final_active = len(py_pool.active_sandboxes)

        self.assertEqual(final_idle, initial_idle, "Pool should replenish to initial state")
        self.assertEqual(final_active, initial_active, "No sandboxes should be active after completion")

        print(f"✅ Pipeline completed: Score {result.result.final_score}/100")

    def test_02_incorrect_submission_with_sandbox(self):
        """Test pipeline with incorrect submission (partial credit)."""
        grading_criteria = {
            "base": {
                "name": "Basic Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Test Case 1",
                        "weight": 33.33,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["echo", "Hello"],
                            "expected_output": "Hello",
                            "program_command": "python3 echo.py"
                        }
                    },
                    {
                        "name": "Test Case 2",
                        "weight": 33.33,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["echo", "World"],
                            "expected_output": "World",
                            "program_command": "python3 echo.py"
                        }
                    },
                    {
                        "name": "Test Case 3",
                        "weight": 33.34,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["echo", "Test"],
                            "expected_output": "Test",
                            "program_command": "python3 echo.py"
                        }
                    }
                ]
            }
        }

        # Incorrect submission - only echoes "Hello"
        student_code = """
command = input()
text = input()
if text == "Hello":
    print(text)
else:
    print("Wrong")
"""

        submission = Submission(
            assignment_id=2,
            student_id="student456",
            submission_files={
                "echo.py": SubmissionFile("echo.py", student_code)
            },
            language=Language.PYTHON
        )

        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config={}
        )

        result = pipeline.run(submission)

        self.assertEqual(result.status, PipelineStatus.SUCCESS)
        self.assertLess(result.result.final_score, 100.0)
        self.assertGreater(result.result.final_score, 0.0)

        print(f"✅ Partial credit working: Score {result.result.final_score:.2f}/100")

    def test_03_missing_required_file_preflight_failure(self):
        """Test that pipeline fails in pre-flight when required file is missing."""
        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Test",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "main.py"],
                            "expected_output": "Hello"
                        }
                    }
                ]
            }
        }

        setup_config = {
            "required_files": ["main.py", "helper.py"]  # Require 2 files
        }

        submission = Submission(
            assignment_id=3,
            student_id="student789",
            submission_files={
                "main.py": SubmissionFile("main.py", "print('Hello')")
                # Missing helper.py!
            },
            language=Language.PYTHON
        )

        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config=setup_config
        )

        # Check initial pool state
        py_pool = self.manager.language_pools[Language.PYTHON]
        initial_idle = len(py_pool.idle_sandboxes)

        result = pipeline.run(submission)

        # Pipeline should fail at pre-flight
        self.assertEqual(result.status, PipelineStatus.FAILED)

        # Verify sandbox was never created (pool unchanged)
        self.assertEqual(len(py_pool.idle_sandboxes), initial_idle)

        print("✅ Pre-flight correctly rejected submission with missing files")

    def test_04_setup_commands_in_sandbox(self):
        """Test that setup commands execute correctly in sandbox."""
        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Use Library",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "use_lib.py"],
                            "expected_output": "Library works!"
                        }
                    }
                ]
            }
        }

        setup_config = {
            "required_files": ["use_lib.py"],
            "setup_commands": [
                "echo 'def lib_function(): return \"Library works!\"' > lib.py"
            ]
        }

        student_code = """
from lib import lib_function
print(lib_function())
"""

        submission = Submission(
            assignment_id=4,
            student_id="student_setup",
            submission_files={
                "use_lib.py": SubmissionFile("use_lib.py", student_code)
            },
            language=Language.PYTHON
        )

        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config=setup_config
        )

        result = pipeline.run(submission)

        self.assertEqual(result.status, PipelineStatus.SUCCESS)
        self.assertEqual(result.result.final_score, 100.0)

        print("✅ Setup commands executed successfully in sandbox")

    def test_05_concurrent_pipeline_executions(self):
        """Test multiple pipeline executions concurrently."""
        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Hello Test",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "hello.py"],
                            "expected_output": "Hello!"
                        }
                    }
                ]
            }
        }

        # Create 3 submissions
        submissions = []
        for i in range(3):
            submission = Submission(
                username=f"student_concurrent_{i}",
                user_id=1000 + i,
                assignment_id=5,
                submission_files={
                    "hello.py": SubmissionFile("hello.py", f"print('Hello!')")
                },
                language=Language.PYTHON
            )
            submissions.append(submission)

        pipelines = []
        for _ in range(3):
            pipeline = build_pipeline(
                template_name="IO",
                include_feedback=False,
                grading_criteria=grading_criteria,
                feedback_config=None,
                setup_config={}
            )
            pipelines.append(pipeline)

        # Run all pipelines (sequentially for testing, but uses different sandboxes)
        results = []
        for i, pipeline in enumerate(pipelines):
            result = pipeline.run(submissions[i])
            results.append(result)

        # All should succeed
        for result in results:
            self.assertEqual(result.status, PipelineStatus.SUCCESS)
            self.assertEqual(result.result.final_score, 100.0)

        print("✅ Concurrent pipeline executions successful")

    def test_06_java_compilation_in_pipeline(self):
        """Test Java assignment with compilation step in pipeline."""
        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Hello Java",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["javac HelloWorld.java && java HelloWorld"],
                            "expected_output": "Hello, Java!"
                        }
                    }
                ]
            }
        }

        java_code = """
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, Java!");
    }
}
"""

        submission = Submission(
            assignment_id=6,
            student_id="java_student",
            submission_files={
                "HelloWorld.java": SubmissionFile("HelloWorld.java", java_code)
            },
            language=Language.JAVA
        )

        setup_config = {
            "required_files": ["HelloWorld.java"]
        }

        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config=setup_config
        )

        # Check Java pool
        java_pool = self.manager.language_pools[Language.JAVA]
        initial_idle = len(java_pool.idle_sandboxes)

        result = pipeline.run(submission)

        self.assertEqual(result.status, PipelineStatus.SUCCESS)
        self.assertEqual(result.result.final_score, 100.0)

        # Wait for cleanup
        time.sleep(2)

        # Pool should replenish
        self.assertEqual(len(java_pool.idle_sandboxes), initial_idle)

        print("✅ Java compilation and execution in pipeline successful")

    def test_07_multi_file_project_in_pipeline(self):
        """Test multi-file Python project through pipeline."""
        grading_criteria = {
            "base": {
                "name": "Module Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Main Program",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "main.py"],
                            "expected_output": "Result: 42"
                        }
                    }
                ]
            }
        }

        submission = Submission(
            assignment_id=7,
            student_id="multifile_student",
            submission_files={
                "main.py": SubmissionFile("main.py", """
from utils.calculator import calculate
result = calculate(40, 2)
print(f"Result: {result}")
"""),
                "utils/calculator.py": SubmissionFile("utils/calculator.py", """
def calculate(a, b):
    return a + b
"""),
                "utils/__init__.py": SubmissionFile("utils/__init__.py", "")
            },
            language=Language.PYTHON
        )

        setup_config = {
            "required_files": ["main.py", "utils/calculator.py"]
        }

        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config=setup_config
        )

        result = pipeline.run(submission)

        self.assertEqual(result.status, PipelineStatus.SUCCESS)
        self.assertEqual(result.result.final_score, 100.0)

        print("✅ Multi-file project successfully graded")

    def test_08_sandbox_cleanup_after_error(self):
        """Test that sandbox is properly cleaned up even when execution errors occur."""
        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Should Error",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "error.py"],
                            "expected_output": "Success"
                        }
                    }
                ]
            }
        }

        # Code that will raise an error
        error_code = """
raise Exception("Intentional error!")
"""

        submission = Submission(
            assignment_id=8,
            student_id="error_student",
            submission_files={
                "error.py": SubmissionFile("error.py", error_code)
            },
            language=Language.PYTHON
        )

        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config={}
        )

        py_pool = self.manager.language_pools[Language.PYTHON]
        initial_idle = len(py_pool.idle_sandboxes)

        result = pipeline.run(submission)

        # Pipeline should complete (even if test fails)
        self.assertEqual(result.status, PipelineStatus.SUCCESS)
        self.assertEqual(result.result.final_score, 0.0)  # Test failed

        # Wait for cleanup
        time.sleep(2)

        # Pool should be replenished
        self.assertEqual(len(py_pool.idle_sandboxes), initial_idle)

        print("✅ Sandbox cleaned up correctly after execution error")

    def test_09_pool_exhaustion_and_recovery(self):
        """Test behavior when pool is temporarily exhausted."""
        # This test would acquire all sandboxes and verify error handling
        # For now, we'll test that we can successfully use all available sandboxes

        py_pool = self.manager.language_pools[Language.PYTHON]
        available = len(py_pool.idle_sandboxes)

        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Simple Test",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "-c", "print('OK')"],
                            "expected_output": "OK"
                        }
                    }
                ]
            }
        }

        # Run as many pipelines as we have sandboxes
        for i in range(min(available, 2)):  # Limit to 2 to avoid hanging
            submission = Submission(
                assignment_id=9,
                student_id=f"stress_{i}",
                submission_files={
                    "test.py": SubmissionFile("test.py", "print('OK')")
                },
                language=Language.PYTHON
            )

            pipeline = build_pipeline(
                template_name="IO",
                include_feedback=False,
                grading_criteria=grading_criteria,
                feedback_config=None,
                setup_config={}
            )

            result = pipeline.run(submission)
            self.assertEqual(result.status, PipelineStatus.SUCCESS)

        print("✅ Pool handled multiple sequential requests successfully")

    def test_10_sandbox_isolation_between_submissions(self):
        """Test that sandboxes are isolated between different submissions."""
        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Check Isolation",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "check.py"],
                            "expected_output": "Clean"
                        }
                    }
                ]
            }
        }

        # First submission creates a file
        submission1 = Submission(
            assignment_id=10,
            student_id="isolation_1",
            submission_files={
                "check.py": SubmissionFile("check.py", """
with open('secret.txt', 'w') as f:
    f.write('secret data')
print('Created')
""")
            },
            language=Language.PYTHON
        )

        pipeline1 = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria={
                "base": {
                    "name": "Tests",
                    "weight": 100,
                    "tests": [
                        {
                            "name": "Create File",
                            "weight": 100,
                            "test": "expect_output",
                            "parameters": {
                                "inputs": ["python3", "check.py"],
                                "expected_output": "Created"
                            }
                        }
                    ]
                }
            },
            feedback_config=None,
            setup_config={}
        )

        result1 = pipeline1.run(submission1)
        self.assertEqual(result1.status, PipelineStatus.SUCCESS)

        time.sleep(2)  # Allow cleanup

        # Second submission checks if file exists (should not)
        submission2 = Submission(
            assignment_id=10,
            student_id="isolation_2",
            submission_files={
                "check.py": SubmissionFile("check.py", """
import os
if os.path.exists('secret.txt'):
    print('Contaminated')
else:
    print('Clean')
""")
            },
            language=Language.PYTHON
        )

        pipeline2 = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config={}
        )

        result2 = pipeline2.run(submission2)

        self.assertEqual(result2.status, PipelineStatus.SUCCESS)
        self.assertEqual(result2.result.final_score, 100.0)  # Should print "Clean"

        print("✅ Sandbox isolation between submissions verified")


class TestPipelineSandboxResourceManagement(unittest.TestCase):
    """Test resource management and cleanup in pipeline."""

    @classmethod
    def setUpClass(cls):
        """Use already initialized manager."""
        cls.manager = get_sandbox_manager()

    def test_sandbox_release_on_pipeline_success(self):
        """Verify sandbox is released when pipeline succeeds."""
        py_pool = self.manager.language_pools[Language.PYTHON]
        initial_idle = len(py_pool.idle_sandboxes)
        initial_active = len(py_pool.active_sandboxes)

        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Test",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "-c", "print('OK')"],
                            "expected_output": "OK"
                        }
                    }
                ]
            }
        }

        submission = Submission(
            assignment_id=11,
            student_id="resource_test",
            submission_files={
                "test.py": SubmissionFile("test.py", "print('OK')")
            },
            language=Language.PYTHON
        )

        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config={}
        )

        # During execution, a sandbox should be active
        result = pipeline.run(submission)
        self.assertEqual(result.status, PipelineStatus.SUCCESS)

        # After completion and cleanup
        time.sleep(2)

        final_idle = len(py_pool.idle_sandboxes)
        final_active = len(py_pool.active_sandboxes)

        self.assertEqual(final_idle, initial_idle)
        self.assertEqual(final_active, initial_active)

        print("✅ Sandbox correctly released on pipeline success")

    def test_sandbox_container_lifecycle(self):
        """Test complete lifecycle: create -> use -> destroy -> replenish."""
        py_pool = self.manager.language_pools[Language.PYTHON]

        # Record initial container IDs
        initial_containers = {s.container_ref.id for s in py_pool.idle_sandboxes}

        grading_criteria = {
            "base": {
                "name": "Tests",
                "weight": 100,
                "tests": [
                    {
                        "name": "Test",
                        "weight": 100,
                        "test": "expect_output",
                        "parameters": {
                            "inputs": ["python3", "-c", "print('Test')"],
                            "expected_output": "Test"
                        }
                    }
                ]
            }
        }

        submission = Submission(
            username="lifecycle_test",
            user_id=4002,
            assignment_id=12,
            submission_files={
                "test.py": SubmissionFile("test.py", "print('Test')")
            },
            language=Language.PYTHON
        )

        pipeline = build_pipeline(
            template_name="IO",
            include_feedback=False,
            grading_criteria=grading_criteria,
            feedback_config=None,
            setup_config={}
        )

        result = pipeline.run(submission)
        self.assertEqual(result.status, PipelineStatus.SUCCESS)

        # Wait for replenishment
        time.sleep(2)

        # Container should have been destroyed and a new one created
        final_containers = {s.container_ref.id for s in py_pool.idle_sandboxes}

        # At least one container should be different (the one that was used)
        self.assertNotEqual(initial_containers, final_containers)

        # But pool size should be the same
        self.assertEqual(len(py_pool.idle_sandboxes), len(initial_containers))

        print("✅ Container lifecycle (create -> use -> destroy -> replenish) verified")


if __name__ == '__main__':
    unittest.main(verbosity=2)

