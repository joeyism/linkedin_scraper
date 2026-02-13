#!/usr/bin/env python3
"""
Example: Search for jobs and scrape job details
"""
import asyncio
from linkedin_scraper.scrapers.job_search import JobSearchScraper
from linkedin_scraper.scrapers.job import JobScraper
from linkedin_scraper.core.browser import BrowserManager


async def main():
    """Search for jobs and scrape details"""
    
    # Uses default user_data_dir — session persists automatically
    async with BrowserManager(headless=False) as browser:
        
        # Search for jobs
        search_scraper = JobSearchScraper(browser.page)
        print("🔍 Searching for jobs...")
        job_urls = await search_scraper.search(
            keywords="software engineer",
            location="Toronto",
            limit=5
        )
        
        print(f"\n✓ Found {len(job_urls)} jobs")
        for url in job_urls:
            print(f"  - {url}")
        
        # Scrape first job details if any found
        if job_urls:
            print(f"\n📄 Scraping first job details...")
            job_scraper = JobScraper(browser.page)
            for job_url in job_urls:
                job = await job_scraper.scrape(job_url)
                
                print("\n" + "="*60)
                print(f"Title: {job.job_title}")
                print(f"Company: {job.company}")
                print(f"Location: {job.location}")
                print(f"Posted: {job.posted_date}")
                print(f"Applicants: {job.applicant_count}")
                print(f"Description: {job.job_description[:200]}..." if job.job_description else "Description: N/A")
                print("="*60)
    
    print("\n✓ Done!")


if __name__ == "__main__":
    asyncio.run(main())
