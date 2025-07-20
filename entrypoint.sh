#!/bin/bash
# Add non required argument validation.
python connectors/adapters/github_action_adapter/adapter_entrypoint.py \
    --github-token $1 \
    --app_token $2 \
    --test_framework $3 \
    --grading_preset $4 \
    --student-name $GITHUB_ACTOR \
    --feedback-type $5 \
    --openai_key $6 \
    --redis_url $7 \
    --redis_token $8
