"""
Wrapper script for seeding with better error reporting for Render builds.
"""
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_seed():
    try:
        print("=" * 60)
        print("Starting seed_data.py...")
        print("=" * 60)
        import seed_data
        print("✓ seed_data completed successfully\n")
    except Exception as e:
        print(f"✗ seed_data FAILED: {e}")
        traceback.print_exc()
        return False

    try:
        print("=" * 60)
        print("Starting seed_documents.py...")
        print("=" * 60)
        import seed_documents
        print("✓ seed_documents completed successfully\n")
    except Exception as e:
        print(f"✗ seed_documents FAILED: {e}")
        traceback.print_exc()
        return False

    print("=" * 60)
    print("All seeding completed successfully!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_seed()
    sys.exit(0 if success else 1)
