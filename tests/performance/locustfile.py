"""
Locust load testing configuration for autograder.

Install: pip install locust
Run: locust -f tests/performance/locustfile.py --host=http://localhost:8000
"""

from locust import HttpUser, task, between, events
import random
import json


# Code samples for different languages
CODE_SAMPLES = {
    "python": {
        "filename": "calculator.py",
        "content": "a = int(input())\nb = int(input())\nprint(a + b)"
    },
    "java": {
        "filename": "Calculator.java",
        "content": """import java.util.Scanner;
public class Calculator {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int a = sc.nextInt();
        int b = sc.nextInt();
        System.out.println(a + b);
        sc.close();
    }
}"""
    },
    "node": {
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
    },
    "cpp": {
        "filename": "calculator.cpp",
        "content": """#include <iostream>
int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a + b << std::endl;
    return 0;
}"""
    }
}

# Assignment ID (should be created before running)
ASSIGNMENT_ID = "calc-multi-lang"


class AutograderUser(HttpUser):
    """Simulates a user submitting code to the autograder."""

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a simulated user starts."""
        self.user_id = random.randint(10000, 99999)

    @task(10)  # Weight: 10 (most common operation)
    def submit_code(self):
        """Submit code for grading."""
        # Randomly select a language
        language = random.choice(list(CODE_SAMPLES.keys()))
        code_info = CODE_SAMPLES[language]

        # Prepare submission
        submission = {
            "external_assignment_id": ASSIGNMENT_ID,
            "external_user_id": f"locust-{self.user_id}",
            "username": f"user{self.user_id}",
            "files": [
                {
                    "filename": code_info["filename"],
                    "content": code_info["content"]
                }
            ],
            "language": language
        }

        # Submit
        with self.client.post(
            "/api/v1/submissions",
            json=submission,
            catch_response=True,
            name=f"Submit [{language}]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                submission_id = data.get("id")

                # Store for potential later retrieval
                if not hasattr(self, 'submissions'):
                    self.submissions = []
                self.submissions.append(submission_id)

                response.success()
            else:
                response.failure(f"Submission failed: {response.status_code}")

    @task(3)  # Weight: 3
    def check_submission(self):
        """Check status of a previous submission."""
        if not hasattr(self, 'submissions') or not self.submissions:
            return

        # Pick a random submission to check
        submission_id = random.choice(self.submissions)

        with self.client.get(
            f"/api/v1/submissions/{submission_id}",
            catch_response=True,
            name="Check Submission"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # Remove from list
                self.submissions.remove(submission_id)
                response.failure("Submission not found")
            else:
                response.failure(f"Check failed: {response.status_code}")

    @task(1)  # Weight: 1 (less common)
    def get_assignment_config(self):
        """Retrieve assignment configuration."""
        with self.client.get(
            f"/api/v1/configs/{ASSIGNMENT_ID}",
            catch_response=True,
            name="Get Config"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Config retrieval failed: {response.status_code}")


@events.init_command_line_parser.add_listener
def _(parser):
    """Add custom command line arguments."""
    parser.add_argument(
        "--assignment-id",
        type=str,
        default="calc-multi-lang",
        help="Assignment ID to use for testing"
    )


@events.test_start.add_listener
def _(environment, **kwargs):
    """Called before test starts."""
    global ASSIGNMENT_ID
    if environment.parsed_options:
        ASSIGNMENT_ID = environment.parsed_options.assignment_id

    print(f"\n{'='*60}")
    print("Locust Load Test Starting")
    print(f"Assignment ID: {ASSIGNMENT_ID}")
    print(f"{'='*60}\n")

