#!/usr/bin/env python3
"""Fix docstrings in __init__.py files to remove surrounding whitespace."""

import os
from pathlib import Path


def fix_init_file(filepath):
    """Fix docstring formatting in an __init__.py file."""
    with open(filepath, "r") as f:
        content = f.read()

    # Fix common patterns
    if content.startswith('"""  ') and '"""' in content[4:]:
        # Remove extra spaces after opening quotes
        content = content.replace('"""  ', '"""', 1)

    # Write back
    with open(filepath, "w") as f:
        f.write(content)
    print(f"Fixed: {filepath}")


def main():
    """Find and fix all __init__.py files."""
    for root, dirs, files in os.walk("."):
        # Skip venv, build, etc.
        dirs[:] = [
            d
            for d in dirs
            if d not in ["venv", ".venv", "build", "dist", "__pycache__", ".git"]
        ]

        for file in files:
            if file == "__init__.py":
                filepath = os.path.join(root, file)
                fix_init_file(filepath)


if __name__ == "__main__":
    main()
