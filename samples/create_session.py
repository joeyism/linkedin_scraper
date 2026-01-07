#!/usr/bin/env python3
"""
Create LinkedIn Session File

This script helps you create a linkedin_session.json file by logging in manually.
The session file is needed to run integration tests and scraping examples.

Usage:
    python samples/create_session.py
    
The script will:
1. Open a browser window with LinkedIn login page
2. Wait for you to manually log in (up to 5 minutes)
3. Automatically detect when login is complete
4. Save your session to linkedin_session.json

Note: The session file contains authentication cookies and should never be committed to git.
"""
import asyncio
from linkedin_scraper import BrowserManager, wait_for_manual_login


async def create_session():
    """Create a LinkedIn session file through manual login."""
    print("="*60)
    print("LinkedIn Session Creator")
    print("="*60)
    print("\nThis script will help you create a session file for LinkedIn.")
    print("\nSteps:")
    print("1. A browser window will open")
    print("2. Log in to LinkedIn manually")
    print("3. The script will detect when you're logged in")
    print("4. Your session will be saved to linkedin_session.json")
    print("\n" + "="*60 + "\n")
    
    async with BrowserManager(headless=False) as browser:
        # Navigate to LinkedIn login page
        print("Opening LinkedIn login page...")
        await browser.page.goto("https://www.linkedin.com/login")
        
        print("\n🔐 Please log in to LinkedIn in the browser window...")
        print("   (You have 5 minutes to complete the login)")
        print("   - Enter your email and password")
        print("   - Complete any 2FA or CAPTCHA challenges")
        print("   - Wait for your feed to load")
        print("\n⏳ Waiting for login completion...\n")
        
        # Wait for manual login (5 minutes timeout)
        try:
            await wait_for_manual_login(browser.page, timeout=300000)
        except Exception as e:
            print(f"\n❌ Login failed: {e}")
            print("\nPlease try again and make sure you:")
            print("  - Complete the login within 5 minutes")
            print("  - Wait until your LinkedIn feed loads")
            return
        
        # Save session to project root
        session_path = "linkedin_session.json"
        print(f"\n💾 Saving session to {session_path}...")
        await browser.save_session(session_path)
        
        print("\n" + "="*60)
        print("✅ Success! Session file created.")
        print("="*60)
        print(f"\nSession saved to: {session_path}")
        print("\nYou can now:")
        print("  - Run integration tests: pytest")
        print("  - Run example scripts: python samples/scrape_person.py")
        print("\nNote: Keep this file secure and don't commit it to git.")
        print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(create_session())
