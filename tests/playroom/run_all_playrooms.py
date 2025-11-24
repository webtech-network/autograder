"""
Run All Playrooms

This script allows you to run all playrooms or individual ones for testing purposes.

Usage:
    python -m tests.playroom.run_all_playrooms              # Run all playrooms
    python -m tests.playroom.run_all_playrooms webdev       # Run only webdev playroom
    python -m tests.playroom.run_all_playrooms api essay    # Run multiple playrooms
    python -m tests.playroom.run_all_playrooms --list       # List available playrooms
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


# Import all playroom functions
from tests.playroom.webdev_playroom import run_webdev_playroom
from tests.playroom.api_playroom import run_api_playroom
from tests.playroom.essay_playroom import run_essay_playroom
from tests.playroom.io_playroom import run_io_playroom


# Map of playroom names to their runner functions
PLAYROOMS = {
    "webdev": {
        "name": "Web Development",
        "runner": run_webdev_playroom,
        "description": "Tests HTML/CSS grading with Bootstrap and custom classes"
    },
    "api": {
        "name": "API Testing",
        "runner": run_api_playroom,
        "description": "Tests REST API endpoints in a Docker container"
    },
    "essay": {
        "name": "Essay Grading",
        "runner": run_essay_playroom,
        "description": "Tests AI-powered essay grading (requires OpenAI API key)"
    },
    "io": {
        "name": "Input/Output",
        "runner": run_io_playroom,
        "description": "Tests command-line programs with stdin/stdout validation"
    }
}


def list_playrooms():
    """Display all available playrooms."""
    print("\n" + "="*70)
    print("AVAILABLE PLAYROOMS")
    print("="*70 + "\n")

    for key, info in PLAYROOMS.items():
        print(f"  {key:10} - {info['name']}")
        print(f"             {info['description']}")
        print()

    print("="*70 + "\n")


def run_playroom(playroom_key: str):
    """Run a specific playroom by its key."""
    if playroom_key not in PLAYROOMS:
        print(f"❌ Error: Unknown playroom '{playroom_key}'")
        print(f"   Available playrooms: {', '.join(PLAYROOMS.keys())}")
        return False

    try:
        PLAYROOMS[playroom_key]["runner"]()
        return True
    except Exception as e:
        print(f"\n❌ Error running {playroom_key} playroom: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all():
    """Run all playrooms sequentially."""
    print("\n" + "#"*70)
    print("# RUNNING ALL PLAYROOMS")
    print("#"*70 + "\n")

    results = {}
    for key in PLAYROOMS.keys():
        success = run_playroom(key)
        results[key] = success
        print("\n" + "-"*70 + "\n")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70 + "\n")

    for key, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {PLAYROOMS[key]['name']:20} - {status}")

    total = len(results)
    passed = sum(1 for s in results.values() if s)
    print(f"\n  Total: {passed}/{total} playrooms completed successfully")
    print("\n" + "="*70 + "\n")


def main():
    """Main entry point for the playroom runner."""
    parser = argparse.ArgumentParser(
        description="Run autograder playrooms for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tests.playroom.run_all_playrooms              # Run all playrooms
  python -m tests.playroom.run_all_playrooms webdev       # Run only webdev
  python -m tests.playroom.run_all_playrooms api essay    # Run multiple
  python -m tests.playroom.run_all_playrooms --list       # List available
        """
    )

    parser.add_argument(
        'playrooms',
        nargs='*',
        help='Specific playrooms to run (e.g., webdev api). If none specified, runs all.'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available playrooms'
    )

    args = parser.parse_args()

    # Handle --list flag
    if args.list:
        list_playrooms()
        return

    # If no playrooms specified, run all
    if not args.playrooms:
        run_all()
        return

    # Run specified playrooms
    print(f"\n🎮 Running {len(args.playrooms)} playroom(s)...\n")
    for playroom_key in args.playrooms:
        run_playroom(playroom_key)
        if len(args.playrooms) > 1:
            print("\n" + "-"*70 + "\n")


if __name__ == "__main__":
    main()

