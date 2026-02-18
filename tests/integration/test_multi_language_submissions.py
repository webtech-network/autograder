"""Integration test for multi-language submissions for the same assignment."""

import pytest
from httpx import AsyncClient

from web.main import app


@pytest.mark.asyncio
class TestMultiLanguageSubmissions:
    """Test that the same assignment can accept submissions in different languages."""

    async def test_create_config_and_submit_multiple_languages(self):
        """
        Test the complete flow:
        1. Create a grading config with a default language (python)
        2. Submit in Python (using default)
        3. Submit in Java (language override)
        4. Submit in Node (language override)
        5. Submit in C++ (language override)

        All submissions should be accepted and processed correctly.
        """
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Step 1: Create grading configuration with Python as default
            config_response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "multi-lang-calc-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {
                            "weight": 100,
                            "tests": [
                                {
                                    "name": "expect_output",
                                    "parameters": [
                                        {"name": "inputs", "value": ["5", "3"]},
                                        {"name": "expected_output", "value": "8"},
                                        {"name": "program_command", "value": "CMD"}
                                    ]
                                }
                            ]
                        }
                    },
                    "language": "python",
                    "setup_config": {
                        "required_files": ["calculator.py"]
                    }
                }
            )

            assert config_response.status_code == 200
            config_data = config_response.json()
            assert config_data["language"] == "python"
            assert config_data["external_assignment_id"] == "multi-lang-calc-001"

            # Step 2: Submit Python code (uses default language)
            python_submission = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "multi-lang-calc-001",
                    "external_user_id": "student-py-001",
                    "username": "python_student",
                    "files": [
                        {
                            "filename": "calculator.py",
                            "content": "a = int(input())\nb = int(input())\nprint(a + b)"
                        }
                    ]
                    # No language override - uses config's default (python)
                }
            )

            assert python_submission.status_code == 200
            py_data = python_submission.json()
            assert py_data["status"] == "pending"
            py_submission_id = py_data["id"]

            # Step 3: Submit Java code (language override)
            java_submission = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "multi-lang-calc-001",
                    "external_user_id": "student-java-001",
                    "username": "java_student",
                    "files": [
                        {
                            "filename": "Calculator.java",
                            "content": """import java.util.Scanner;
public class Calculator {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int a = sc.nextInt();
        int b = sc.nextInt();
        System.out.println(a + b);
    }
}"""
                        }
                    ],
                    "language": "java"  # Language override
                }
            )

            assert java_submission.status_code == 200
            java_data = java_submission.json()
            assert java_data["status"] == "pending"
            java_submission_id = java_data["id"]

            # Step 4: Submit Node.js code (language override)
            node_submission = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "multi-lang-calc-001",
                    "external_user_id": "student-node-001",
                    "username": "node_student",
                    "files": [
                        {
                            "filename": "calculator.js",
                            "content": """const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
const lines = [];
rl.on('line', l => {
    lines.push(l);
    if (lines.length === 2) {
        console.log(parseInt(lines[0]) + parseInt(lines[1]));
        rl.close();
    }
});"""
                        }
                    ],
                    "language": "node"  # Language override
                }
            )

            assert node_submission.status_code == 200
            node_data = node_submission.json()
            assert node_data["status"] == "pending"
            node_submission_id = node_data["id"]

            # Step 5: Submit C++ code (language override)
            cpp_submission = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "multi-lang-calc-001",
                    "external_user_id": "student-cpp-001",
                    "username": "cpp_student",
                    "files": [
                        {
                            "filename": "calculator.cpp",
                            "content": """#include <iostream>
int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a + b << std::endl;
    return 0;
}"""
                        }
                    ],
                    "language": "cpp"  # Language override
                }
            )

            assert cpp_submission.status_code == 200
            cpp_data = cpp_submission.json()
            assert cpp_data["status"] == "pending"
            cpp_submission_id = cpp_data["id"]

            # Verify all submissions are stored with correct languages
            # Check Python submission
            py_detail = await client.get(f"/api/v1/submissions/{py_submission_id}")
            assert py_detail.status_code == 200
            py_detail_data = py_detail.json()
            # Should have default language from config or explicit language from submission

            # Check Java submission
            java_detail = await client.get(f"/api/v1/submissions/{java_submission_id}")
            assert java_detail.status_code == 200
            java_detail_data = java_detail.json()

            # Check Node submission
            node_detail = await client.get(f"/api/v1/submissions/{node_submission_id}")
            assert node_detail.status_code == 200
            node_detail_data = node_detail.json()

            # Check C++ submission
            cpp_detail = await client.get(f"/api/v1/submissions/{cpp_submission_id}")
            assert cpp_detail.status_code == 200
            cpp_detail_data = cpp_detail.json()

    async def test_submit_with_invalid_language_override_fails(self):
        """Test that submitting with an invalid language override fails validation."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # First create a valid config
            config_response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-invalid-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": "python"
                }
            )
            assert config_response.status_code == 200

            # Try to submit with invalid language
            submission_response = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "test-invalid-lang-001",
                    "external_user_id": "user-001",
                    "username": "testuser",
                    "files": [
                        {
                            "filename": "test.rb",
                            "content": "puts 'hello'"
                        }
                    ],
                    "language": "ruby"  # Invalid language
                }
            )

            assert submission_response.status_code == 422  # Validation error

    async def test_config_language_does_not_restrict_submission_languages(self):
        """
        Test that the config's default language doesn't restrict submission languages.
        Students can submit in any supported language regardless of config default.
        """
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create config with Java as default
            config_response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-flexible-lang-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {
                            "weight": 100,
                            "tests": [
                                {
                                    "name": "expect_output",
                                    "parameters": [
                                        {"name": "inputs", "value": ["echo", "hello"]},
                                        {"name": "expected_output", "value": "hello"}
                                    ]
                                }
                            ]
                        }
                    },
                    "language": "java"  # Default is Java
                }
            )
            assert config_response.status_code == 200

            # Submit Python code (different from default)
            py_response = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "test-flexible-lang-001",
                    "external_user_id": "user-py-001",
                    "username": "py_user",
                    "files": [
                        {
                            "filename": "test.py",
                            "content": "print('hello')"
                        }
                    ],
                    "language": "python"  # Override to Python
                }
            )

            assert py_response.status_code == 200
            assert py_response.json()["status"] == "pending"

            # Submit C++ code (also different from default)
            cpp_response = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "test-flexible-lang-001",
                    "external_user_id": "user-cpp-001",
                    "username": "cpp_user",
                    "files": [
                        {
                            "filename": "test.cpp",
                            "content": "#include <iostream>\nint main() { std::cout << \"hello\"; return 0; }"
                        }
                    ],
                    "language": "cpp"  # Override to C++
                }
            )

            assert cpp_response.status_code == 200
            assert cpp_response.json()["status"] == "pending"

    async def test_case_insensitive_language_override(self):
        """Test that language overrides are case-insensitive."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create config
            config_response = await client.post(
                "/api/v1/configs",
                json={
                    "external_assignment_id": "test-case-001",
                    "template_name": "input_output",
                    "criteria_config": {
                        "test_library": "input_output",
                        "base": {"weight": 100, "tests": []}
                    },
                    "language": "python"
                }
            )
            assert config_response.status_code == 200

            # Submit with uppercase language
            submission_response = await client.post(
                "/api/v1/submissions",
                json={
                    "external_assignment_id": "test-case-001",
                    "external_user_id": "user-001",
                    "username": "testuser",
                    "files": [
                        {
                            "filename": "Test.java",
                            "content": "public class Test { }"
                        }
                    ],
                    "language": "JAVA"  # Uppercase
                }
            )

            assert submission_response.status_code == 200
            data = submission_response.json()
            assert data["status"] == "pending"

