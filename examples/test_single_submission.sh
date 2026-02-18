#!/bin/bash
# Quick cURL testing for multi-language submissions
# Usage: ./test_single_submission.sh [python|java|node|cpp|all]

API_URL="${API_URL:-http://localhost:8000}"
ASSIGNMENT_ID="${ASSIGNMENT_ID:-calc-multi-lang}"

submit_python() {
    echo "🐍 Submitting Python..."
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/submissions" \
      -H "Content-Type: application/json" \
      -d '{
        "external_assignment_id": "'$ASSIGNMENT_ID'",
        "external_user_id": "curl-test-py",
        "username": "cURL Test Python",
        "language": "python",
        "files": [
          {
            "filename": "calculator.py",
            "content": "a = int(input())\nb = int(input())\nprint(a + b)"
          }
        ]
      }')

    SUBMISSION_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    if [ -n "$SUBMISSION_ID" ]; then
        echo "✅ Python submitted - ID: $SUBMISSION_ID"
        echo "   Check: curl $API_URL/api/v1/submissions/$SUBMISSION_ID"
    else
        echo "❌ Python submission failed"
        echo "$RESPONSE"
    fi
}

submit_java() {
    echo "☕ Submitting Java..."
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/submissions" \
      -H "Content-Type: application/json" \
      -d '{
        "external_assignment_id": "'$ASSIGNMENT_ID'",
        "external_user_id": "curl-test-java",
        "username": "cURL Test Java",
        "language": "java",
        "files": [
          {
            "filename": "Calculator.java",
            "content": "import java.util.Scanner;\npublic class Calculator {\n  public static void main(String[] args) {\n    Scanner sc = new Scanner(System.in);\n    System.out.println(sc.nextInt() + sc.nextInt());\n  }\n}"
          }
        ]
      }')

    SUBMISSION_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    if [ -n "$SUBMISSION_ID" ]; then
        echo "✅ Java submitted - ID: $SUBMISSION_ID"
        echo "   Check: curl $API_URL/api/v1/submissions/$SUBMISSION_ID"
    else
        echo "❌ Java submission failed"
        echo "$RESPONSE"
    fi
}

submit_node() {
    echo "📗 Submitting Node.js..."
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/submissions" \
      -H "Content-Type: application/json" \
      -d '{
        "external_assignment_id": "'$ASSIGNMENT_ID'",
        "external_user_id": "curl-test-node",
        "username": "cURL Test Node",
        "language": "node",
        "files": [
          {
            "filename": "calculator.js",
            "content": "const readline = require(\"readline\");\nconst rl = readline.createInterface({ input: process.stdin });\nconst lines = [];\nrl.on(\"line\", l => { lines.push(l); if (lines.length === 2) { console.log(parseInt(lines[0]) + parseInt(lines[1])); rl.close(); }});"
          }
        ]
      }')

    SUBMISSION_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    if [ -n "$SUBMISSION_ID" ]; then
        echo "✅ Node.js submitted - ID: $SUBMISSION_ID"
        echo "   Check: curl $API_URL/api/v1/submissions/$SUBMISSION_ID"
    else
        echo "❌ Node.js submission failed"
        echo "$RESPONSE"
    fi
}

submit_cpp() {
    echo "⚡ Submitting C++..."
    RESPONSE=$(curl -s -X POST "$API_URL/api/v1/submissions" \
      -H "Content-Type: application/json" \
      -d '{
        "external_assignment_id": "'$ASSIGNMENT_ID'",
        "external_user_id": "curl-test-cpp",
        "username": "cURL Test C++",
        "language": "cpp",
        "files": [
          {
            "filename": "calculator.cpp",
            "content": "#include <iostream>\nint main() { int a, b; std::cin >> a >> b; std::cout << (a + b) << std::endl; return 0; }"
          }
        ]
      }')

    SUBMISSION_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
    if [ -n "$SUBMISSION_ID" ]; then
        echo "✅ C++ submitted - ID: $SUBMISSION_ID"
        echo "   Check: curl $API_URL/api/v1/submissions/$SUBMISSION_ID"
    else
        echo "❌ C++ submission failed"
        echo "$RESPONSE"
    fi
}

# Interactive menu
show_menu() {
    echo ""
    echo "======================================================================"
    echo "🧪 Multi-Language Submission Testing"
    echo "======================================================================"
    echo "API: $API_URL"
    echo "Assignment: $ASSIGNMENT_ID"
    echo "======================================================================"
    echo ""
    echo "Select a language to submit:"
    echo "  1) 🐍 Python"
    echo "  2) ☕ Java"
    echo "  3) 📗 Node.js"
    echo "  4) ⚡ C++"
    echo "  5) 🚀 All languages"
    echo "  6) ❌ Exit"
    echo ""
    echo -n "Enter choice [1-6]: "
}

# Main script
if [ $# -eq 0 ]; then
    # Interactive mode - no arguments provided
    while true; do
        show_menu
        read choice
        echo ""

        case $choice in
            1)
                submit_python
                ;;
            2)
                submit_java
                ;;
            3)
                submit_node
                ;;
            4)
                submit_cpp
                ;;
            5)
                submit_python
                echo ""
                submit_java
                echo ""
                submit_node
                echo ""
                submit_cpp
                echo ""
                echo "======================================================================"
                echo "✅ All 4 languages submitted!"
                echo "Wait ~20 seconds for grading to complete, then check results:"
                echo "  curl $API_URL/api/v1/submissions/{id}"
                echo "======================================================================"
                ;;
            6)
                echo "👋 Goodbye!"
                exit 0
                ;;
            *)
                echo "❌ Invalid choice. Please enter 1-6."
                ;;
        esac

        echo ""
        echo -n "Press Enter to continue..."
        read
    done
else
    # Command-line mode - argument provided
    echo "======================================================================"
    echo "🧪 Multi-Language Submission Testing"
    echo "======================================================================"
    echo "API: $API_URL"
    echo "Assignment: $ASSIGNMENT_ID"
    echo "======================================================================"
    echo ""

    case "${1}" in
        python|py|1)
            submit_python
            ;;
        java|2)
            submit_java
            ;;
        node|nodejs|js|3)
            submit_node
            ;;
        cpp|c++|4)
            submit_cpp
            ;;
        all|5)
            submit_python
            echo ""
            submit_java
            echo ""
            submit_node
            echo ""
            submit_cpp
            echo ""
            echo "======================================================================"
            echo "✅ All 4 languages submitted!"
            echo "Wait ~20 seconds for grading to complete, then check results:"
            echo "  curl $API_URL/api/v1/submissions/{id}"
            echo "======================================================================"
            ;;
        *)
            echo "Usage: $0 [python|java|node|cpp|all|1|2|3|4|5]"
            echo ""
            echo "Interactive mode:"
            echo "  $0           # Show interactive menu"
            echo ""
            echo "Command-line mode:"
            echo "  $0 all       # Submit all languages"
            echo "  $0 python    # Submit only Python"
            echo "  $0 java      # Submit only Java"
            echo "  $0 node      # Submit only Node.js"
            echo "  $0 cpp       # Submit only C++"
            echo "  $0 1         # Submit Python (by number)"
            echo "  $0 2         # Submit Java (by number)"
            echo "  $0 3         # Submit Node.js (by number)"
            echo "  $0 4         # Submit C++ (by number)"
            echo "  $0 5         # Submit all languages (by number)"
            echo ""
            echo "Environment variables:"
            echo "  API_URL=$API_URL"
            echo "  ASSIGNMENT_ID=$ASSIGNMENT_ID"
            exit 1
            ;;
    esac
fi

