import subprocess
import time
import os
import pytest
import requests

@pytest.fixture(scope="session", autouse=True)
def docker_environment():
    """Start the docker environment for E2E tests if not already running."""
    api_url = "http://localhost:8000/api/v1/health"
    
    # Check if already healthy
    try:
        response = requests.get(api_url, timeout=2)
        if response.status_code == 200:
            print("\nAPI is already healthy, skipping Docker startup.")
            yield
            return
    except requests.exceptions.RequestException:
        pass

    print("\nStarting Docker environment...")
    
    # We'll use the docker-compose.yml in the autograder directory
    autograder_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    
    # First, ensure it's down
    subprocess.run(["docker", "compose", "down", "-v"], cwd=autograder_dir, capture_output=True, check=False)
    
    # Build and up
    with subprocess.Popen(
        ["docker", "compose", "up", "--build", "-d"],
        cwd=autograder_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    ) as process:
        _, stderr = process.communicate()
        
        if process.returncode != 0:
            pytest.fail(f"Failed to start docker environment: {stderr.decode()}")

    # Wait for API to be healthy
    max_retries = 30
    retry_interval = 2
    
    healthy = False
    for i in range(max_retries):
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                healthy = True
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(retry_interval)
        print(f"Waiting for API to be healthy... ({i+1}/{max_retries})")

    if not healthy:
        # Get logs before failing
        result = subprocess.run(
            ["docker", "compose", "logs"], 
            cwd=autograder_dir, 
            capture_output=True, 
            check=False
        )
        logs = result.stdout.decode()
        print(logs)
        pytest.fail("API failed to become healthy within timeout")

    yield

    print("\nKeeping Docker environment up for inspection (manual cleanup required: docker compose down -v)")

@pytest.fixture
def api_base_url():
    """Return the base URL for the API."""
    return "http://localhost:8000/api/v1"

@pytest.fixture
def auth_headers():
    """Return the authorization headers for the API."""
    return {"Authorization": "Bearer e2e-test-token"}
