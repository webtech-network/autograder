#!/bin/sh
set -e
# Print a message to indicate the start of the autograding process
echo "Starting autograder..."

# --- Install dependencies in the student's repository and run server.js ---
cd "$GITHUB_WORKSPACE/submission"

sudo apt-get install tree

if [ -f "package.json" ]; then
    echo "Downloading dependencies from student's project"
    npm install;
else
    echo "Error: no package.json file found."
    exit 1;
fi

echo "Starting server.js at port 3000..."
node server.js &
SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"

#Checking if the server started:

SERVER_URL="http://localhost:3000"
CONNECTION_ATTEMPTS=10
ATTEMPT_COUNTER=0
SERVER_STATUS=1

while [ $ATTEMPT_COUNTER -ne $CONNECTION_ATTEMPTS ]; do
    if curl -s "$SERVER_URL" > /dev/null; then
        SERVER_STATUS=0
        break
    else
        echo "Server not reachable yet. Retrying in 2 seconds (Attempt $(($ATTEMPT_COUNTER + 1))/$CONNECTION_ATTEMPTS)..."
        sleep 2
        ATTEMPT_COUNTER=$(($ATTEMPT_COUNTER + 1))
    fi
done

export SERVER_STATUS

if [ $SERVER_STATUS -eq 0 ]; then 
    echo "Server healthcheck responded with status code: $SERVER_STATUS. Server is up and recheable"
else 
    echo "Server healthcheck responded with status code: $SERVER_STATUS. Server is not healthy"
fi

tree -I 'node_modules'

echo "Running fatal analysis..."
cd /app
python fatal_analysis.py --token $1

# --- Running tests from action repository --- #

cd /app

#Treat errors
echo "Running tests..."
npm test -- --json --outputFile=./tests/test-results.json || true

echo "Parsing results..."
TEST_OUTPUT_FILE="test-results.json"

if [ ! -f "./tests/$TEST_OUTPUT_FILE" ]; then 
    echo "Error: $TEST_OUTPUT_FILE was not found after running all tests. Exiting with code 1."
    kill "$SERVER_PID"
    exit 1
fi

python tests/result-parser.py

# --- Run the autograder ---
python main.py  --token $1 --redis-token $2 --redis-url $3 --openai-key $4

echo "Autograding completed successfully!"
echo "Final results generated and sent to GitHub Classroom!"
