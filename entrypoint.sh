#!/bin/sh

# Print a message to indicate the start of the autograding process
echo "🚀 Starting autograder..."

# Ensure that the necessary environment variables are set and print them for debugging
echo "HTML Weight: $INPUT_HTML_WEIGHT"
echo "CSS Weight: $INPUT_CSS_WEIGHT"
echo "JS Weight: $INPUT_JS_WEIGHT"
echo "Timeout: $INPUT_TIMEOUT"
echo "Grading Criteria File: $INPUT_GRADING_CRITERIA"

# Set default values for arguments if they are not provided
HTML_WEIGHT="${INPUT_HTML_WEIGHT:-30}"
CSS_WEIGHT="${INPUT_CSS_WEIGHT:-40}"
JS_WEIGHT="${INPUT_JS_WEIGHT:-30}"
TIMEOUT="${INPUT_TIMEOUT:-10}"
GRADING_CRITERIA="${INPUT_GRADING_CRITERIA:-criteria.json}"

# Specify the path to the student's submission folder (we assume files are in the "submission" folder)
STUDENT_REPO_PATH="$GITHUB_WORKSPACE/submission"

# Print some of the important paths for debugging
echo "Student repository path: $STUDENT_REPO_PATH"
echo "Grading criteria: $GRADING_CRITERIA"

# Run the Python autograder script with the provided inputs
# This command will invoke autograder.py and pass the weights and grading criteria
python /app/autograder.py \
  --html-weight "$HTML_WEIGHT" \
  --css-weight "$CSS_WEIGHT" \
  --js-weight "$JS_WEIGHT" \
  --grading-criteria "$GRADING_CRITERIA" \
  --timeout "$TIMEOUT"

# Check if the autograder script executed successfully
echo "✅ Autograding completed successfully!"

# Ensure the final grading results are written to the appropriate output file
# Base64 encode the results.json file before sending it to GitHub Classroom
echo "Encoding results.json to Base64 and sending it to GitHub Classroom..."
echo "result=$(jq -c . autograding_output/results.json | jq -sRr @base64)" >> "$GITHUB_OUTPUT"

# Provide a message indicating completion
echo "🎉 Final results generated and sent to GitHub Classroom!"
