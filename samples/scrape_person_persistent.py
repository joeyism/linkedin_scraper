"""
Scrape a LinkedIn profile using PersistentBrowserManager.

This example demonstrates using a persistent browser profile for scraping.
Run create_persistent_session.py first to create your authenticated profile.

Usage:
    python samples/scrape_person_persistent.py

The script will reuse your existing session from ~/.linkedin/profile
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from linkedin_scraper import (  # noqa: E402
    PersistentBrowserManager,
    PersonScraper,
    is_logged_in,
    ConsoleCallback,
)


async def scrape_person_with_persistent_profile():
    """Scrape a person's LinkedIn profile using persistent browser profile."""

    profile_dir = Path.home() / ".linkedin" / "profile"

    # Check if profile exists
    if not profile_dir.exists():
        print("✗ No persistent profile found!")
        print()
        print("Please run create_persistent_session.py first to create a profile:")
        print("    python samples/create_persistent_session.py")
        return

    print(f"Using persistent profile from: {profile_dir}")
    print()

    # Example profile URL - replace with your target
    profile_url = "https://www.linkedin.com/in/williamhgates/"

    # Create console callback for progress tracking
    callback = ConsoleCallback()

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=False  # Set to True for headless mode
    ) as browser:
        print("Browser started with persistent profile")

        # Verify we're logged in
        await browser.page.goto("https://www.linkedin.com/feed/")
        if not await is_logged_in(browser.page):
            print("✗ Not logged in! Your session may have expired.")
            print("Please run create_persistent_session.py to log in again.")
            return

        print("✓ Logged in successfully")
        print()
        print(f"Scraping profile: {profile_url}")
        print()

        # Create scraper with progress callback
        scraper = PersonScraper(browser.page, callback=callback)

        try:
            # Scrape the profile
            person = await scraper.scrape(profile_url)

            # Display results
            print()
            print("=" * 60)
            print("Profile Data")
            print("=" * 60)
            print(f"Name: {person.name}")
            print(f"Headline: {person.headline}")
            print(f"Location: {person.location}")
            print()
            print(f"Experiences: {len(person.experiences)}")
            if person.experiences:
                print("\nMost Recent Experience:")
                exp = person.experiences[0]
                print(f"  • {exp.title} at {exp.company}")
                print(f"    {exp.date_range}")

            print()
            print(f"Education: {len(person.educations)}")
            if person.educations:
                print("\nMost Recent Education:")
                edu = person.educations[0]
                print(f"  • {edu.degree} from {edu.institution}")
                print(f"    {edu.date_range}")

            print()
            print(f"Skills: {len(person.skills)}")
            if person.skills:
                print(f"  Top skills: {', '.join(person.skills[:5])}")

            print()
            print("=" * 60)
            print()
            print("✓ Scraping complete!")
            print()
            print(
                "Note: Your session is automatically saved to the persistent profile."
            )
            print("Next time you run this script, you'll still be logged in!")

        except Exception as e:
            print(f"✗ Error scraping profile: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(scrape_person_with_persistent_profile())
