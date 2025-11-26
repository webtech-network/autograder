#!/usr/bin/env python3
"""
Autograder API Test Suite
==========================

This script allows developers to test the Autograder API with various payloads.
It provides a menu-driven interface to select and send different test scenarios.

Usage:
    python test_api_requests.py [--url API_URL]

Requirements:
    - requests library: pip install requests
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests


class AutograderAPITester:
    """
    A comprehensive testing suite for the Autograder API.
    Provides multiple test scenarios for different template types.
    """
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip('/')
        self.test_data_dir = Path(__file__).parent / "tests" / "data"
        
    def print_header(self, text: str):
        """Print a formatted header."""
        print("\n" + "=" * 80)
        print(f"  {text}")
        print("=" * 80)
        
    def print_subheader(self, text: str):
        """Print a formatted subheader."""
        print(f"\n--- {text} ---")
        
    def load_test_files(self, test_type: str) -> Dict[str, Any]:
        """Load test files from the data directory."""
        test_dir = self.test_data_dir / test_type
        
        if not test_dir.exists():
            raise FileNotFoundError(f"Test directory not found: {test_dir}")
        
        files = {}
        for file_path in test_dir.glob("*"):
            if file_path.is_file():
                files[file_path.name] = file_path
                
        return files
    
    def read_file(self, file_path: Path, mode: str = 'rb') -> bytes:
        """Read a file and return its content."""
        with open(file_path, mode) as f:
            return f.read()
    
    def send_request(self, payload: Dict[str, Any], files: Dict[str, tuple]) -> Dict[str, Any]:
        """Send a POST request to the autograder API."""
        try:
            self.print_subheader("Sending request to API...")
            print(f"Endpoint: {self.base_url}/grade_submission/")
            print(f"Template: {payload['template_preset']}")
            print(f"Student: {payload['student_name']}")
            print(f"Files: {list(files.keys())}")
            
            response = requests.post(
                f"{self.base_url}/grade_submission/",
                data=payload,
                files=files,
                timeout=120
            )
            
            self.print_subheader("Response received")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            print(f"❌ ERROR: Could not connect to API at {self.base_url}")
            print("   Make sure the API server is running.")
            return None
        except requests.exceptions.Timeout:
            print("❌ ERROR: Request timed out")
            return None
        except Exception as e:
            print(f"❌ ERROR: {e}")
            return None
    
    def print_results(self, results: Dict[str, Any]):
        """Pretty print the autograder results."""
        if not results:
            return
            
        self.print_header("AUTOGRADING RESULTS")
        
        print(f"\n📊 Server Status: {results.get('server_status', 'N/A')}")
        print(f"📊 Autograding Status: {results.get('autograding_status', 'N/A')}")
        print(f"🎯 Final Score: {results.get('final_score', 'N/A')}")
        
        if results.get('feedback'):
            self.print_subheader("Feedback")
            feedback = results['feedback']
            if isinstance(feedback, str):
                print(feedback)
            else:
                print(json.dumps(feedback, indent=2))
        
        if results.get('test_report'):
            self.print_subheader("Test Report")
            for i, test in enumerate(results['test_report'], 1):
                test_name = test.get('name', 'Unknown Test')
                score = test.get('score', 0)
                report = test.get('report', '')
                
                status = "✅" if score == 100 else "❌" if score == 0 else "⚠️"
                print(f"\n  {status} Test {i}: {test_name}")
                print(f"     Score: {score}/100")
                if report:
                    print(f"     Report: {report}")
    
    # ========================================================================
    # Test Scenarios
    # ========================================================================
    
    def test_web_dev_preset(self):
        """Test Web Development preset with HTML/CSS/JS files."""
        self.print_header("TEST CASE 1: Web Development Preset")
        
        try:
            files_dict = self.load_test_files("web_dev")
            
            # Prepare submission files
            submission_files = []
            for filename in ['index.html', 'style.css', 'script.js']:
                if filename in files_dict:
                    submission_files.append(
                        ('submission_files', (filename, self.read_file(files_dict[filename]), 'text/plain'))
                    )
            
            # Prepare configuration files
            files = submission_files + [
                ('criteria_json', ('criteria.json', self.read_file(files_dict['criteria.json']), 'application/json')),
                ('feedback_json', ('feedback.json', self.read_file(files_dict['feedback.json']), 'application/json')),
            ]
            
            payload = {
                'template_preset': 'web dev',
                'student_name': 'John Doe',
                'student_credentials': 'test-token-123',
                'include_feedback': 'true',
                'feedback_type': 'default'
            }
            
            results = self.send_request(payload, files)
            self.print_results(results)
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    def test_api_preset(self):
        """Test API Testing preset with Node.js API."""
        self.print_header("TEST CASE 2: API Testing Preset")
        
        try:
            files_dict = self.load_test_files("api_testing")
            
            # Prepare submission files
            submission_files = []
            for filename in ['server.js', 'package.json']:
                if filename in files_dict:
                    submission_files.append(
                        ('submission_files', (filename, self.read_file(files_dict[filename]), 'text/plain'))
                    )
            
            # Prepare configuration files
            files = submission_files + [
                ('criteria_json', ('criteria.json', self.read_file(files_dict['criteria.json']), 'application/json')),
                ('feedback_json', ('feedback.json', self.read_file(files_dict['feedback.json']), 'application/json')),
                ('setup_json', ('setup.json', self.read_file(files_dict['setup.json']), 'application/json')),
            ]
            
            payload = {
                'template_preset': 'api',
                'student_name': 'Jane Smith',
                'student_credentials': 'test-token-456',
                'include_feedback': 'true',
                'feedback_type': 'default'
            }
            
            results = self.send_request(payload, files)
            self.print_results(results)
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    def test_io_preset(self):
        """Test Input/Output preset with Python calculator."""
        self.print_header("TEST CASE 3: Input/Output Preset")
        
        try:
            files_dict = self.load_test_files("input_output")
            
            # Prepare submission files
            submission_files = []
            for filename in ['calculator.py', 'requirements.txt']:
                if filename in files_dict:
                    submission_files.append(
                        ('submission_files', (filename, self.read_file(files_dict[filename]), 'text/plain'))
                    )
            
            # Prepare configuration files
            files = submission_files + [
                ('criteria_json', ('criteria.json', self.read_file(files_dict['criteria.json']), 'application/json')),
                ('feedback_json', ('feedback.json', self.read_file(files_dict['feedback.json']), 'application/json')),
                ('setup_json', ('setup.json', self.read_file(files_dict['setup.json']), 'application/json')),
            ]
            
            payload = {
                'template_preset': 'io',
                'student_name': 'Bob Johnson',
                'student_credentials': 'test-token-789',
                'include_feedback': 'true',
                'feedback_type': 'default'
            }
            
            results = self.send_request(payload, files)
            self.print_results(results)
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    def test_essay_preset(self):
        """Test Essay preset with a text file and AI-assisted checks."""
        self.print_header("TEST CASE 4: Essay Preset")

        try:
            files_dict = self.load_test_files("essay")

            # Prepare submission files
            submission_files = []
            for filename in ['essay.txt']:
                if filename in files_dict:
                    submission_files.append(
                        ('submission_files', (filename, self.read_file(files_dict[filename]), 'text/plain'))
                    )

            # Prepare configuration files
            files = submission_files + [
                ('criteria_json', ('criteria.json', self.read_file(files_dict['criteria.json']), 'application/json')),
                ('feedback_json', ('feedback.json', self.read_file(files_dict['feedback.json']), 'application/json')),
            ]

            payload = {
                'template_preset': 'essay',
                'student_name': 'Eve Adams',
                'student_credentials': 'test-token-202',
                'include_feedback': 'true',
                'feedback_type': 'default'
            }

            results = self.send_request(payload, files)
            self.print_results(results)

        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    def test_custom_template(self):
        """Test Custom Template with custom Python template."""
        self.print_header("TEST CASE 5: Custom Template")
        
        try:
            files_dict = self.load_test_files("custom_template")
            
            # Prepare submission files
            submission_files = []
            for filename in ['main.py']:
                if filename in files_dict:
                    submission_files.append(
                        ('submission_files', (filename, self.read_file(files_dict[filename]), 'text/plain'))
                    )
            
            # Prepare configuration files including custom template
            files = submission_files + [
                ('criteria_json', ('criteria.json', self.read_file(files_dict['criteria.json']), 'application/json')),
                ('feedback_json', ('feedback.json', self.read_file(files_dict['feedback.json']), 'application/json')),
                ('custom_template', ('custom_template.py', self.read_file(files_dict['custom_template.py']), 'text/plain')),
            ]
            
            payload = {
                'template_preset': 'custom',
                'student_name': 'Alice Williams',
                'student_credentials': 'test-token-101',
                'include_feedback': 'true',
                'feedback_type': 'default'
            }
            
            results = self.send_request(payload, files)
            self.print_results(results)
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    def test_get_template_info(self, template_name: str):
        """Test GET endpoint for template information."""
        self.print_header(f"GET TEMPLATE INFO: {template_name}")
        
        try:
            url = f"{self.base_url}/templates/{template_name.replace(' ', '_')}"
            print(f"GET {url}")
            
            response = requests.get(url, timeout=10)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("\n✅ Template Information:")
                print(json.dumps(data, indent=2))
            else:
                print(f"❌ Error: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
    
    def run_all_tests(self):
        """Run all test scenarios."""
        self.print_header("RUNNING ALL TEST SCENARIOS")
        
        self.test_web_dev_preset()
        print("\n" + "─" * 80)
        
        self.test_api_preset()
        print("\n" + "─" * 80)
        
        self.test_io_preset()
        print("\n" + "─" * 80)

        self.test_essay_preset()
        print("\n" + "─" * 80)
        
        self.test_custom_template()
        print("\n" + "─" * 80)
        
        # Test GET endpoints
        for template in ["web_dev", "api", "io", "essay"]:
            self.test_get_template_info(template)
            print("\n" + "─" * 80)
        
        self.print_header("ALL TESTS COMPLETED")


def main():
    """Main function with interactive menu."""
    parser = argparse.ArgumentParser(
        description="Test the Autograder API with various payloads"
    )
    parser.add_argument(
        '--url',
        default='http://localhost:8001',
        help='Base URL of the Autograder API (default: http://localhost:8001)'
    )
    parser.add_argument(
        '--test',
        choices=['web', 'api', 'io', 'essay', 'custom', 'all'],
        help='Run a specific test directly without menu'
    )
    
    args = parser.parse_args()
    
    tester = AutograderAPITester(args.url)
    
    # Check if direct test was specified
    if args.test:
        if args.test == 'web':
            tester.test_web_dev_preset()
        elif args.test == 'api':
            tester.test_api_preset()
        elif args.test == 'io':
            tester.test_io_preset()
        elif args.test == 'essay':
            tester.test_essay_preset()
        elif args.test == 'custom':
            tester.test_custom_template()
        elif args.test == 'all':
            tester.run_all_tests()
        return
    
    # Interactive menu
    while True:
        print("\n" + "=" * 80)
        print("  AUTOGRADER API TEST SUITE")
        print("=" * 80)
        print(f"\nAPI URL: {tester.base_url}")
        print("\nAvailable Test Scenarios:")
        print("  1. Web Development Preset (HTML/CSS/JS)")
        print("  2. API Testing Preset (Node.js Express API)")
        print("  3. Input/Output Preset (Python Calculator)")
        print("  4. Essay Preset (AI-assisted essay grading)")
        print("  5. Custom Template (Custom Python Template)")
        print("  6. Get Template Info (web dev)")
        print("  7. Get Template Info (api)")
        print("  8. Get Template Info (io)")
        print("  9. Get Template Info (essay)")
        print("  10. Run All Tests")
        print("  11. Change API URL")
        print("  0. Exit")
        
        choice = input("\nSelect a test scenario (0-11): ").strip()
        
        if choice == '1':
            tester.test_web_dev_preset()
        elif choice == '2':
            tester.test_api_preset()
        elif choice == '3':
            tester.test_io_preset()
        elif choice == '4':
            tester.test_essay_preset()
        elif choice == '5':
            tester.test_custom_template()
        elif choice == '6':
            tester.test_get_template_info("web dev")
        elif choice == '7':
            tester.test_get_template_info("api")
        elif choice == '8':
            tester.test_get_template_info("io")
        elif choice == '9':
            tester.test_get_template_info("essay")
        elif choice == '10':
            tester.run_all_tests()
        elif choice == '11':
            new_url = input("Enter new API URL: ").strip()
            tester.base_url = new_url.rstrip('/')
            print(f"✅ API URL updated to: {tester.base_url}")
        elif choice == '0':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please select 0-11.")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
