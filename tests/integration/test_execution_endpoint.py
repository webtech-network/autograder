"""
Test the Deliberate Code Execution feature.

This script tests the execution endpoint with various scenarios.
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"


def test_simple_python_execution():
    """Test simple Python code execution without inputs."""
    print("\n=== Test 1: Simple Python Execution ===")

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

    response = requests.post(f"{BASE_URL}/execute", json=request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert "Hello, World!" in data["output"]
    assert data["category"] == "success"
    print("✓ Test passed!")


def test_python_with_input():
    """Test Python code with stdin input."""
    print("\n=== Test 2: Python with Input ===")

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

    response = requests.post(f"{BASE_URL}/execute", json=request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert "Hello, Alice!" in data["output"]
    print("✓ Test passed!")


def test_python_runtime_error():
    """Test Python code with runtime error."""
    print("\n=== Test 3: Python Runtime Error ===")

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

    response = requests.post(f"{BASE_URL}/execute", json=request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "runtime_error"
    assert data["error_message"] is not None
    print("✓ Test passed!")


def test_java_execution():
    """Test Java code execution."""
    print("\n=== Test 4: Java Execution ===")

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

    response = requests.post(f"{BASE_URL}/execute", json=request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert "Hello from Java!" in data["output"]
    print("✓ Test passed!")


def test_node_execution():
    """Test Node.js code execution."""
    print("\n=== Test 5: Node.js Execution ===")

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

    response = requests.post(f"{BASE_URL}/execute", json=request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert "Hello from Node.js!" in data["output"]
    print("✓ Test passed!")


def test_cpp_execution():
    """Test C++ code execution."""
    print("\n=== Test 6: C++ Execution ===")

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

    response = requests.post(f"{BASE_URL}/execute", json=request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert "Hello from C++!" in data["output"]
    print("✓ Test passed!")


def test_multiple_files():
    """Test execution with multiple files."""
    print("\n=== Test 7: Multiple Files ===")

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

    response = requests.post(f"{BASE_URL}/execute", json=request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 200
    data = response.json()
    assert "Hello, World!" in data["output"]
    print("✓ Test passed!")


def test_invalid_language():
    """Test with invalid language."""
    print("\n=== Test 8: Invalid Language ===")

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

    response = requests.post(f"{BASE_URL}/execute", json=request)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 422  # Validation error
    print("✓ Test passed!")


if __name__ == "__main__":
    print("Testing Deliberate Code Execution Feature")
    print("=" * 50)

    try:
        test_simple_python_execution()
        test_python_with_input()
        test_python_runtime_error()
        test_java_execution()
        test_node_execution()
        test_cpp_execution()
        test_multiple_files()
        test_invalid_language()

        print("\n" + "=" * 50)
        print("All tests passed! ✓")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except requests.exceptions.ConnectionError:
        print("\n✗ Could not connect to server. Make sure the API is running on http://localhost:8000")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")

