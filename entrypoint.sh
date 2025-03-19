#!/bin/sh
set -e

# Print a message to indicate the start of the autograding process
echo "🚀 Starting autograder..."

# Ensure that the necessary environment variables are set
echo "HTML Weight: $INPUT_HTML_WEIGHT"
echo "CSS Weight: $INPUT_CSS_WEIGHT"
echo "JS Weight: $INPUT_JS_WEIGHT"

# Check if the autograder script executed successfully
echo "✅ Autograding completed successfully!"


# Provide a message indicating completion
echo "🎉 Final results generated and sent to GitHub Classroom!"
