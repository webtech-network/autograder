"""
Example usage patterns for sandbox container lifecycle management.

This file demonstrates best practices for using the sandbox manager
to ensure containers are always properly cleaned up.
"""

from sandbox_manager.manager import initialize_sandbox_manager, get_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig
from sandbox_manager.models.sandbox_models import Language


# ============================================================================
# Example 1: Initialize Sandbox Manager (Application Startup)
# ============================================================================

def example_initialization():
    """
    Initialize the sandbox manager at application startup.
    This should be called once when your application starts.
    """
    # Load configuration (or define programmatically)
    pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")

    # Initialize manager
    # - Cleans up orphaned containers from previous runs
    # - Registers signal handlers for graceful shutdown
    # - Creates initial pool of containers
    manager = initialize_sandbox_manager(pool_configs)

    print("Sandbox manager initialized and ready")
    return manager


# ============================================================================
# Example 2: Using Context Manager (RECOMMENDED)
# ============================================================================

def example_context_manager_usage():
    """
    Recommended pattern: Use context manager for automatic cleanup.

    Benefits:
    - Guaranteed cleanup even if exceptions occur
    - Less code, less error-prone
    - Follows Python best practices
    """
    manager = get_sandbox_manager()

    # Pattern: with manager.acquire_sandbox(language) as sandbox:
    with manager.acquire_sandbox(Language.PYTHON) as sandbox:
        # Prepare files
        submission_files = {
            "solution.py": {"filename": "solution.py", "content": "print('Hello World')"}
        }
        sandbox.prepare_workdir(submission_files)

        # Run student code
        result = sandbox.run_command("python solution.py")

        # Check results
        if result.exit_code == 0:
            print(f"Success: {result.stdout}")
        else:
            print(f"Error: {result.stderr}")

        # Sandbox is automatically released here, even if exception occurs

    print("Sandbox released and destroyed")


# ============================================================================
# Example 3: Exception Handling with Context Manager
# ============================================================================

def example_exception_handling():
    """
    Context manager ensures cleanup even when exceptions occur.
    """
    manager = get_sandbox_manager()

    try:
        with manager.acquire_sandbox(Language.PYTHON) as sandbox:
            # This might raise an exception
            result = sandbox.run_command("python buggy_script.py")

            if result.exit_code != 0:
                raise RuntimeError(f"Script failed: {result.stderr}")

            # Process results
            return result.stdout
    except RuntimeError as e:
        print(f"Error during grading: {e}")
        # Sandbox is STILL cleaned up, even though we raised an exception
        return None


# ============================================================================
# Example 4: Manual Acquire/Release (Legacy Pattern)
# ============================================================================

def example_manual_acquire_release():
    """
    Manual pattern: Explicit acquire and release.

    Note: Only use this if you can't use context manager.
    Always use try/finally to ensure cleanup!
    """
    manager = get_sandbox_manager()

    sandbox = manager.get_sandbox(Language.PYTHON)
    try:
        # Use sandbox
        result = sandbox.run_command("python solution.py")
        print(result.stdout)
    finally:
        # CRITICAL: Always release in finally block
        manager.release_sandbox(Language.PYTHON, sandbox)


# ============================================================================
# Example 5: Grading Multiple Submissions
# ============================================================================

def example_grade_multiple_submissions():
    """
    Process multiple submissions safely.
    """
    manager = get_sandbox_manager()

    submissions = [
        {"id": 1, "code": "print('Hello')"},
        {"id": 2, "code": "print('World')"},
        {"id": 3, "code": "print('!')"},
    ]

    results = []

    for submission in submissions:
        try:
            # Each submission gets its own sandbox
            with manager.acquire_sandbox(Language.PYTHON) as sandbox:
                # Prepare code
                files = {
                    "solution.py": {
                        "filename": "solution.py",
                        "content": submission["code"]
                    }
                }
                sandbox.prepare_workdir(files)

                # Run and grade
                result = sandbox.run_command("python solution.py")
                results.append({
                    "id": submission["id"],
                    "output": result.stdout,
                    "success": result.exit_code == 0
                })
        except Exception as e:
            print(f"Error grading submission {submission['id']}: {e}")
            results.append({
                "id": submission["id"],
                "error": str(e),
                "success": False
            })
        # Sandbox automatically cleaned up after each submission

    return results


# ============================================================================
# Example 6: Running Commands with Different Languages
# ============================================================================

