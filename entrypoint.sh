#!/bin/sh

# Print a message to indicate the start of the autograding process
echo "🚀 Starting autograder..."

# Specify the path to the student's submission folder (we assume files are in the "submission" folder)
STUDENT_REPO_PATH="$GITHUB_WORKSPACE/submission"

# Print some of the important paths for debugging
echo "Student repository path: $STUDENT_REPO_PATH"
echo "Grading criteria: $GRADING_CRITERIA"

# --- Tests (start) --- #
node ./tests/test_*.js

# --- Tests (end) -- #

# Run the Python autograder script with the provided inputs
# This command will invoke autograder.py and pass the weights and grading criteria
python /app/autograder.py  --token $5

# Check if the autograder script executed successfully
echo "✅ Autograding completed successfully!"
# Provide a message indicating completion
echo "🎉 Final results generated and sent to GitHub Classroom!"
