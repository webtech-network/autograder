import json
import os
import re

# --- Configuration ---
INPUT_FILENAME = 'tests/test-results.json' 
OUTPUT_DIR = 'tests/results'
OUTPUT_FILES = {
    'base': os.path.join(OUTPUT_DIR, 'test_base_results.json'),
    'bonus': os.path.join(OUTPUT_DIR, 'test_bonus_results.json'),
    'penalty': os.path.join(OUTPUT_DIR, 'test_penalty_results.json')
}

def parse_test_results():
    """
    Reads a Jest test report, parses it, and writes the results into separate
    files for base, bonus, and penalty tests, prepending the route to base test titles.
    """
    results = {'base': [], 'bonus': [], 'penalty': []}

    try:
        # --- 1. Setup Output Directory ---
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"Output directory '{OUTPUT_DIR}' is ready.")

        # --- 2. Read and Load Input File ---
        with open(INPUT_FILENAME, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # --- 3. Process Test Suites ---
        for test_suite in data['testResults']:
            suite_name = test_suite['name']
            test_type = 'unknown'

            if 'base.test.js' in suite_name:
                test_type = 'base'
            elif 'bonus.test.js' in suite_name:
                test_type = 'bonus'
            elif 'penalty.test.js' in suite_name:
                test_type = 'penalty'
            
            if test_type == 'unknown':
                continue

            # --- 4. Process Individual Assertions ---
            for assertion in test_suite['assertionResults']:
                message = assertion['failureMessages'][0] if assertion['status'] == 'failed' and assertion['failureMessages'] else ""
                
                subject = ""
                if test_type == 'base':
                    for title in assertion['ancestorTitles']:
                        if title.startswith('Route: '):
                            match = re.search(r"Route: (.*?) -", title)
                            if match:
                                subject = match.group(1).strip()
                                break
                
                test_title = assertion['title']
                if test_type == 'base' and subject:
                    test_title = f"Route: {subject} - {test_title}"
                
                # Construct the final test result object
                parsed_result = {
                    'test': test_title,
                    'status': assertion['status'],
                    'message': message,
                    'subject': subject
                }
                
                results[test_type].append(parsed_result)

        # --- 5. Write to Output Files ---
        for test_type, output_file in OUTPUT_FILES.items():
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results[test_type], f, indent=4, ensure_ascii=False)
            print(f"Successfully saved {test_type} results to '{output_file}'")

    except FileNotFoundError:
        print(f"Error: The input file '{INPUT_FILENAME}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    parse_test_results()