"""
Create a persistent LinkedIn session using PersistentBrowserManager.

This script helps you log in to LinkedIn once and save your session
to a persistent browser profile. Unlike session.json, this profile
works exactly like a real Chrome profile and automatically saves
cookies and session data.

Usage:
    python samples/create_persistent_session.py

The profile will be saved to ~/.linkedin/profile by default.
You can then use this profile in your scraping scripts.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from linkedin_scraper import (  # noqa: E402
    PersistentBrowserManager,
    wait_for_manual_login,
    is_logged_in,
)


async def create_persistent_session():
    """Create a persistent LinkedIn session via manual login."""

    profile_dir = Path.home() / ".linkedin" / "profile"

    print("Creating persistent LinkedIn session...")
    print(f"Profile will be saved to: {profile_dir}")
    print()

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=False  # Show browser for manual login
    ) as browser:
        # Navigate to LinkedIn login
        print("Navigating to LinkedIn login page...")
        await browser.page.goto("https://www.linkedin.com/login")

        # Check if already logged in (from previous session)
        if await is_logged_in(browser.page):
            print("✓ Already logged in! Session is active.")
            print()
            print(f"Profile location: {profile_dir}")
            print()
            print("You can now use this profile in your scraping scripts:")
            print()
            print(
                "    from linkedin_scraper import PersistentBrowserManager, PersonScraper"
            )
            print()
            print(
                "    async with PersistentBrowserManager("
                "user_data_dir='~/.linkedin/profile') as browser:"
            )
            print("        scraper = PersonScraper(browser.page)")
            print(
                "        person = await scraper.scrape('https://linkedin.com/in/username')"
            )
            return

        # Wait for manual login
        print()
        print("=" * 60)
        print("Please log in to LinkedIn in the browser window...")
        print("=" * 60)
        print()

        try:
            await wait_for_manual_login(browser.page, timeout=300)  # 5 minute timeout
            print()
            print("✓ Login successful!")
        except TimeoutError:
            print()
            print("✗ Login timed out. Please try again.")
            return

        # Verify login
        if await is_logged_in(browser.page):
            print("✓ Session verified!")
            print()
            print(f"Profile saved to: {profile_dir}")
            print()
            print("You can now use this profile in your scraping scripts:")
            print()
            print(
                "    from linkedin_scraper import PersistentBrowserManager, PersonScraper"
            )
            print()
            print(
                "    async with PersistentBrowserManager("
                "user_data_dir='~/.linkedin/profile') as browser:"
            )
            print("        scraper = PersonScraper(browser.page)")
            print(
                "        person = await scraper.scrape('https://linkedin.com/in/username')"
            )
            print()
            print(
                "The session will persist across script runs - no need to log in again!"
            )
        else:
            print("✗ Login verification failed. Please try again.")


if __name__ == "__main__":
    asyncio.run(create_persistent_session())
