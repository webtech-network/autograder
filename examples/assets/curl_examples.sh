#!/bin/bash
# Autograder Web API Test Examples using cURL
# ============================================
# This script contains cURL commands to test the Autograder Web API (RESTful)
# Note: The old multipart/form-data endpoint has been replaced with JSON API

# Set the base URL (change this to your API endpoint)
BASE_URL="http://localhost:8000/api/v1"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print headers
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Function to print warnings
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Change to the tests/assets directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# ========================================
# Test 0: Health Check
# ========================================
test_health() {
    print_header "TEST 0: Health Check"
    
    curl -X GET "$BASE_URL/health" | jq '.'
}

# ========================================
# Test 1: Create Web Development Config
# ========================================
create_webdev_config() {
    print_header "TEST 1: Create Web Development Config"
    
    curl -X POST "$BASE_URL/configs" \
      -H "Content-Type: application/json" \
      -d '{
        "external_assignment_id": "webdev_hw1",
        "template_name": "webdev",
        "language": null,
        "criteria_config": {
          "base": {
            "weight": 100,
            "subjects": {
              "HTML Structure": {
                "weight": 100,
                "tests": [
                  {
                    "file": "index.html",
                    "name": "Check Bootstrap Linked"
                  }
                ]
              }
            }
          }
        },
        "feedback_config": {
          "general": {
            "report_title": "Web Development Grading Report",
            "show_score": true
          }
        }
      }' | jq '.'
}

# ========================================
# Test 2: Submit Web Development Code
# ========================================
submit_webdev() {
    print_header "TEST 2: Submit Web Development Code"
    
    curl -X POST "$BASE_URL/submissions" \
      -H "Content-Type: application/json" \
      -d '{
        "external_assignment_id": "webdev_hw1",
        "external_user_id": "student123",
        "username": "john.doe",
        "files": [
          {
            "filename": "index.html",
            "content": "<!DOCTYPE html><html><head><title>Test</title><link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css\" rel=\"stylesheet\"></head><body><h1 class=\"display-4\">Hello World</h1></body></html>"
          }
        ]
      }' | jq '.'
}

# ========================================
# Test 3: Create I/O Config
# ========================================
create_io_config() {
    print_header "TEST 3: Create I/O Config"
    
    print_warning "This creates a configuration for a Python I/O assignment"
    
    curl -X POST "$BASE_URL/configs" \
      -H "Content-Type: application/json" \
      -d '{
        "external_assignment_id": "python_calc",
        "template_name": "IO",
        "language": "python",
        "criteria_config": {
          "base": {
            "weight": 100,
            "subjects": [
              {
                "subject_name": "Basic Tests",
                "weight": 100,
                "tests": [
                  {
                    "name": "expect_output",
                    "parameters": [
                      {"name": "inputs", "value": ["5", "3"]},
                      {"name": "expected_output", "value": "8"},
                      {"name": "program_command", "value": "python3 calc.py"}
                    ]
                  }
                ]
              }
            ]
          }
        },
        "setup_config": {
          "required_files": ["calc.py"]
        }
      }' | jq '.'
}

# ========================================
# Test 4: Submit I/O Code
# ========================================
submit_io() {
    print_header "TEST 4: Submit I/O Code"
    
    print_warning "Requires Docker and sandbox manager to be running"
    
    curl -X POST "$BASE_URL/submissions" \
      -H "Content-Type: application/json" \
      -d '{
        "external_assignment_id": "python_calc",
        "external_user_id": "student456",
        "username": "jane.smith",
        "files": [
          {
            "filename": "calc.py",
            "content": "a = int(input())\nb = int(input())\nprint(a + b)"
          }
        ]
      }' | jq '.'
}

# ========================================
# Test 5: List All Configs
# ========================================
list_configs() {
    print_header "TEST 5: List All Configs"
    
    curl -X GET "$BASE_URL/configs" | jq '.'
}

# ========================================
# Test 6: Get Specific Config
# ========================================
get_config() {
    print_header "TEST 6: Get Specific Config"
    
    if [ -z "$1" ]; then
        echo "Usage: get_config <config_id>"
        echo "Example: get_config 1"
        return
    fi
    
    curl -X GET "$BASE_URL/configs/$1" | jq '.'
}

