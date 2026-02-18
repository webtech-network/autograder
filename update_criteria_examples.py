"""Script to update all criteria examples to use multi-language command format."""

import json
import os
from pathlib import Path


def update_program_command(obj):
    """Recursively update program_command in nested structures."""
    if isinstance(obj, dict):
        if "program_command" in obj:
            cmd = obj["program_command"]
            # Only update if it's a simple string starting with python3
            if isinstance(cmd, str) and cmd.startswith("python3"):
                # Extract the filename
                parts = cmd.split()
                if len(parts) == 2:
                    filename_py = parts[1]
                    # Generate multi-language commands
                    base_name = filename_py.replace(".py", "")

                    # Handle different naming conventions
                    if base_name[0].islower():
                        # lowercase: calculator.py -> Calculator.java
                        java_class = base_name.capitalize()
                    else:
                        # Already capitalized
                        java_class = base_name

                    obj["program_command"] = {
                        "python": cmd,
                        "java": f"java {java_class}",
                        "node": f"node {base_name}.js",
                        "cpp": f"./{base_name}"
                    }
                    print(f"  Updated: {cmd} -> multi-language dict")

        # Recurse into nested dicts
        for key, value in obj.items():
            update_program_command(value)
    elif isinstance(obj, list):
        # Recurse into lists
        for item in obj:
            update_program_command(item)


def update_criteria_file(filepath):
    """Update a single criteria JSON file."""
    print(f"\nProcessing: {filepath}")

    with open(filepath, 'r') as f:
        data = json.load(f)

    update_program_command(data)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # Add trailing newline

    print(f"  Saved: {filepath}")


def main():
    """Update all criteria example files."""
    criteria_dir = Path("/home/raspiestchip/PycharmProjects/autograder/examples/assets/input_output/criteria_examples")

    print("Updating criteria example files to use multi-language command format...")

    for filepath in criteria_dir.glob("*.json"):
        update_criteria_file(filepath)

    print("\n✓ All criteria files updated successfully!")


if __name__ == "__main__":
    main()

