"""
Simple stress test script for quick performance testing.
"""

import asyncio
import httpx
import time
import sys
import json
from datetime import datetime
from pathlib import Path


async def submit_single(client, assignment_id, user_id, language):
    """Submit a single submission and fetch grading results."""
    code_samples = {
        "python": ("a = int(input())\nb = int(input())\nprint(a + b)", "calculator.py"),
        "java": ("import java.util.Scanner;\npublic class Calculator {\n  public static void main(String[] args) {\n    Scanner sc = new Scanner(System.in);\n    System.out.println(sc.nextInt() + sc.nextInt());\n  }\n}", "Calculator.java"),
        "node": ("const readline = require('readline');\nconst rl = readline.createInterface({ input: process.stdin });\nconst lines = [];\nrl.on('line', l => { lines.push(l); if (lines.length === 2) { console.log(parseInt(lines[0]) + parseInt(lines[1])); rl.close(); }});", "calculator.js"),
        "cpp": ("#include <iostream>\nint main() { int a, b; std::cin >> a >> b; std::cout << a + b << std::endl; return 0; }", "calculator.cpp")
    }

    code, filename = code_samples[language]

    start = time.time()
    try:
        response = await client.post(
            "http://localhost:8000/api/v1/submissions",
            json={
                "external_assignment_id": assignment_id,
                "external_user_id": f"stress-{user_id}",
                "username": f"user{user_id}",
                "files": [{"filename": filename, "content": code}],
                "language": language
            },
            timeout=30.0
        )
        elapsed = (time.time() - start) * 1000

        if response.status_code == 200:
            submission_data = response.json()
            submission_id = submission_data["id"]

            # Wait for grading to complete (2 seconds should be enough for simple tests)
            await asyncio.sleep(2)

            # Fetch grading results
            try:
                result_response = await client.get(
                    f"http://localhost:8000/api/v1/submissions/{submission_id}",
                    timeout=10.0
                )
                if result_response.status_code == 200:
                    result_data = result_response.json()
                    return {
                        "success": True,
                        "time": elapsed,
                        "id": submission_id,
                        "status": result_data.get("status", "unknown"),
                        "score": result_data.get("score"),
                        "max_score": result_data.get("max_score"),
                        "grading_completed": result_data.get("status") == "completed"
                    }
            except Exception:
                pass  # If fetching results fails, return basic info

            return {"success": True, "time": elapsed, "id": submission_id, "status": "unknown"}
        else:
            return {"success": False, "time": elapsed, "error": response.status_code}
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {"success": False, "time": elapsed, "error": str(e)}


