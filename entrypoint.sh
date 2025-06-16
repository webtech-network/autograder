#!/bin/sh

# Print a message to indicate the start of the autograding process
echo "🚀 Starting autograder..."

echo "Starting PostgreSQL container..."
docker-compose -f /app/docker-copose.yaml up -d db

echo "Awaiting PostgreSQL to be ready..."
/usr/bin/python -c
'
import sys
import os
import subprocess
import time

for _ in range(30): # Wait up to 150 seconds (30 * 5s)
    try:
        subprocess.run(["nc", "-z", "localhost", "5432"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("PostgreSQL is ready!")
        break
    except subprocess.CalledProcessError:
        print("PostgreSQL not ready yet, retrying...")
        time.sleep(5)
else:
    print("PostgreSQL did not become ready in time. Exiting.")
    sys.exit(1) 
'

# Ensure that the necessary environment variables are set and print them for debugging
echo "HTML Weight: $1"
echo "CSS Weight: $2"
echo "JS Weight: $3"
echo "Timeout: $4"
echo "token: $5"

# Set default values for arguments if they are not provided
HTML_WEIGHT="${1:-30}"
CSS_WEIGHT="${2:-40}"
JS_WEIGHT="${3:-30}"
TIMEOUT="${4:-10}"
GRADING_CRITERIA="${6:-criteria.json}"

# Specify the path to the student's submission folder (we assume files are in the "submission" folder)
STUDENT_REPO_PATH="$GITHUB_WORKSPACE/submission"

# Print some of the important paths for debugging
echo "Student repository path: $STUDENT_REPO_PATH"
echo "Grading criteria: $GRADING_CRITERIA"

#Installing Node.js dependencies and running Knex
cd "$STUDENT_REPO_PATH" || exit
echo "Installing Node.js dependencies..."
npm install

echo "Running Knex migrations"
npx knex migrate:latest --knexfile knexfile.js --cwd .

echo "Running Knex seeds..."
npx knex seed:run --knexfile knexfile.js --cwd .

#Running tests (Adjust according to the library)
echo "Running Node.js tests"
npm test > /tmp/node_test_output.txt 2>&1
NODE_TEST_EXIT_CODE=$?

# Run the Python autograder script with the provided inputs
# This command will invoke autograder.py and pass the weights and grading criteria
python /app/autograder.py --html-weight $HTML_WEIGHT --css-weight $CSS_WEIGHT --js-weight $JS_WEIGHT --grading-criteria $GRADING_CRITERIA --timeout $TIMEOUT --token $5

#Stops PostgreSQL container
echo "Stopping PostgreSQL container..."
docker compose -f /app/docker-compose.yaml down

# Check if the autograder script executed successfully
echo "✅ Autograding completed successfully!"
# Provide a message indicating completion
echo "🎉 Final results generated and sent to GitHub Classroom!"