def example_multiple_languages():
    """
    Use different language sandboxes for different assignments.
    """
    manager = get_sandbox_manager()

    # Python submission
    print("Grading Python submission...")
    with manager.acquire_sandbox(Language.PYTHON) as sandbox:
        files = {"solution.py": {"filename": "solution.py", "content": "print(2+2)"}}
        sandbox.prepare_workdir(files)
        result = sandbox.run_command("python solution.py")
        print(f"Python result: {result.stdout}")

    # Node.js submission
    print("Grading Node.js submission...")
    with manager.acquire_sandbox(Language.NODE) as sandbox:
        files = {"solution.js": {"filename": "solution.js", "content": "console.log(2+2)"}}
        sandbox.prepare_workdir(files)
        result = sandbox.run_command("node solution.js")
        print(f"Node result: {result.stdout}")

    # C++ submission
    print("Grading C++ submission...")
    with manager.acquire_sandbox(Language.CPP) as sandbox:
        files = {
            "solution.cpp": {
                "filename": "solution.cpp",
                "content": '#include <iostream>\nint main() { std::cout << 2+2 << std::endl; }'
            }
        }
        sandbox.prepare_workdir(files)

        # Compile
        compile_result = sandbox.run_command("g++ solution.cpp -o solution")
        if compile_result.exit_code == 0:
            # Run
            run_result = sandbox.run_command("./solution")
            print(f"C++ result: {run_result.stdout}")
        else:
            print(f"Compilation failed: {compile_result.stderr}")


# ============================================================================
# Example 7: Application Shutdown (Important!)
# ============================================================================

def example_application_shutdown():
    """
    Properly shutdown the sandbox manager when application exits.

    This ensures all containers are destroyed and resources cleaned up.
    """
    manager = get_sandbox_manager()

    # Do application work...
    print("Application running...")

    # When shutting down (in FastAPI lifespan, atexit handler, etc.)
    print("Shutting down...")
    manager.shutdown()
    print("All containers destroyed")


# ============================================================================
# Example 8: FastAPI Integration
# ============================================================================

def example_fastapi_integration():
    """
    Integrate sandbox manager with FastAPI application lifecycle.
    """
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        print("Starting application...")
        pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
        manager = initialize_sandbox_manager(pool_configs)
        print("Sandbox manager ready")

        yield  # Application runs

        # Shutdown
        print("Shutting down application...")
        manager.shutdown()
        print("Sandbox manager shutdown complete")

    app = FastAPI(lifespan=lifespan)

    @app.post("/grade")
    async def grade_submission(code: str):
        manager = get_sandbox_manager()

        with manager.acquire_sandbox(Language.PYTHON) as sandbox:
            files = {"solution.py": {"filename": "solution.py", "content": code}}
            sandbox.prepare_workdir(files)
            result = sandbox.run_command("python solution.py")

            return {
                "success": result.exit_code == 0,
                "output": result.stdout,
                "error": result.stderr
            }

    return app


# ============================================================================
# Example 9: Testing and Debugging
# ============================================================================

def example_debugging():
    """
    Debugging and monitoring container lifecycle.
    """
    import docker
    from sandbox_manager.language_pool import LABEL_APP

    client = docker.from_env()

    # List all autograder sandbox containers
    containers = client.containers.list(
        all=True,
        filters={"label": f"{LABEL_APP}=autograder-sandbox"}
    )

    print(f"Found {len(containers)} sandbox containers:")
    for container in containers:
        labels = container.labels
        print(f"  - ID: {container.id[:12]}")
        print(f"    Language: {labels.get('autograder.sandbox.language')}")
        print(f"    Pool ID: {labels.get('autograder.sandbox.pool_id')}")
        print(f"    Created: {labels.get('autograder.sandbox.created_at')}")
        print(f"    Status: {container.status}")


# ============================================================================
# Example 10: Error Recovery
# ============================================================================

def example_error_recovery():
    """
    Handle errors gracefully while ensuring cleanup.
    """
    manager = get_sandbox_manager()
    max_retries = 3

    for attempt in range(max_retries):
        try:
            with manager.acquire_sandbox(Language.PYTHON) as sandbox:
                # Attempt grading
                result = sandbox.run_command("python solution.py", timeout=30)

                if result.exit_code == 0:
                    return {"success": True, "output": result.stdout}
                else:
                    raise RuntimeError(f"Execution failed: {result.stderr}")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # Final attempt failed
                return {"success": False, "error": str(e)}
            # Sandbox is still cleaned up, retry with new one


# ============================================================================
# Main Demo
# ============================================================================

def main():
    """
    Run demonstrations (for testing/learning purposes).
    """
    print("=" * 70)
    print("Sandbox Lifecycle Management Examples")
    print("=" * 70)

    # Initialize
    print("\n1. Initializing sandbox manager...")
    example_initialization()

    # Context manager usage
    print("\n2. Using context manager (recommended)...")
    example_context_manager_usage()

    # Multiple submissions
    print("\n3. Grading multiple submissions...")
    results = example_grade_multiple_submissions()
    print(f"Graded {len(results)} submissions")

    # Shutdown
    print("\n4. Shutting down...")
    example_application_shutdown()

    print("\n" + "=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()

