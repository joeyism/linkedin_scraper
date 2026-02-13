#!/usr/bin/env python3
"""
Example: Scrape person profile with detailed information

This example shows how to scrape a LinkedIn person profile including
work experience and education history.
"""
import asyncio
from linkedin_scraper.scrapers.person import PersonScraper
from linkedin_scraper.core.browser import BrowserManager


async def main():
    """Scrape a person profile"""
    profile_url = "https://www.linkedin.com/in/williamhgates/"
    
    # Uses default user_data_dir — session persists automatically
    async with BrowserManager(headless=False) as browser:
        # Initialize scraper with the browser page
        scraper = PersonScraper(browser.page)
        
        # Scrape the profile
        print(f"🚀 Scraping: {profile_url}")
        person = await scraper.scrape(profile_url)
        
        # Display person info
        print("\n" + "="*60)
        print(f"Person: {person.name}")
        print(f"Location: {person.location}")
        print(f"About: {person.about[:100] if person.about else 'N/A'}...")
        print("="*60)
        
        # Display work experience
        print(f"\n💼 Work Experience ({len(person.experiences)} positions):")
        for exp in person.experiences[:5]:  # Show first 5
            print(f"  - {exp.position_title} at {exp.institution_name}")
            print(f"    {exp.from_date} - {exp.to_date}")
        
        if len(person.experiences) > 5:
            print(f"  ... and {len(person.experiences) - 5} more positions")
        
        # Display education
        print(f"\n🎓 Education ({len(person.educations)} schools):")
        for edu in person.educations[:3]:  # Show first 3
            print(f"  - {edu.institution_name}")
            if edu.degree:
                print(f"    {edu.degree}")
        
        if len(person.educations) > 3:
            print(f"  ... and {len(person.educations) - 3} more schools")
    
    print("\n✓ Done!")


if __name__ == "__main__":
    asyncio.run(main())
