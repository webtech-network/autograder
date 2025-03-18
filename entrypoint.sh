#!/bin/sh
set -e

# Print a message to indicate the start of the autograding process
echo "🚀 Starting autograder..."

# Ensure that the necessary environment variables are set
echo "HTML Weight: $INPUT_HTML_WEIGHT"
echo "CSS Weight: $INPUT_CSS_WEIGHT"
echo "JS Weight: $INPUT_JS_WEIGHT"

# Path to the folder where the student files are located (e.g., "submission/")
STUDENT_REPO_PATH="$GITHUB_WORKSPACE/submission"

# Run the Python autograder script with the provided inputs, including weights
python /app/autograder.py \
  --repo "$STUDENT_REPO_PATH" \
  --html-weight "$INPUT_HTML_WEIGHT" \
  --css-weight "$INPUT_CSS_WEIGHT" \
  --js-weight "$INPUT_JS_WEIGHT"

# Check if the autograder script executed successfully
echo "✅ Autograding completed successfully!"

# Ensure the final grading results are written to the appropriate output file
# Base64 encode the results.json file before sending it to GitHub Classroom
echo "result=$(jq -c . autograding_output/results.json | jq -sRr @base64)" >> "$GITHUB_OUTPUT"

# Provide a message indicating completion
echo "🎉 Final results generated and sent to GitHub Classroom!"
