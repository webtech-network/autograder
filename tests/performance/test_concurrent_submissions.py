"""
Concurrent Performance Testing for Autograder System

This script tests the autograder's ability to handle multiple simultaneous submissions
across different languages and scenarios.
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import httpx
import json


@dataclass
class SubmissionResult:
    """Track results of a single submission."""
    submission_id: int
    language: str
    status_code: int
    submission_time_ms: float
    grading_time_ms: float = 0.0
    final_score: float = None
    success: bool = False
    error: str = None


@dataclass
class PerformanceMetrics:
    """Performance metrics for concurrent testing."""
    total_submissions: int
    successful_submissions: int
    failed_submissions: int
    total_time_seconds: float
    avg_submission_time_ms: float
    avg_grading_time_ms: float
    min_submission_time_ms: float
    max_submission_time_ms: float
    submissions_per_second: float
    results: List[SubmissionResult] = field(default_factory=list)


class ConcurrentTester:
    """Test autograder with concurrent submissions."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.assignment_id = None

    async def setup_assignment(self) -> str:
        """Create a test assignment configuration."""
        print("Setting up test assignment...")

        config = {
            "external_assignment_id": f"perf-test-{int(time.time())}",
            "template_name": "input_output",
            "languages": ["python", "java", "node", "cpp"],
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
                                {
                                    "name": "program_command",
                                    "value": {
                                        "python": "python3 calculator.py",
                                        "java": "java Calculator",
                                        "node": "node calculator.js",
                                        "cpp": "./calculator"
                                    }
                                }
                            ]
                        },
                        {
                            "name": "expect_output",
                            "parameters": [
                                {"name": "inputs", "value": ["10", "7"]},
                                {"name": "expected_output", "value": "17"},
                                {
                                    "name": "program_command",
                                    "value": {
                                        "python": "python3 calculator.py",
                                        "java": "java Calculator",
                                        "node": "node calculator.js",
                                        "cpp": "./calculator"
                                    }
                                }
                            ]
                        }
                    ]
                }
            },
            "setup_config": {
                "python": {
                    "required_files": ["calculator.py"],
                    "setup_commands": []
                },
                "java": {
                    "required_files": ["Calculator.java"],
                    "setup_commands": ["javac Calculator.java"]
                },
                "node": {
                    "required_files": ["calculator.js"],
                    "setup_commands": []
                },
                "cpp": {
                    "required_files": ["calculator.cpp"],
                    "setup_commands": ["g++ calculator.cpp -o calculator"]
                }
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/configs",
                json=config,
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                self.assignment_id = data["external_assignment_id"]
                print(f"✓ Assignment created: {self.assignment_id}")
                return self.assignment_id
            else:
                raise Exception(f"Failed to create assignment: {response.text}")

    async def submit_code(
        self,
        user_id: str,
        language: str,
        code: str,
        filename: str
    ) -> SubmissionResult:
        """Submit code and track timing."""
        start_time = time.time()

        submission_data = {
            "external_assignment_id": self.assignment_id,
            "external_user_id": user_id,
            "username": f"user_{user_id}",
            "files": [
                {
                    "filename": filename,
                    "content": code
                }
            ],
            "language": language
        }

        result = SubmissionResult(
            submission_id=0,
            language=language,
            status_code=0,
            submission_time_ms=0.0
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/submissions",
                    json=submission_data,
                    timeout=60.0
                )

                submission_time = (time.time() - start_time) * 1000
                result.submission_time_ms = submission_time
                result.status_code = response.status_code

                if response.status_code == 200:
                    data = response.json()
                    result.submission_id = data["id"]
                    result.success = True
                else:
                    result.error = f"HTTP {response.status_code}: {response.text[:100]}"

        except Exception as e:
            result.error = str(e)
            result.submission_time_ms = (time.time() - start_time) * 1000

        return result

    async def wait_for_grading(self, submission_id: int, timeout: int = 60) -> Dict[str, Any]:
        """Wait for submission to be graded."""
        start_time = time.time()

        async with httpx.AsyncClient() as client:
            while time.time() - start_time < timeout:
                try:
                    response = await client.get(
                        f"{self.base_url}/api/v1/submissions/{submission_id}",
                        timeout=10.0
                    )

                    if response.status_code == 200:
                        data = response.json()

                        if data["status"] in ["completed", "failed"]:
                            grading_time = (time.time() - start_time) * 1000
                            return {
                                "status": data["status"],
                                "final_score": data.get("final_score"),
                                "grading_time_ms": grading_time
                            }

                except Exception as e:
                    pass

                await asyncio.sleep(0.5)

        return {
            "status": "timeout",
            "final_score": None,
            "grading_time_ms": timeout * 1000
        }

    def get_sample_code(self, language: str) -> tuple[str, str]:
        """Get sample code for each language."""
        if language == "python":
            return (
                "a = int(input())\nb = int(input())\nprint(a + b)",
                "calculator.py"
            )
        elif language == "java":
            return (
                """import java.util.Scanner;
public class Calculator {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int a = sc.nextInt();
        int b = sc.nextInt();
        System.out.println(a + b);
        sc.close();
    }
}""",
                "Calculator.java"
            )
        elif language == "node":
            return (
                """const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
const lines = [];
rl.on('line', l => {
    lines.push(l);
    if (lines.length === 2) {
        console.log(parseInt(lines[0]) + parseInt(lines[1]));
        rl.close();
    }
});""",
                "calculator.js"
            )
        elif language == "cpp":
            return (
                """#include <iostream>
int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a + b << std::endl;
    return 0;
}""",
                "calculator.cpp"
            )

    async def run_concurrent_test(
        self,
        num_submissions: int,
        languages: List[str] = None,
        wait_for_grading: bool = True
    ) -> PerformanceMetrics:
        """Run concurrent submission test."""
        if languages is None:
            languages = ["python", "java", "node", "cpp"]

        print(f"\n{'='*60}")
        print(f"Running concurrent test: {num_submissions} submissions")
        print(f"Languages: {', '.join(languages)}")
        print(f"Wait for grading: {wait_for_grading}")
        print(f"{'='*60}\n")

        # Ensure assignment exists
        if not self.assignment_id:
            await self.setup_assignment()

        # Prepare submissions
        tasks = []
        for i in range(num_submissions):
            language = languages[i % len(languages)]
            code, filename = self.get_sample_code(language)

            task = self.submit_code(
                user_id=f"{i:04d}",
                language=language,
                code=code,
                filename=filename
            )
            tasks.append(task)

        # Submit all concurrently
        print(f"Submitting {num_submissions} submissions concurrently...")
        start_time = time.time()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        print(f"✓ All submissions completed in {total_time:.2f}s")

        # Wait for grading if requested
        if wait_for_grading:
            print(f"\nWaiting for grading to complete...")
            grading_tasks = []

            for result in results:
                if isinstance(result, SubmissionResult) and result.success:
                    grading_tasks.append(
                        self.wait_for_grading(result.submission_id)
                    )

            grading_results = await asyncio.gather(*grading_tasks, return_exceptions=True)

            # Update results with grading info
            grading_idx = 0
            for result in results:
                if isinstance(result, SubmissionResult) and result.success:
                    if grading_idx < len(grading_results):
                        grading_info = grading_results[grading_idx]
                        if isinstance(grading_info, dict):
                            result.grading_time_ms = grading_info.get("grading_time_ms", 0)
                            result.final_score = grading_info.get("final_score")
                        grading_idx += 1

        # Calculate metrics
        valid_results = [r for r in results if isinstance(r, SubmissionResult)]
        successful = [r for r in valid_results if r.success]
        failed = [r for r in valid_results if not r.success]

        submission_times = [r.submission_time_ms for r in valid_results]
        grading_times = [r.grading_time_ms for r in successful if r.grading_time_ms > 0]

        metrics = PerformanceMetrics(
            total_submissions=num_submissions,
            successful_submissions=len(successful),
            failed_submissions=len(failed),
            total_time_seconds=total_time,
            avg_submission_time_ms=statistics.mean(submission_times) if submission_times else 0,
            avg_grading_time_ms=statistics.mean(grading_times) if grading_times else 0,
            min_submission_time_ms=min(submission_times) if submission_times else 0,
            max_submission_time_ms=max(submission_times) if submission_times else 0,
            submissions_per_second=num_submissions / total_time if total_time > 0 else 0,
            results=valid_results
        )

        return metrics

    def print_metrics(self, metrics: PerformanceMetrics):
        """Print performance metrics."""
        print(f"\n{'='*60}")
        print("PERFORMANCE METRICS")
        print(f"{'='*60}")
        print(f"Total Submissions:    {metrics.total_submissions}")
        print(f"Successful:           {metrics.successful_submissions} ({metrics.successful_submissions/metrics.total_submissions*100:.1f}%)")
        print(f"Failed:               {metrics.failed_submissions}")
        print(f"Total Time:           {metrics.total_time_seconds:.2f}s")
        print(f"Throughput:           {metrics.submissions_per_second:.2f} submissions/sec")
        print(f"\nSubmission Times:")
        print(f"  Average:            {metrics.avg_submission_time_ms:.0f}ms")
        print(f"  Min:                {metrics.min_submission_time_ms:.0f}ms")
        print(f"  Max:                {metrics.max_submission_time_ms:.0f}ms")

        if metrics.avg_grading_time_ms > 0:
            print(f"\nGrading Times:")
            print(f"  Average:            {metrics.avg_grading_time_ms:.0f}ms")

        # Language breakdown
        lang_stats = {}
        for result in metrics.results:
            if result.language not in lang_stats:
                lang_stats[result.language] = {"total": 0, "success": 0}
            lang_stats[result.language]["total"] += 1
            if result.success:
                lang_stats[result.language]["success"] += 1

        print(f"\nLanguage Breakdown:")
        for lang, stats in sorted(lang_stats.items()):
            success_rate = stats["success"] / stats["total"] * 100
            print(f"  {lang:8s}:          {stats['success']}/{stats['total']} ({success_rate:.1f}%)")

        print(f"{'='*60}\n")


async def main():
    """Run performance tests."""
    tester = ConcurrentTester()

    # Test scenarios
    scenarios = [
        {"num": 5, "wait": True, "name": "5 concurrent (with grading)"},
        {"num": 10, "wait": True, "name": "10 concurrent (with grading)"},
        {"num": 20, "wait": False, "name": "20 concurrent (submissions only)"},
        {"num": 50, "wait": False, "name": "50 concurrent (submissions only)"},
    ]

    all_metrics = []

    for scenario in scenarios:
        print(f"\n\n{'#'*60}")
        print(f"# Test: {scenario['name']}")
        print(f"{'#'*60}")

        metrics = await tester.run_concurrent_test(
            num_submissions=scenario["num"],
            wait_for_grading=scenario["wait"]
        )

        tester.print_metrics(metrics)
        all_metrics.append((scenario["name"], metrics))

        # Small delay between scenarios
        await asyncio.sleep(2)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY OF ALL TESTS")
    print(f"{'='*60}")

    for name, metrics in all_metrics:
        print(f"\n{name}:")
        print(f"  Success Rate: {metrics.successful_submissions}/{metrics.total_submissions} ({metrics.successful_submissions/metrics.total_submissions*100:.1f}%)")
        print(f"  Throughput:   {metrics.submissions_per_second:.2f} submissions/sec")
        print(f"  Avg Time:     {metrics.avg_submission_time_ms:.0f}ms")


if __name__ == "__main__":
    print("="*60)
    print("Autograder Concurrent Performance Test")
    print("="*60)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()

