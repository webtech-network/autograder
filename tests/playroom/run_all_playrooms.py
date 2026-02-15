"""
Run all playroom tests in sequence.

This script executes all template playrooms and provides a summary report.
It initializes the sandbox manager once at the beginning and cleans up at the end.
Each playroom test is run in sequence, and errors are caught to allow other tests to continue.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sandbox_manager.manager import initialize_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig

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
    
    # Initialize sandbox manager once for all tests
    print("\n🔧 Initializing sandbox manager...")
    try:
        pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
        manager = initialize_sandbox_manager(pool_configs)
        print("✅ Sandbox manager ready\n")
        sandbox_initialized = True
    except Exception as e:
        print(f"❌ Failed to initialize sandbox manager: {str(e)}")
        print("   Some playrooms may fail without sandbox support\n")
        manager = None
        sandbox_initialized = False
    
    # Track results
    results = []
    playrooms = [
        ("Web Development", run_webdev_playroom, False),  # No sandbox needed
        ("API Testing", run_api_playroom, True),          # Needs sandbox
        ("Input/Output", run_io_playroom, True),          # Needs sandbox
        ("Essay Grading", run_essay_playroom, False)      # No sandbox needed
    ]
    
    # Run each playroom
    for name, runner, needs_sandbox in playrooms:
        # Skip sandbox-dependent tests if sandbox not available
        if needs_sandbox and not sandbox_initialized:
            print(f"\n{'='*80}")
            print(f" Skipping: {name} (requires sandbox)")
            print(f"{'='*80}\n")
            results.append((name, "⏭️  SKIPPED (no sandbox)"))
            continue
            
        try:
            print(f"\n{'='*80}")
            print(f" Running: {name}")
            print(f"{'='*80}\n")
            
            # For sandbox-dependent playrooms, they handle their own manager
            # For non-sandbox playrooms, just run them
            if needs_sandbox:
                # These playrooms initialize their own sandbox manager
                # We need to shutdown ours first to avoid conflicts
                if manager:
                    manager.shutdown()
                    manager = None
                runner()
                # Re-initialize for next test
                if needs_sandbox:
                    pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
                    manager = initialize_sandbox_manager(pool_configs)
            else:
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
    print("="*80)
    
    # Cleanup
    if manager:
        print("\n🧹 Cleaning up sandbox manager...")
        try:
            manager.shutdown()
            print("✅ Cleanup complete\n")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {str(e)}\n")


if __name__ == "__main__":
    main()
