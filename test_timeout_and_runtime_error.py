#!/usr/bin/env python3
"""
Test script to verify timeout handling and runtime error classification.
"""

import asyncio

from sandbox_manager.manager import initialize_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language
from web.schemas.execution import DeliberateCodeExecutionRequest
from web.schemas.submission import SubmissionFileData
from web.service.deliberate_execution_service import execute_code


async def test_runtime_error():
    """Test that runtime errors are properly classified."""
    print("\n=== Testing Runtime Error Classification ===")

    request = DeliberateCodeExecutionRequest(
        language="python",
        submission_files=[
            SubmissionFileData(
                filename="main.py",
                content="""def calculate_ratio(total, count):
    return total / count

# Triggering the error by passing 0 as the count
result = calculate_ratio(100, 0)
print(result)"""
            )
        ],
        program_command="python main.py",
        test_cases=[[]]
    )

    response = await execute_code(request)
    result = response.results[0]

    print(f"Category: {result.category}")
    print(f"Error Message: {result.error_message}")
    print(f"Output: {result.output[:200]}...")
    print(f"Execution Time: {result.execution_time:.3f}s")

    if result.category.value == "runtime_error":
        print("✅ Runtime error correctly classified!")
    else:
        print(f"❌ FAIL: Expected 'runtime_error', got '{result.category.value}'")

    return result.category.value == "runtime_error"


async def test_timeout():
    """Test that infinite loops are properly timed out."""
    print("\n=== Testing Timeout Handling ===")

    request = DeliberateCodeExecutionRequest(
        language="python",
        submission_files=[
            SubmissionFileData(
                filename="main.py",
                content="""import time

counter = 0
while True:
    counter += 1
    # The script will hang here indefinitely until killed by the environment
    pass"""
            )
        ],
        program_command="python main.py",
        test_cases=[[]]
    )

    print("Starting infinite loop test (should timeout in 30 seconds)...")
    start = asyncio.get_event_loop().time()

    response = await execute_code(request)

    end = asyncio.get_event_loop().time()
    elapsed = end - start

    result = response.results[0]

    print(f"Category: {result.category}")
    print(f"Error Message: {result.error_message}")
    print(f"Output: {result.output}")
    print(f"Execution Time: {result.execution_time:.3f}s")
    print(f"Total Elapsed Time: {elapsed:.3f}s")

    if result.category.value == "timeout":
        print("✅ Timeout correctly detected!")
        if elapsed < 35:  # Should timeout around 30 seconds
            print("✅ Timeout occurred in reasonable time!")
            return True
        else:
            print(f"⚠️ WARNING: Timeout took {elapsed:.1f}s, expected ~30s")
            return True
    else:
        print(f"❌ FAIL: Expected 'timeout', got '{result.category.value}'")
        return False


async def test_successful_execution():
    """Test that successful execution is properly classified."""
    print("\n=== Testing Successful Execution ===")

    request = DeliberateCodeExecutionRequest(
        language="python",
        submission_files=[
            SubmissionFileData(
                filename="main.py",
                content="""print("Hello, World!")
result = 5 + 3
print(f"5 + 3 = {result}")"""
            )
        ],
        program_command="python main.py",
        test_cases=[[]]
    )

    response = await execute_code(request)
    result = response.results[0]

    print(f"Category: {result.category}")
    print(f"Error Message: {result.error_message}")
    print(f"Output: {result.output}")
    print(f"Execution Time: {result.execution_time:.3f}s")

    if result.category.value == "success":
        print("✅ Successful execution correctly classified!")
    else:
        print(f"❌ FAIL: Expected 'success', got '{result.category.value}'")

    return result.category.value == "success"


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Deliberate Code Execution Service")
    print("=" * 60)

    # Initialize sandbox manager
    print("\n🔧 Initializing sandbox manager...")

    pool_configs = [
        SandboxPoolConfig(
            language=Language.PYTHON,
            pool_size=2,
            scale_limit=5,
            idle_timeout=300,
            running_timeout=120  # 2 minutes for monitoring thread cleanup
        )
    ]

    try:
        manager = initialize_sandbox_manager(pool_configs)
        print("✅ Sandbox manager initialized")
        print("⏳ Waiting for sandboxes to start...")
        await asyncio.sleep(3)  # Give containers time to start
        print("✅ Sandboxes ready\n")
    except Exception as e:
        import traceback
        print(f"❌ Failed to initialize sandbox manager: {e}")
        traceback.print_exc()
        return False

    results = []

    try:
        # Test 1: Successful execution
        try:
            results.append(("Successful Execution", await test_successful_execution()))
        except Exception as e:
            import traceback
            print(f"❌ Test failed with exception: {e}")
            traceback.print_exc()
            results.append(("Successful Execution", False))

        # Test 2: Runtime error
        try:
            results.append(("Runtime Error Classification", await test_runtime_error()))
        except Exception as e:
            import traceback
            print(f"❌ Test failed with exception: {e}")
            traceback.print_exc()
            results.append(("Runtime Error Classification", False))

        # Test 3: Timeout (this will take ~30 seconds)
        try:
            results.append(("Timeout Handling", await test_timeout()))
        except Exception as e:
            import traceback
            print(f"❌ Test failed with exception: {e}")
            traceback.print_exc()
            results.append(("Timeout Handling", False))

        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        for test_name, passed in results:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{test_name}: {status}")

        total = len(results)
        passed = sum(1 for _, p in results if p)
        print(f"\nTotal: {passed}/{total} tests passed")

        return all(p for _, p in results)

    finally:
        # Cleanup
        print("\n🧹 Cleaning up sandbox manager...")
        try:
            manager.shutdown()
            print("✅ Cleanup complete")
        except Exception as e:
            print(f"⚠️ Error during cleanup: {e}")


if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