async def stress_test(num_submissions=10, assignment_id="calc-multi-lang"):
    """Run stress test."""
    print(f"\n{'='*60}")
    print(f"STRESS TEST: {num_submissions} submissions")
    print(f"{'='*60}\n")

    languages = ["python", "java", "node", "cpp"]
    test_start_time = datetime.now()

    async with httpx.AsyncClient() as client:
        # Create tasks
        tasks = []
        submission_details = []
        for i in range(num_submissions):
            lang = languages[i % len(languages)]
            submission_details.append({
                "index": i,
                "user_id": f"stress-{i}",
                "username": f"user{i}",
                "language": lang
            })
            tasks.append(submit_single(client, assignment_id, i, lang))

        # Run concurrently
        print(f"Submitting {num_submissions} requests...")
        start_time = time.time()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        # Analyze results and combine with submission details
        detailed_results = []
        for i, (detail, result) in enumerate(zip(submission_details, results)):
            if isinstance(result, dict):
                detailed_results.append({
                    **detail,
                    "success": result.get("success"),
                    "submission_id": result.get("id"),
                    "response_time_ms": result.get("time"),
                    "status": result.get("status", "unknown"),
                    "score": result.get("score"),
                    "max_score": result.get("max_score"),
                    "grading_completed": result.get("grading_completed", False),
                    "error": result.get("error") if not result.get("success") else None
                })
            else:
                detailed_results.append({
                    **detail,
                    "success": False,
                    "submission_id": None,
                    "response_time_ms": None,
                    "status": "error",
                    "score": None,
                    "max_score": None,
                    "grading_completed": False,
                    "error": str(result)
                })

        successful = sum(1 for r in detailed_results if r["success"])
        failed = len(detailed_results) - successful

        times = [r["response_time_ms"] for r in detailed_results if r["response_time_ms"]]
        avg_time = sum(times) / len(times) if times else 0

        # Calculate score statistics
        graded_results = [r for r in detailed_results if r.get("score") is not None and r.get("max_score") is not None]
        if graded_results:
            perfect_scores = sum(1 for r in graded_results if r["score"] == r["max_score"])
            avg_score = sum(r["score"] for r in graded_results) / len(graded_results)
            avg_max_score = sum(r["max_score"] for r in graded_results) / len(graded_results)
            avg_score_percentage = (avg_score / avg_max_score * 100) if avg_max_score > 0 else 0
        else:
            perfect_scores = 0
            avg_score = 0
            avg_max_score = 0
            avg_score_percentage = 0

        # Prepare dump data
        dump_data = {
            "test_metadata": {
                "test_name": "Stress Test",
                "test_start_time": test_start_time.isoformat(),
                "test_end_time": datetime.now().isoformat(),
                "assignment_id": assignment_id,
                "num_submissions": num_submissions
            },
            "summary": {
                "total_submissions": num_submissions,
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / num_submissions * 100) if num_submissions > 0 else 0,
                "total_time_seconds": total_time,
                "throughput_per_second": num_submissions / total_time if total_time > 0 else 0,
                "avg_response_time_ms": avg_time,
                "min_response_time_ms": min(times) if times else None,
                "max_response_time_ms": max(times) if times else None,
                "graded_count": len(graded_results),
                "perfect_scores": perfect_scores,
                "avg_score": avg_score,
                "avg_max_score": avg_max_score,
                "avg_score_percentage": avg_score_percentage
            },
            "language_breakdown": {},
            "submissions": detailed_results
        }

        # Calculate language-specific stats
        for lang in languages:
            lang_results = [r for r in detailed_results if r["language"] == lang]
            if lang_results:
                lang_successful = sum(1 for r in lang_results if r["success"])
                lang_times = [r["response_time_ms"] for r in lang_results if r["response_time_ms"]]
                dump_data["language_breakdown"][lang] = {
                    "total": len(lang_results),
                    "successful": lang_successful,
                    "failed": len(lang_results) - lang_successful,
                    "success_rate": (lang_successful / len(lang_results) * 100) if lang_results else 0,
                    "avg_response_time_ms": sum(lang_times) / len(lang_times) if lang_times else None
                }

        # Save dump to file
        dump_dir = Path("tests/performance/results")
        dump_dir.mkdir(exist_ok=True)

        timestamp = test_start_time.strftime("%Y%m%d_%H%M%S")
        dump_file = dump_dir / f"stress_test_{num_submissions}subs_{timestamp}.json"

        with open(dump_file, 'w') as f:
            json.dump(dump_data, f, indent=2)

        print(f"\n{'='*60}")
        print(f"RESULTS")
        print(f"{'='*60}")
        print(f"Total Time:      {total_time:.2f}s")
        print(f"Successful:      {successful}/{num_submissions} ({successful/num_submissions*100:.1f}%)")
        print(f"Failed:          {failed}")
        print(f"Throughput:      {num_submissions/total_time:.2f} req/s")
        print(f"Avg Time:        {avg_time:.0f}ms")
        print(f"Min Time:        {min(times):.0f}ms" if times else "N/A")
        print(f"Max Time:        {max(times):.0f}ms" if times else "N/A")
        print(f"{'='*60}")
        print(f"📊 Results saved to: {dump_file}")
        print(f"{'='*60}\n")

        return dump_data


async def main():
    """Run multiple stress test scenarios."""
    if len(sys.argv) > 1:
        # Single test with custom count
        num = int(sys.argv[1])
        await stress_test(num)
    else:
        # Multiple scenarios
        scenarios = [5, 10, 20, 50,100]

        for num in scenarios:
            await stress_test(num)
            await asyncio.sleep(2)  # Cool down


if __name__ == "__main__":
    print("Autograder Stress Test")
    print("Usage: python test_stress.py [num_submissions]")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted")

