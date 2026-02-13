#!/usr/bin/env python3
"""
Example: Scrape a LinkedIn company page

This example shows how to use the CompanyScraper to scrape company information.
"""
import asyncio
from linkedin_scraper.scrapers.company import CompanyScraper
from linkedin_scraper.core.browser import BrowserManager


async def main():
    """Scrape a single company"""
    company_url = "https://www.linkedin.com/company/microsoft/"
    
    # Uses default user_data_dir — session persists automatically
    async with BrowserManager(headless=False) as browser:
        # Initialize scraper with the browser page
        scraper = CompanyScraper(browser.page)
        
        # Scrape the company
        print(f"🚀 Scraping: {company_url}")
        company = await scraper.scrape(company_url)
        
        # Display results
        print("\n" + "="*60)
        print(f"Name: {company.name}")
        print(f"Industry: {company.industry}")
        print(f"Company Size: {company.company_size}")
        print(f"Headquarters: {company.headquarters}")
        print(f"Founded: {company.founded}")
        print(f"Website: {company.website}")
        if company.about_us:
            print(f"About: {company.about_us[:150]}...")
        print("="*60)
    
    print("\n✓ Done!")


if __name__ == "__main__":
    asyncio.run(main())
