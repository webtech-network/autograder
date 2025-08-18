#!/bin/bash
# Add non required argument validation.

cd /app

tree -a -I "node_modules|.git|.github|.vscode|.idea|.pytest_cache|__pycache__|.DS_Store" .

python -m connectors.adapters.github_action_adapter.github_entrypoint \
    --github-token $GITHUB_TOKEN \
    --app-token $APP_TOKEN \
    --test-framework $TEST_FRAMEWORK \
    --grading-preset $GRADING_PRESET \
    --student-name $GITHUB_ACTOR \
    --feedback-type $FEEDBACK_TYPE \
    --openai-key $OPENAI_KEY \
    --redis-url $REDIS_URL \
    --redis-token $REDIS_TOKEN
