#!/usr/bin/env bash
# Run against a local API. One canonical definition is shared with Python/Actions.
set -euo pipefail
base_url="${AUTOGRADER_API_URL:-http://localhost:8000}/api/v1"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-health}" in
  health) curl --fail-with-body "$base_url/health" ;;
  create-web)
    jq -n --slurpfile definition "$script_dir/web_dev/definition.json" \
      --arg assignment "${2:-web-example}" '{external_assignment_id:$assignment,definition:$definition[0]}' |
      curl --fail-with-body -X POST "$base_url/configs" -H 'Content-Type: application/json' --data-binary @-
    ;;
  create-io)
    jq -n --slurpfile definition "$script_dir/input_output/criteria_examples/1_base_only_simple.json" \
      --arg assignment "${2:-io-example}" '{external_assignment_id:$assignment,definition:$definition[0]}' |
      curl --fail-with-body -X POST "$base_url/configs" -H 'Content-Type: application/json' --data-binary @-
    ;;
  validate-io)
    curl --fail-with-body -X POST "$base_url/configs/validate" -H 'Content-Type: application/json' \
      --data-binary "@$script_dir/input_output/criteria_examples/1_base_only_simple.json"
    ;;
  *) echo 'Usage: curl_examples.sh health|create-web|create-io|validate-io [assignment-alias]' >&2; exit 2 ;;
esac
