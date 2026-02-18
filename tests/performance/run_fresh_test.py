#!/usr/bin/env python3
"""
Run a fresh stress test with correct filenames and compare with old results.
"""

import asyncio
import sys
from pathlib import Path

print("="*70)
print("🧪 FRESH STRESS TEST - Testing Fixed Filenames")
print("="*70)
print()
print("This will create NEW submissions with correct filenames:")
print("  ✅ calculator.py")
print("  ✅ Calculator.java")
print("  ✅ calculator.js")
print("  ✅ calculator.cpp")
print()
print("Old submissions (with wrong filenames) will remain in the database")
print("but you'll be able to compare them with the new ones.")
print()
print("="*70)
print()

# Get number of submissions
if len(sys.argv) > 1:
    num_subs = int(sys.argv[1])
else:
    num_subs = 10

print(f"📊 Running test with {num_subs} submissions...")
print()

# Import and run the stress test
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.performance.test_stress import stress_test

# Run it
result = asyncio.run(stress_test(num_subs, "calc-multi-lang"))

print()
print("="*70)
print("✅ TEST COMPLETE!")
print("="*70)
print()
print("Next steps:")
print("  1. View results: python tests/performance/view_results.py --latest")
print("  2. Check the HTML report for submissions with correct filenames")
print("  3. Compare scores - new submissions should have scores > 0")
print()
print("🔍 What to look for in the report:")
print("  - Submissions after the test start time (just now)")
print("  - Filenames: calculator.py, Calculator.java, calculator.js, calculator.cpp")
print("  - Scores: Should be 100 for correct submissions")
print("  - Errors: Should see no 'file not found' errors")
print()

