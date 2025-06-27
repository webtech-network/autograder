#!/bin/sh

# Print a message to indicate the start of the autograding process
echo "🚀 Starting autograder..."


# --- Database Setup (start) --- #

echo "Starting PostgreSQL container..."
docker-compose -f ./docker-compose.yaml up -d db

POSTGRES_READY=0
echo "Awaiting PostgreSQL to be ready..."
for i in {1..24}; do
    if nc -z localhost 5432 > /dev/null 2>&1; then
        echo "PostgreSQL is ready!"
        POSTGRES_READY=1
        break;
    fi
    echo "PostgreSQL not ready yet, retrying... (attempt $i/24)"
    sleep 5
done

if [ $POSTGRES_READY -eq 0 ]; then
    echo "Failure: PostgreSQL did not load in time. Exiting..."
    docker compose -f ./docker-compose.yaml down
    exit 1
fi

# --- Database Setup (end) --- #

GRADING_CRITERIA="${6:-criteria.json}"

# Specify the path to the student's submission folder (we assume files are in the "submission" folder)
STUDENT_REPO_PATH="$GITHUB_WORKSPACE/submission"

# Print some of the important paths for debugging
echo "Student repository path: $STUDENT_REPO_PATH"
echo "Grading criteria: $GRADING_CRITERIA"

# --- Installing dependencies and running Knex (start) --- #

cd "$STUDENT_REPO_PATH" || exit
echo "Installing Node.js dependencies..."
npm install

echo "Running Knex migrations"
npx knex migrate:latest --knexfile knexfile.js --cwd .

echo "Running Knex seeds..."
npx knex seed:run --knexfile knexfile.js --cwd .

# --- Installing dependencies and running Knex (end) --- #

# --- Running tests and generating output file (start) --- #

echo "Running Node.js tests"
npm test > /tmp/node_test_output.txt 2>&1
NODE_TEST_EXIT_CODE=$?

# --- Running tests and generating output file (end) --- #

# Run the Python autograder script with the provided inputs
# This command will invoke autograder.py and pass the weights and grading criteria (Adjust to Node.js)
python /app/autograder.py --token $5

#Stops PostgreSQL container
echo "Stopping PostgreSQL container..."
docker compose -f /app/docker-compose.yaml down

# Check if the autograder script executed successfully
echo "✅ Autograding completed successfully!"

# Provide a message indicating completion
echo "🎉 Final results generated and sent to GitHub Classroom!"
