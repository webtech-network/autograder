#!/bin/bash

# Performance Testing Setup Script
# Creates the test assignment needed for performance tests

set -e

echo "============================================================"
echo "Autograder Performance Test Setup"
echo "============================================================"
echo ""

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
ASSIGNMENT_ID="calc-multi-lang"

echo "API URL: $API_URL"
echo "Assignment ID: $ASSIGNMENT_ID"
echo ""

# Check if API is running
echo "Checking API availability..."
if curl -s -f "$API_URL/docs" > /dev/null; then
    echo "✓ API is running"
else
    echo "✗ API is not accessible at $API_URL"
    echo "  Please start the API first:"
    echo "  uvicorn web.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

echo ""
echo "Creating test assignment..."

# Create assignment configuration
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/configs" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "'$ASSIGNMENT_ID'",
    "template_name": "input_output",
    "languages": ["python", "java", "node", "cpp"],
    "criteria_config": {
      "test_library": "input_output",
      "base": {
        "weight": 100,
        "tests": [
          {
            "name": "expect_output",
            "parameters": [
              {"name": "inputs", "value": ["5", "3"]},
              {"name": "expected_output", "value": "8"},
              {
                "name": "program_command",
                "value": {
                  "python": "python3 calculator.py",
                  "java": "java Calculator",
                  "node": "node calculator.js",
                  "cpp": "./calculator"
                }
              }
            ]
          },
          {
            "name": "expect_output",
            "parameters": [
              {"name": "inputs", "value": ["10", "7"]},
              {"name": "expected_output", "value": "17"},
              {
                "name": "program_command",
                "value": {
                  "python": "python3 calculator.py",
                  "java": "java Calculator",
                  "node": "node calculator.js",
                  "cpp": "./calculator"
                }
              }
            ]
          }
        ]
      }
    },
    "setup_config": {
      "python": {
        "required_files": ["calculator.py"],
        "setup_commands": []
      },
      "java": {
        "required_files": ["Calculator.java"],
        "setup_commands": ["javac Calculator.java"]
      },
      "node": {
        "required_files": ["calculator.js"],
        "setup_commands": []
      },
      "cpp": {
        "required_files": ["calculator.cpp"],
        "setup_commands": ["g++ calculator.cpp -o calculator"]
      }
    }
  }')

# Extract HTTP code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Assignment created successfully"
    echo ""
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
elif [ "$HTTP_CODE" = "400" ]; then
    echo "⚠ Assignment already exists (this is OK)"
else
    echo "✗ Failed to create assignment (HTTP $HTTP_CODE)"
    echo "$BODY"
    exit 1
fi

echo ""
echo "============================================================"
echo "Setup Complete!"
echo "============================================================"
echo ""
echo "You can now run performance tests:"
echo ""
echo "  # Quick stress test"
echo "  python tests/performance/test_stress.py 20"
echo ""
echo "  # Comprehensive test"
echo "  python tests/performance/test_concurrent_submissions.py"
echo ""
echo "  # Locust load test (with UI)"
echo "  locust -f tests/performance/locustfile.py --host=$API_URL"
echo ""
echo "============================================================"

