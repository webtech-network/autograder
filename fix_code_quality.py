#!/usr/bin/env python3
"""Script to automatically fix common code quality issues."""

import os
import re
from pathlib import Path


def add_module_docstring(file_path):
    """Add module docstring if missing."""
    with open(file_path, "r") as f:
        content = f.read()

    # Check if file starts with docstring or shebang
    if (
        content.startswith('"""')
        or content.startswith("'''")
        or content.startswith("#!")
    ):
        return False

    # Get module name from file path
    module_name = Path(file_path).stem.replace("_", " ").title()

    # Add module docstring
    docstring = f'"""{module_name} module."""\n\n'

    with open(file_path, "w") as f:
        f.write(docstring + content)

    return True


def fix_f_string_placeholders(file_path):
    """Fix f-strings without placeholders."""
    with open(file_path, "r") as f:
        content = f.read()

    original = content

    # Find f-strings without placeholders
    # Pattern: "..." or '...' without { }
    pattern = r'f(["\'])([^"\'{]*?)\1'

    def replace_func(match):
        quote = match.group(1)
        string_content = match.group(2)
        # Check if it has braces
        if "{" not in string_content:
            # Remove the f prefix
            return f"{quote}{string_content}{quote}"
        return match.group(0)

    content = re.sub(pattern, replace_func, content)

    if content != original:
        with open(file_path, "w") as f:
            f.write(content)
        return True
    return False


def remove_unused_imports(file_path):
    """Comment out obviously unused imports marked by flake8."""
    # This is a simple version - in production use autoflake
    pass


def main():
    """Main function."""
    python_files = []

    # Find all Python files
    for root, dirs, files in os.walk("."):
        # Skip common directories
        dirs[:] = [
            d
            for d in dirs
            if d
            not in {".git", "__pycache__", "venv", ".venv", "build", "dist", ".eggs"}
        ]

        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    # Fix each file
    for file_path in python_files:
        try:
            modified = False
            if add_module_docstring(file_path):
                print(f"Added docstring to {file_path}")
                modified = True

            if fix_f_string_placeholders(file_path):
                print(f"Fixed f-strings in {file_path}")
                modified = True

        except Exception as e:
            print(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    main()
