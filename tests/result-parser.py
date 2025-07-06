import json
import pandas as pd

filename = 'test-results.json' 

parsed_tests = []

try:
    with open(filename, 'r') as file:
        data = json.load(file)

    for test_suite in data['testResults']:
        suite_name = test_suite['name']
        test_type = 'unknown'
        if 'bonus.test.js' in suite_name:
            test_type = 'bonus'
        elif 'penalty.test.js' in suite_name:
            test_type = 'penalty'
        elif 'base.test.js' in suite_name:
            test_type = 'base'

        for assertion in test_suite['assertionResults']:
            parsed_tests.append({
                'title': assertion['title'],
                'type': test_type,
                'status': assertion['status']
            })

    df = pd.DataFrame(parsed_tests)
    print(df)

except FileNotFoundError:
    print(f"Error: The file '{filename}' was not found.")
except json.JSONDecodeError:
    print(f"Error: The file '{filename}' is not a valid JSON file.")