# ========================================
# Test 7: Get Submission Results
# ========================================
get_submission() {
    print_header "TEST 7: Get Submission Results"
    
    if [ -z "$1" ]; then
        echo "Usage: get_submission <submission_id>"
        echo "Example: get_submission 1"
        return
    fi
    
    curl -X GET "$BASE_URL/submissions/$1" | jq '.'
}

# ========================================
# Test 8: List Recent Submissions
# ========================================
list_submissions() {
    print_header "TEST 8: List Recent Submissions"
    
    curl -X GET "$BASE_URL/submissions" | jq '.'
}

# ========================================
# Main Menu
# ========================================
show_menu() {
    echo -e "\n${GREEN}Autograder Web API Test Suite - cURL Edition${NC}"
    echo "========================================"
    echo "Base URL: $BASE_URL"
    echo ""
    echo "Basic Tests:"
    echo "  1. Health Check"
    echo ""
    echo "Configuration Management:"
    echo "  2. Create Web Development Config"
    echo "  3. Create I/O Config"
    echo "  4. List All Configs"
    echo "  5. Get Specific Config (requires ID)"
    echo ""
    echo "Submission Management:"
    echo "  6. Submit Web Development Code"
    echo "  7. Submit I/O Code"
    echo "  8. Get Submission Results (requires ID)"
    echo "  9. List Recent Submissions"
    echo ""
    echo "Workflow Tests:"
    echo "  10. Complete Web Dev Workflow"
    echo "  11. Complete I/O Workflow"
    echo ""
    echo "Utilities:"
    echo "  12. Change Base URL"
    echo "  0. Exit"
    echo ""
}

# Complete workflow for Web Dev
complete_webdev_workflow() {
    print_header "Complete Web Development Workflow"
    
    echo "Step 1: Creating configuration..."
    create_webdev_config
    sleep 1
    
    echo -e "\nStep 2: Submitting code..."
    submit_webdev
    sleep 1
    
    echo -e "\nStep 3: Getting results..."
    print_warning "Use 'Get Submission Results' with the submission ID from above"
}

# Complete workflow for I/O
complete_io_workflow() {
    print_header "Complete I/O Workflow"
    
    print_warning "This workflow requires Docker and sandbox manager"
    
    echo "Step 1: Creating configuration..."
    create_io_config
    sleep 1
    
    echo -e "\nStep 2: Submitting code..."
    submit_io
    sleep 1
    
    echo -e "\nStep 3: Getting results..."
    print_warning "Use 'Get Submission Results' with the submission ID from above"
}

# Main loop
if [ "$1" = "--health" ]; then
    test_health
elif [ "$1" = "--webdev" ]; then
    complete_webdev_workflow
elif [ "$1" = "--io" ]; then
    complete_io_workflow
elif [ "$1" = "--url" ] && [ -n "$2" ]; then
    BASE_URL="$2"
    echo "Base URL set to: $BASE_URL"
else
    # Interactive mode
    while true; do
        show_menu
        read -p "Select an option (0-12): " choice
        
        case $choice in
            1) test_health ;;
            2) create_webdev_config ;;
            3) create_io_config ;;
            4) list_configs ;;
            5) 
                read -p "Enter config ID: " config_id
                get_config "$config_id"
                ;;
            6) submit_webdev ;;
            7) submit_io ;;
            8) 
                read -p "Enter submission ID: " sub_id
                get_submission "$sub_id"
                ;;
            9) list_submissions ;;
            10) complete_webdev_workflow ;;
            11) complete_io_workflow ;;
            12) 
                read -p "Enter new base URL (current: $BASE_URL): " new_url
                BASE_URL="${new_url:-$BASE_URL}"
                echo -e "${GREEN}Base URL updated to: $BASE_URL${NC}"
                ;;
            0) 
                echo -e "\n${GREEN}Goodbye!${NC}\n"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option. Please select 0-12.${NC}"
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
fi

