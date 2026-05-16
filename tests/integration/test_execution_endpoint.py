"""
Test the Deliberate Code Execution feature.

This script tests the execution endpoint with various scenarios.
"""

import pytest
from httpx import AsyncClient
from web.main import app

BASE_URL = "/api/v1/execute"


@pytest.mark.asyncio
class TestExecutionEndpoint:
    """Integration tests for the Deliberate Code Execution endpoint."""

    async def test_simple_python_execution(self):
        """Test simple Python code execution without inputs."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "python",
                "submission_files": [
                    {
                        "filename": "main.py",
                        "content": "print('Hello, World!')"
                    }
                ],
                "program_command": "python main.py"
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 200
            data = response.json()
            assert "Hello, World!" in data["output"]
            assert data["category"] == "success"

    async def test_python_with_input(self):
        """Test Python code with stdin input."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "python",
                "submission_files": [
                    {
                        "filename": "main.py",
                        "content": "name = input('Enter name: ')\\nprint(f'Hello, {name}!')"
                    }
                ],
                "program_command": "python main.py",
                "inputs": [["Alice"]]
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 200
            data = response.json()
            assert "Hello, Alice!" in data["output"]

    async def test_python_runtime_error(self):
        """Test Python code with runtime error."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "python",
                "submission_files": [
                    {
                        "filename": "main.py",
                        "content": "x = 1 / 0  # Division by zero"
                    }
                ],
                "program_command": "python main.py"
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 200
            data = response.json()
            assert data["category"] == "runtime_error"
            assert data["error_message"] is not None

    async def test_java_execution(self):
        """Test Java code execution."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "java",
                "submission_files": [
                    {
                        "filename": "Main.java",
                        "content": """
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello from Java!");
    }
}
"""
                    }
                ],
                "program_command": "javac Main.java && java Main"
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 200
            data = response.json()
            assert "Hello from Java!" in data["output"]

    async def test_node_execution(self):
        """Test Node.js code execution."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "node",
                "submission_files": [
                    {
                        "filename": "app.js",
                        "content": "console.log('Hello from Node.js!');"
                    }
                ],
                "program_command": "node app.js"
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 200
            data = response.json()
            assert "Hello from Node.js!" in data["output"]

    async def test_cpp_execution(self):
        """Test C++ code execution."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "cpp",
                "submission_files": [
                    {
                        "filename": "main.cpp",
                        "content": """
#include <iostream>
using namespace std;

int main() {
    cout << "Hello from C++!" << endl;
    return 0;
}
"""
                    }
                ],
                "program_command": "g++ main.cpp -o main && ./main"
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 200
            data = response.json()
            assert "Hello from C++!" in data["output"]

    async def test_c_execution(self):
        """Test C code execution."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "c",
                "submission_files": [
                    {
                        "filename": "main.c",
                        "content": """
#include <stdio.h>

int main() {
    printf("Hello from C!\\n");
    return 0;
}
"""
                    }
                ],
                "program_command": "gcc main.c -o main && ./main"
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 200
            data = response.json()
            assert "Hello from C!" in data["output"]

    async def test_multiple_files(self):
        """Test execution with multiple files."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "python",
                "submission_files": [
                    {
                        "filename": "main.py",
                        "content": "from utils import greet\\ngreet('World')"
                    },
                    {
                        "filename": "utils.py",
                        "content": "def greet(name):\\n    print(f'Hello, {name}!')"
                    }
                ],
                "program_command": "python main.py"
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 200
            data = response.json()
            assert "Hello, World!" in data["output"]

    async def test_invalid_language(self):
        """Test with invalid language."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            request = {
                "language": "rust",  # Not supported
                "submission_files": [
                    {
                        "filename": "main.rs",
                        "content": "fn main() { println!(\"Hello\"); }"
                    }
                ],
                "program_command": "rustc main.rs && ./main"
            }

            response = await client.post(BASE_URL, json=request)
            assert response.status_code == 422  # Validation error
