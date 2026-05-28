#!/bin/bash
set -e

# Change to autograder directory
cd "$(dirname "$0")/.."

echo "🚀 Building and starting Docker environment for E2E tests..."
docker compose down -v
docker compose up --build -d

# Function to check if API is healthy
check_health() {
    curl -s http://localhost:8000/api/v1/health | grep -q "healthy"
}

echo "⏳ Waiting for API to be healthy..."
max_retries=60
count=0
until check_health || [ $count -eq $max_retries ]; do
    sleep 2
    count=$((count + 1))
    echo -n "."
done

if [ $count -eq $max_retries ]; then
    echo -e "\n❌ API failed to become healthy. Logs:"
    docker compose logs
    docker compose down -v
    exit 1
fi

echo -e "\n✅ API is healthy. Running tests..."

# Run pytest
export PYTHONPATH=$PYTHONPATH:.
if ! pytest tests/e2e/ -v; then
    echo "❌ Tests failed. Keeping environment up for inspection."
    exit 1
fi

echo "🧹 Cleaning up..."
docker compose down -v

echo "🎉 E2E tests completed!"
