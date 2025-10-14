import sys
import os
import json

# This is a common pattern to make sibling directories importable
# We need to add the project's root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from autograder.builder.template_library.templates.api_testing import ApiTestingTemplate
from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig
from autograder.context import request_context


def create_mock_submission():
    """Creates the in-memory files for a simple student Express.js API."""

    # package.json to define dependencies
    package_json = {
        "name": "student-api",
        "version": "1.0.0",
        "main": "server.js",
        "scripts": {
            "start": "node server.js"
        },
        "dependencies": {
            "express": "^4.17.1"
        }
    }

    # server.js - the student's actual API code
    server_js = """
    const express = require('express');
    const app = express();
    const port = 8000;

    app.get('/health', (req, res) => {
      res.status(200).send({ status: 'ok' });
    });

    app.get('/api/user', (req, res) => {
      res.json({ userId: 1, name: 'John Doe' });
    });

    app.listen(port, () => {
      console.log(`Server listening at http://localhost:${port}`);
    });
    """

    return {
        "package.json": json.dumps(package_json, indent=2),
        "server.js": server_js
    }


def create_mock_configs():
    """Creates the mock setup and criteria configurations."""

    setup_config = {
        "runtime_image": "node:18-alpine",
        "container_port": 8000,
        "start_command": "node server.js",
        "commands": {
            "install_dependencies": "npm install"
        }
    }

    criteria_config = {
        "base": {
            "subjects": {
                "api_functionality": {
                    "weight": 100,
                    "tests": [
                        {"name": "health_check", "calls": [["/health"]]},
                        {"name": "check_response_json", "calls": [["/api/user", "userId", 1]]}
                    ]
                }
            }
        }
    }

    return setup_config, criteria_config


def main():
    """Main function to run the mock test execution."""

    print("--- 1. Setting up mock environment ---")
    submission_files = create_mock_submission()
    setup_config, criteria_config = create_mock_configs()

    # The AssignmentConfig object holds all configurations
    assignment_config = AssignmentConfig(
        criteria=criteria_config,
        feedback=None,  # Not needed for this test
        setup=setup_config
    )

    # The AutograderRequest encapsulates everything needed for a grading job
    autograder_request = AutograderRequest(
        submission_files=submission_files,
        assignment_config=assignment_config,
        student_name="MockStudent"
    )

    # Set the global context so the SandboxExecutor can find the request
    request_context.set_request(autograder_request)

    print("--- 2. Initializing API Testing Template ---")
    # This is where the SandboxExecutor is started and the container is built.
    template = None
    try:
        template = ApiTestingTemplate()

        print("\n--- 3. Running Tests ---")

        # Test 1: Health Check
        health_check_test = template.get_test("health_check")
        # Arguments are from the 'calls' array in the criteria config
        health_result = health_check_test.execute("/health")

        print("\n--- Health Check Result ---")
        print(f"Score: {health_result.score}")
        print(f"Report: {health_result.report}")
        print("---------------------------")

        # Test 2: JSON Response Check
        json_check_test = template.get_test("check_response_json")
        # Arguments are from the 'calls' array in the criteria config
        json_result = json_check_test.execute("/api/user", "userId", 1)

        print("\n--- JSON Check Result ---")
        print(f"Score: {json_result.score}")
        print(f"Report: {json_result.report}")
        print("-------------------------")

    except Exception as e:
        print(f"\nAN ERROR OCCURRED: {e}")
        # It's good practice to log the full traceback for debugging
        import traceback
        traceback.print_exc()

    finally:
        # CRITICAL: This block ensures the container is always stopped and removed.
        if template:
            print("\n--- 4. Cleaning up sandbox environment ---")
            template.stop()


if __name__ == "__main__":
    print("=== Starting API Testing Template Test ===")
    #main()
