#!/bin/sh

# Print a message to indicate the start of the autograding process
echo "Starting autograder..."

#set -e
cd /app

python fatal_analysis.py --token $1

# --- Install dependencies in the student's repository and run server.js ---
cd "$GITHUB_WORKSPACE/submission"


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

while [ $ATTEMPT_COUNTER -ne $CONNECTION_ATTEMPTS ]; do
    if curl -s "$SERVER_URL" > /dev/null; then
        echo "Server is up and reachable."
        break
    else
        echo "Server not reachable yet. Retrying in 2 seconds (Attempt $(($ATTEMPT_COUNTER + 1))/$CONNECTION_ATTEMPTS)..."
        sleep 2
        ATTEMPT_COUNTER=$(($ATTEMPT_COUNTER + 1))
    fi
done


if [ "$RETRY_COUNT" -eq "$MAX_RETRIES" ]; then
    echo "Error: Server failed to start or become reachable after multiple attempts."
    kill "$SERVER_PID" || true
    exit 1
fi

# --- Running tests from action repository --- #

cd /app

#if [ -f "package.json" ]; then
#    echo "Installing autograder dependencies..."
#    npm install;
#else
#    echo "Warning: package.json not found in Autograder's directory. Skipping npm install..."
#fi


#Treat errors
echo "Running tests..."
npm test -- --json --outputFile=./tests/test-results.json

echo "Parsing results..."
TEST_OUTPUT_FILE="test-results.json"

if [ ! -f "./tests/$TEST_OUTPUT_FILE" ]; then 
    echo "Error: $TEST_OUTPUT_FILE was not found after running all tests. Exiting with code 1."
    kill "$SERVER_PID"
    exit 1
fi

python tests/result-parser.py

# --- Run the autograder ---
python autograder.py  --token $1 --redis-token $2 --redis-url $3 --openai-key $4

echo "Autograding completed successfully!"
echo "Final results generated and sent to GitHub Classroom!"
