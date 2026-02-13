#!/usr/bin/env python3
"""
Example: Scrape a single LinkedIn profile

This example shows how to use the PersonScraper to scrape a LinkedIn profile.
Requires a prior session created via create_session.py.
"""
import asyncio
from linkedin_scraper.scrapers.person import PersonScraper
from linkedin_scraper.core.browser import BrowserManager


async def main():
    """Scrape a single person profile"""
    profile_url = "https://www.linkedin.com/in/williamhgates/"

    # Uses default user_data_dir — session persists automatically
    async with BrowserManager(headless=False) as browser:
        # Initialize scraper with the browser page
        scraper = PersonScraper(browser.page)

        # Scrape the profile
        print(f"Scraping: {profile_url}")
        person = await scraper.scrape(profile_url)

        # Display results
        print("\n" + "=" * 60)
        print(f"Name: {person.name}")
        print(f"Location: {person.location}")
        print(f"About: {person.about[:100]}..." if person.about else "About: N/A")
        print(f"Experiences: {len(person.experiences)}")
        print(f"Education: {len(person.educations)}")
        print("=" * 60)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
