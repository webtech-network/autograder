#!/usr/bin/env python3
"""
Validation script for I/O template criteria examples.

This script validates all criteria JSON files in the criteria_examples directory
against the Pydantic models used by the autograder.

Usage:
    python validate_criteria.py
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from autograder.models.config.criteria import CriteriaConfig


def validate_criteria_file(filepath: Path) -> tuple[bool, str]:
    """Validate a single criteria JSON file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Validate using Pydantic model
        config = CriteriaConfig.from_dict(data)

        # Count tests
        def count_tests(obj):
            count = 0
            if hasattr(obj, 'tests') and obj.tests:
                count += len(obj.tests)
            if hasattr(obj, 'subjects') and obj.subjects:
                for s in obj.subjects:
                    count += count_tests(s)
            return count

        base_tests = count_tests(config.base)
        bonus_tests = count_tests(config.bonus) if config.bonus else 0
        penalty_tests = count_tests(config.penalty) if config.penalty else 0

        return True, f"✓ Valid ({base_tests} base, {bonus_tests} bonus, {penalty_tests} penalty tests)"

    except json.JSONDecodeError as e:
        return False, f"✗ JSON Error: {e}"
    except Exception as e:
        return False, f"✗ Validation Error: {e}"


def main():
    examples_dir = Path(__file__).parent / "criteria_examples"

    if not examples_dir.exists():
        print("Error: criteria_examples directory not found")
        sys.exit(1)

    print("=" * 60)
    print("Validating I/O Template Criteria Examples")
    print("=" * 60)
    print()

    all_valid = True

    for filepath in sorted(examples_dir.glob("*.json")):
        valid, message = validate_criteria_file(filepath)
        status = "PASS" if valid else "FAIL"
        print(f"[{status}] {filepath.name}")
        print(f"       {message}")
        print()

        if not valid:
            all_valid = False

    print("=" * 60)
    if all_valid:
        print("All criteria examples are valid!")
        sys.exit(0)
    else:
        print("Some criteria examples failed validation!")
        sys.exit(1)


if __name__ == "__main__":
    main()

