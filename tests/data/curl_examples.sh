#!/bin/bash
# Autograder API Test Examples using cURL
# ========================================
# This script contains cURL commands to test the Autograder API

# Set the base URL (change this to your API endpoint)
BASE_URL="http://localhost:8001"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print headers
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Change to the tests/data directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# ========================================
# Test 1: Web Development Template
# ========================================
test_web_dev() {
    print_header "TEST 1: Web Development Template"
    
    curl -X POST "$BASE_URL/grade_submission/" \
      -F "submission_files=@web_dev/index.html" \
      -F "submission_files=@web_dev/style.css" \
      -F "submission_files=@web_dev/script.js" \
      -F "criteria_json=@web_dev/criteria.json" \
      -F "feedback_json=@web_dev/feedback.json" \
      -F "template_preset=web dev" \
      -F "student_name=John Doe" \
      -F "student_credentials=test-token-123" \
      -F "include_feedback=true" \
      -F "feedback_type=default" \
      | jq '.'
}

# ========================================
# Test 2: API Testing Template
# ========================================
test_api() {
    print_header "TEST 2: API Testing Template"
    
    curl -X POST "$BASE_URL/grade_submission/" \
      -F "submission_files=@api_testing/server.js" \
      -F "submission_files=@api_testing/package.json" \
      -F "criteria_json=@api_testing/criteria.json" \
      -F "feedback_json=@api_testing/feedback.json" \
      -F "setup_json=@api_testing/setup.json" \
      -F "template_preset=api" \
      -F "student_name=Jane Smith" \
      -F "student_credentials=test-token-456" \
      -F "include_feedback=true" \
      -F "feedback_type=default" \
      | jq '.'
}

# ========================================
# Test 3: Input/Output Template
# ========================================
test_io() {
    print_header "TEST 3: Input/Output Template"
    
    curl -X POST "$BASE_URL/grade_submission/" \
      -F "submission_files=@input_output/calculator.py" \
      -F "submission_files=@input_output/requirements.txt" \
      -F "criteria_json=@input_output/criteria.json" \
      -F "feedback_json=@input_output/feedback.json" \
      -F "setup_json=@input_output/setup.json" \
      -F "template_preset=io" \
      -F "student_name=Bob Johnson" \
      -F "student_credentials=test-token-789" \
      -F "include_feedback=true" \
      -F "feedback_type=default" \
      | jq '.'
}

# ========================================
# Test 4: Essay Template
# ========================================
test_essay() {
    print_header "TEST 4: Essay Template"
    
    curl -X POST "$BASE_URL/grade_submission/" \
      -F "submission_files=@essay/essay.txt" \
      -F "criteria_json=@essay/criteria.json" \
      -F "feedback_json=@essay/feedback.json" \
      -F "template_preset=essay" \
      -F "student_name=Eve Adams" \
      -F "student_credentials=test-token-202" \
      -F "include_feedback=true" \
      -F "feedback_type=default" \
      | jq '.'
}

# ========================================
# Test 5: Custom Template
# ========================================
test_custom() {
    print_header "TEST 5: Custom Template"
    
    curl -X POST "$BASE_URL/grade_submission/" \
      -F "submission_files=@custom_template/main.py" \
      -F "criteria_json=@custom_template/criteria.json" \
      -F "feedback_json=@custom_template/feedback.json" \
      -F "custom_template=@custom_template/custom_template.py" \
      -F "template_preset=custom" \
      -F "student_name=Alice Williams" \
      -F "student_credentials=test-token-101" \
      -F "include_feedback=true" \
      -F "feedback_type=default" \
      | jq '.'
}

# ========================================
# Template Info - Web Dev
# ========================================
test_template_info_web() {
    print_header "TEMPLATE INFO: Web Dev"
    
    curl -X GET "$BASE_URL/template/web_dev" | jq '.'
}

# ========================================
# Template Info - API
# ========================================
test_template_info_api() {
    print_header "TEMPLATE INFO: API"
    
    curl -X GET "$BASE_URL/template/api" | jq '.'
}

# ========================================
# Template Info - I/O
# ========================================
test_template_info_io() {
    print_header "TEMPLATE INFO: I/O"
    
    curl -X GET "$BASE_URL/template/io" | jq '.'
}

# ========================================
# Template Info - Essay
# ========================================
test_template_info_essay() {
    print_header "TEMPLATE INFO: Essay"
    
    curl -X GET "$BASE_URL/template/essay" | jq '.'
}

# ========================================
# Main Menu
# ========================================
show_menu() {
    echo -e "\n${GREEN}Autograder API Test Suite - cURL Edition${NC}"
    echo "========================================"
    echo "Base URL: $BASE_URL"
    echo ""
    echo "1. Test Web Development Template"
    echo "2. Test API Testing Template"
    echo "3. Test Input/Output Template"
    echo "4. Test Essay Template"
    echo "5. Test Custom Template"
    echo "6. Get Template Info - Web Dev"
    echo "7. Get Template Info - API"
    echo "8. Get Template Info - I/O"
    echo "9. Get Template Info - Essay"
    echo "10. Run All Tests"
    echo "11. Change Base URL"
    echo "0. Exit"
    echo ""
}

# Run all tests
run_all() {
    test_web_dev
    test_api
    test_io
    test_essay
    test_custom
    test_template_info_web
    test_template_info_api
    test_template_info_io
    test_template_info_essay
}

# Main loop
if [ "$1" = "--all" ]; then
    run_all
elif [ "$1" = "--web" ]; then
    test_web_dev
elif [ "$1" = "--api" ]; then
    test_api
elif [ "$1" = "--io" ]; then
    test_io
elif [ "$1" = "--essay" ]; then
    test_essay
elif [ "$1" = "--custom" ]; then
    test_custom
elif [ "$1" = "--url" ] && [ -n "$2" ]; then
    BASE_URL="$2"
    echo "Base URL set to: $BASE_URL"
    run_all
else
    # Interactive mode
    while true; do
        show_menu
        read -p "Select an option (0-11): " choice
        
        case $choice in
            1) test_web_dev ;;
            2) test_api ;;
            3) test_io ;;
            4) test_essay ;;
            5) test_custom ;;
            6) test_template_info_web ;;
            7) test_template_info_api ;;
            8) test_template_info_io ;;
            9) test_template_info_essay ;;
            10) run_all ;;
            11) 
                read -p "Enter new base URL: " new_url
                BASE_URL="$new_url"
                echo -e "${GREEN}Base URL updated to: $BASE_URL${NC}"
                ;;
            0) 
                echo -e "\n${GREEN}Goodbye!${NC}\n"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option. Please select 0-11.${NC}"
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
fi
