"""
Run all playroom tests in sequence.

This script executes all template playrooms and provides a summary report.
Note: Since playroom scripts currently manage their own sandbox managers,
this script does not initialize a shared sandbox manager to avoid conflicts.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import playroom runners
from tests.playroom.webdev_playroom import run_webdev_playroom
from tests.playroom.api_playroom import run_api_playroom
from tests.playroom.io_playroom import run_io_playroom
from tests.playroom.essay_playroom import run_essay_playroom


def main():
    """Run all playroom tests."""
    print("="*80)
    print(" AUTOGRADER PLAYROOM TEST SUITE")
    print("="*80)
    print("\nNote: Each playroom manages its own sandbox manager (if needed)")
    print("This ensures clean state between tests.\n")
    
    # Track results
    results = []
    playrooms = [
        ("Web Development", run_webdev_playroom, False),  # No sandbox needed
        ("API Testing", run_api_playroom, True),          # Needs sandbox (manages own)
        ("Input/Output", run_io_playroom, True),          # Needs sandbox (manages own)
        ("Essay Grading", run_essay_playroom, False)      # No sandbox needed
    ]
    
    # Run each playroom
    for name, runner, needs_sandbox in playrooms:
        try:
            print(f"\n{'='*80}")
            print(f" Running: {name}")
            print(f"{'='*80}\n")
            
            # Each playroom manages its own resources
            runner()
            
            results.append((name, "✅ PASSED"))
        except Exception as e:
            print(f"\n❌ Error in {name}: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((name, f"❌ FAILED: {str(e)}"))
    
    # Display summary
    print("\n" + "="*80)
    print(" PLAYROOM TEST SUMMARY")
    print("="*80)
    for name, status in results:
        print(f"{name:30s} {status}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
