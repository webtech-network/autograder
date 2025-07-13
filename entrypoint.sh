#!/bin/sh
set -e
# Print a message to indicate the start of the autograding process
echo "Starting autograder..."

# --- Install dependencies in the student's repository and run server.js ---

echo "Running fatal analysis..."
cd /app
python fatal_analysis.py --token $1

# --- Running tests from action repository --- #

cd /app

#Treat errors
echo "Running tests..."
# Add your test command here

echo "Parsing results..."
TEST_OUTPUT_FILE="test-results.json"

if [ ! -f "./tests/$TEST_OUTPUT_FILE" ]; then
    echo "Error: $TEST_OUTPUT_FILE was not found after running all tests. Exiting with code 1."
    kill "$SERVER_PID"
    exit 1
fi

python tests/result-parser.py
# Parses the test results into the autograder result format.
# --- Run the autograder ---
python autograder.py  --token $1 --redis-token $2 --redis-url $3 --openai-key $4

echo "Autograding completed successfully!"
echo "Final results generated and sent to GitHub Classroom!"