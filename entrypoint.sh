#!/bin/bash
# Add non required argument validation.

python connectors/adapters/github_action_adapter/adapter_entrypoint.py \
    --github-token $GITHUB_TOKEN \
    --app_token $APP_TOKEN \
    --test_framework $TEST_FRAMEWORK \
    --grading_preset $GRADING_PRESET \
    --student-name $GITHUB_ACTOR \
    --feedback-type $FEEDBACK_TYPE \
    --openai_key $OPENAI_KEY \
    --redis_url $REDIS_URL \
    --redis_token $REDIS_TOKEN
