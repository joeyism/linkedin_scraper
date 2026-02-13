#!/usr/bin/env python3
"""
Create LinkedIn Session

This script creates a persistent browser session by logging in manually.
The session is stored in the browser's user data directory and automatically
persists between runs — no session files needed.

Usage:
    python samples/create_session.py

The script will:
1. Open a browser window with LinkedIn login page
2. Wait for you to manually log in (up to 5 minutes)
3. Automatically detect when login is complete
4. Close the browser — session is persisted automatically

After running this, all other sample scripts will reuse the same session.
"""
import asyncio
from linkedin_scraper import BrowserManager, wait_for_manual_login


async def create_session():
    """Create a LinkedIn session through manual login."""
    print("=" * 60)
    print("LinkedIn Session Creator")
    print("=" * 60)
    print("\nThis script will help you create a persistent session for LinkedIn.")
    print("\nSteps:")
    print("1. A browser window will open")
    print("2. Log in to LinkedIn manually")
    print("3. The script will detect when you're logged in")
    print("4. Session persists automatically in the browser data directory")
    print("\n" + "=" * 60 + "\n")

    # Uses default user_data_dir (~/.linkedin_scraper/browser_data)
    async with BrowserManager(headless=False) as browser:
        # Navigate to LinkedIn login page
        print("Opening LinkedIn login page...")
        await browser.page.goto("https://www.linkedin.com/login")

        print("\nPlease log in to LinkedIn in the browser window...")
        print("   (You have 5 minutes to complete the login)")
        print("   - Enter your email and password")
        print("   - Complete any 2FA or CAPTCHA challenges")
        print("   - Wait for your feed to load")
        print("\nWaiting for login completion...\n")

        # Wait for manual login (5 minutes timeout)
        try:
            await wait_for_manual_login(browser.page, timeout=300000)
        except Exception as e:
            print(f"\nLogin failed: {e}")
            print("\nPlease try again and make sure you:")
            print("  - Complete the login within 5 minutes")
            print("  - Wait until your LinkedIn feed loads")
            return

        print("\n" + "=" * 60)
        print("Success! Session created and persisted automatically.")
        print("=" * 60)
        print("\nYour session is stored in the persistent browser profile.")
        print("All future runs using the same user_data_dir will be authenticated.")
        print("\nYou can now:")
        print("  - Run integration tests: pytest")
        print("  - Run example scripts: python samples/scrape_person.py")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(create_session())
