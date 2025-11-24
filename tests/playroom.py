"""
DEPRECATED: This file has been moved to tests/playroom/ directory.

The playroom functionality has been refactored into multiple template-specific
playrooms for better organization and testing coverage.

Please use one of the following:
- tests/playroom/webdev_playroom.py - Web Development template
- tests/playroom/api_playroom.py - API Testing template
- tests/playroom/essay_playroom.py - Essay Grading template
- tests/playroom/io_playroom.py - Input/Output template
- tests/playroom/run_all_playrooms.py - Run all playrooms

Usage:
    python -m tests.playroom.webdev_playroom
    python -m tests.playroom.run_all_playrooms
    python -m tests.playroom.run_all_playrooms webdev

See tests/playroom/README.md for full documentation.
"""

import sys
import os

# Add a deprecation warning
print("\n" + "!" * 70)
print("WARNING: This file is deprecated!")
print("!" * 70)
print("\nPlayrooms have been refactored into separate template-specific files.")
print("Please use the new playroom directory structure:\n")
print("  - tests/playroom/webdev_playroom.py")
print("  - tests/playroom/api_playroom.py")
print("  - tests/playroom/essay_playroom.py")
print("  - tests/playroom/io_playroom.py")
print("  - tests/playroom/run_all_playrooms.py")
print("\nFor backward compatibility, running the webdev playroom...\n")
print("!" * 70 + "\n")

# For backward compatibility, run the webdev playroom
try:
    from tests.playroom.webdev_playroom import run_webdev_playroom
    run_webdev_playroom()
except ImportError:
    print("ERROR: Could not import new playroom structure.")
    print("Please run from project root: python -m tests.playroom.webdev_playroom")
    sys.exit(1)
