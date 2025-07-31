#!/bin/sh
set -e
# Print a message to indicate the start of the autograding process
echo "Starting autograder..."

#Switches to autograder directory and loads environment variables from .env file
#cd /app


#export POSTGRES_USER="postgres"
#export POSTGRES_PASSWORD="postgres"
#export POSTGRES_DB="policia_db"

# --- Starting database container --- #
#DATABASE_CONTAINER_STATUS=1
#CONTAINER_NAME="pg-test-db"

#echo "Starting PostgreSQL container"
#docker compose up -d
#DATABASE_CONTAINER_STATUS=$?

#export DATABASE_CONTAINER_STATUS;

#if [ $DATABASE_CONTAINER_STATUS -ne 0 ]; then
#    echo "Database container responded with status code: $DATABASE_CONTAINER_STATUS. Database is up and recheable"
#else
#    echo "Database container responded with status code: $DATABASE_CONTAINER_STATUS. Database failed to start"
#fi

# --- Checking for database initialization --- #
#DATABASE_STATUS=1
#MAX_DB_CONNECTION_ATTEMPTS=10
#DB_SERVICE_NAME="postgres-database"
#SLEEP_INTERVAL=3

#if [ $DATABASE_CONTAINER_STATUS -eq 0 ]; then
#    echo "Checking for PostgreSQL database's connectivity..."
#    for i in $(seq 1 $MAX_DB_CONNECTION_ATTEMPTS);
#    do
#        echo "Attempt $i/$MAX_DB_CONNECTION_ATTEMPTS"
#
#        docker exec -T $DB_SERVICE_NAME pg_isready -U $POSTGRES_USER -q
#        DATABASE_STATUS=$?

#        if [ $DATABASE_STATUS -eq 0 ]; then
#            echo "PostgreSQL database is successfully accepting connections"
#            break;
#        fi
#
#        if [ $i -eq $MAX_DB_CONNECTION_ATTEMPTS ]; then
#            echo "PostgreSQL database is not accepting connections"
#        else
#            sleep $SLEEP_INTERVAL
#        fi
#    done
#fi

#export DATABASE_STATUS

# --- Install dependencies in the student's repository ---
cd "$GITHUB_WORKSPACE/submission"


if [ -f "package.json" ]; then
    echo "Downloading dependencies from student's project"
    npm ci;
else
    echo "Error: no package.json file found."
    exit 1;
fi

# --- Applies the migrations --- #
npx knex migrate:latest
MIGRATIONS_APPLICATION_STATUS=$?

export MIGRATIONS_APPLICATION_STATUS

# --- Runs seeds --- #
npx knex seed:run
SEEDS_RUN_STATUS=$?

export SEEDS_RUN_STATUS

# --- Runs server --- #

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

tree -I 'node_modules' > project_structure.txt
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

cd /app

# --- Running fatal analysis

echo "Running fatal analysis..."
python fatal_analysis.py --token $1

# --- Running tests from action repository --- #

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

python tests/result_parser.py

# --- Run the autograder ---
echo "$1"
echo "$2"
echo "$3"
echo "$4"
python autograder.py --token $1 --autograder-bot-token $2 --redis-token $3 --redis-url $4 --openai-key $5

docker compose down -v 

echo "Autograding completed successfully!"
echo "Final results generated and sent to GitHub Classroom!"
