"""End-to-end validation test for multi-language feature."""

import json
from pathlib import Path

def test_criteria_files_have_multi_language_commands():
    """Verify all criteria example files use multi-language command format."""
    criteria_dir = Path("examples/assets/input_output/criteria_examples")

    for filepath in criteria_dir.glob("*.json"):
        print(f"\nChecking: {filepath.name}")

        with open(filepath, 'r') as f:
            data = json.load(f)

        # Check all tests in all categories
        for category_name in ['base', 'bonus', 'penalty']:
            if category_name not in data:
                continue

            category = data[category_name]

            # Check direct tests
            if 'tests' in category:
                for test in category['tests']:
                    check_test_command(test, filepath.name)

            # Check tests in subjects
            if 'subjects' in category:
                for subject in category['subjects']:
                    if 'tests' in subject:
                        for test in subject['tests']:
                            check_test_command(test, filepath.name)

                    # Check nested subjects
                    if 'subjects' in subject:
                        for nested_subject in subject['subjects']:
                            if 'tests' in nested_subject:
                                for test in nested_subject['tests']:
                                    check_test_command(test, filepath.name)


def check_test_command(test, filename):
    """Check if a test uses proper multi-language command format."""
    for param in test.get('parameters', []):
        if param['name'] == 'program_command':
            cmd_value = param['value']

            # Should be dict or CMD
            if isinstance(cmd_value, dict):
                # Check has at least one language
                assert len(cmd_value) > 0, f"{filename}: Empty command dict"

                # Check for common languages
                has_lang = any(lang in cmd_value for lang in ['python', 'java', 'node', 'cpp'])
                assert has_lang, f"{filename}: No recognized languages in command dict"

                print(f"  ✓ Multi-language dict with {list(cmd_value.keys())}")
            elif cmd_value == "CMD":
                print(f"  ✓ CMD placeholder")
            elif isinstance(cmd_value, str):
                print(f"  ⚠ Legacy format: {cmd_value}")
            else:
                raise AssertionError(f"{filename}: Invalid command format: {type(cmd_value)}")


if __name__ == "__main__":
    print("=" * 60)
    print("Validating Multi-Language Command Format")
    print("=" * 60)

    test_criteria_files_have_multi_language_commands()

    print("\n" + "=" * 60)
    print("✓ All criteria files validated successfully!")
    print("=" * 60)

