#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
args=(python -m github_action.main)
for mapping in \
  'EXECUTION_MODE:execution-mode' 'DEFINITION_PATH:definition-path' \
  'SUBMISSION_ROOT:submission-root' 'SUBMITTER_ID:submitter-id' 'SUBMITTER_NAME:submitter-name' \
  'SUBMISSION_LANGUAGE:submission-language' 'LOCALE:locale' \
  'GRADING_CONFIG_ID:grading-config-id' 'GRADING_CONFIG_REVISION:grading-config-revision' \
  'TRUSTED_SELF_HOSTED_RUNNER:trusted-self-hosted-runner' 'AUTOGRADER_CLOUD_URL:autograder-cloud-url' \
  'AUTOGRADER_CLOUD_TOKEN:autograder-cloud-token' 'UPLOAD_TO_CLOUD:upload-to-cloud' \
  'RETRY_DELIVERY_PATH:retry-delivery-path'; do
  variable="${mapping%%:*}"
  argument="${mapping#*:}"
  if [[ -n "${!variable:-}" ]]; then
    args+=("--$argument" "${!variable}")
  fi
done
exec "${args[@]}"
