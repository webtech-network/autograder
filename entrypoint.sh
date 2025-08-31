#!/bin/bash
# This script validates required environment variables and dynamically builds
# the command to run the python entrypoint, only passing arguments that are set.

# Exit immediately if a command exits with a non-zero status for robustness.
set -e

# --- 1. Validate Required Environment Variables ---
# These variables correspond to arguments marked as `required=True` in the Python script.
# The script will exit with an error if any of them are missing.
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "Error: Environment variable GITHUB_TOKEN is not set." >&2
  exit 1
fi

if [[ -z "$TEMPLATE_PRESET" ]]; then
  echo "Error: Environment variable TEMPLATE_PRESET is not set." >&2
  exit 1
fi

if [[ -z "$GITHUB_ACTOR" ]]; then
  echo "Error: Environment variable GITHUB_ACTOR is not set." >&2
  exit 1
fi

cd /app

# --- 2. Dynamically Build Command Arguments ---
# Initialize a bash array with the base command and the required arguments.
args=(
    "python"
    "-m"
    "connectors.adapters.github_action_adapter.github_entrypoint"
    "--github-token" "$GITHUB_TOKEN"
    "--template-preset" "$TEMPLATE_PRESET"
    "--student-name" "$GITHUB_ACTOR"
)

# Conditionally add optional arguments to the array ONLY if they are set.
# The '-n' flag checks if the variable's string length is non-zero.
# Note: The argument flags (e.g., --app_token) match the ones in your Python script.
if [[ -n "$APP_TOKEN" ]]; then
    args+=("--app-token" "$APP_TOKEN")
fi

if [[ -n "$FEEDBACK_TYPE" ]]; then
    args+=("--feedback-type" "$FEEDBACK_TYPE")
fi

if [[ -n "$OPENAI_KEY" ]]; then
    args+=("--openai-key" "$OPENAI_KEY")
fi

if [[ -n "$REDIS_URL" ]]; then
    args+=("--redis-url" "$REDIS_URL")
fi

if [[ -n "$REDIS_TOKEN" ]]; then
    args+=("--redis-token" "$REDIS_TOKEN")
fi


# --- 3. Execute the Python Script ---
echo "Executing python entrypoint with configured arguments..."

# The "${args[@]}" syntax expands the array into separate, properly quoted arguments.
# This is the safest way to run commands with dynamic arguments that might contain spaces.
"${args[@]}"
