"""
Migrate from session.json to persistent browser profile.

If you have an existing session.json file created with BrowserManager,
this script will migrate it to a persistent browser profile that works
more reliably and doesn't require manual save/load calls.

Usage:
    python samples/migrate_session.py

This will:
1. Load your existing session.json
2. Create a new persistent profile at ~/.linkedin/profile
3. Copy all cookies and session data
4. Verify the migration worked
5. Optionally delete the old session.json

After migration, use PersistentBrowserManager in your scripts instead of BrowserManager.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from linkedin_scraper import migrate_session_to_profile  # noqa: E402


async def migrate():
    """Migrate session.json to persistent profile."""

    session_file = Path("session.json")
    profile_dir = Path.home() / ".linkedin" / "profile"

    print("LinkedIn Session Migration Tool")
    print("=" * 60)
    print()

    # Check if session.json exists
    if not session_file.exists():
        print("✗ session.json not found in current directory")
        print()
        print("Please make sure session.json exists, or create one first:")
        print("    python samples/create_session.py")
        return

    print(f"Source: {session_file.absolute()}")
    print(f"Target: {profile_dir}")
    print()

    # Check if profile already exists
    if profile_dir.exists():
        print("⚠ Warning: Target profile directory already exists")
        print(f"   {profile_dir}")
        print()
        response = input("Overwrite existing profile? (y/N): ")
        if response.lower() != "y":
            print("Migration cancelled")
            return
        print()

    print("Starting migration...")
    print()

    try:
        success = await migrate_session_to_profile(
            session_path=session_file, user_data_dir=profile_dir, headless=True
        )

        print()
        if success:
            print("✓ Migration successful!")
            print()
            print(f"Your persistent profile is ready at: {profile_dir}")
            print()
            print("You can now use PersistentBrowserManager in your scripts:")
            print()
            print("    from linkedin_scraper import PersistentBrowserManager")
            print()
            print(
                "    async with PersistentBrowserManager("
                "user_data_dir='~/.linkedin/profile') as browser:"
            )
            print("        # Your scraping code here")
            print()

            # Ask if user wants to delete session.json
            response = input("Delete old session.json file? (y/N): ")
            if response.lower() == "y":
                os.remove(session_file)
                print(f"✓ Deleted {session_file}")
            else:
                print(f"Kept {session_file} - you can delete it manually later")

        else:
            print("✗ Migration completed but login verification failed")
            print()
            print("The cookies were copied, but you may need to log in again.")
            print(
                "Run create_persistent_session.py to create a fresh authenticated profile:"
            )
            print("    python samples/create_persistent_session.py")

    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(migrate())
