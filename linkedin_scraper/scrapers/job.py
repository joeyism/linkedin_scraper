"""
Job scraper for LinkedIn.

Extracts job posting information from LinkedIn job pages.
"""
import logging
from typing import Optional
from playwright.async_api import Page

from ..models.job import Job
from ..core.exceptions import ProfileNotFoundError
from ..callbacks import ProgressCallback, SilentCallback
from .base import BaseScraper

logger = logging.getLogger(__name__)


class JobScraper(BaseScraper):
    """
    Scraper for LinkedIn job postings.
    
    Example:
        async with BrowserManager() as browser:
            scraper = JobScraper(browser.page)
            job = await scraper.scrape("https://www.linkedin.com/jobs/view/123456/")
            print(job.to_json())
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize job scraper.
        
        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())
    
    async def scrape(self, linkedin_url: str) -> Job:
        """
        Scrape a LinkedIn job posting.
        
        Args:
            linkedin_url: URL of the LinkedIn job posting
            
        Returns:
            Job object with scraped data
            
        Raises:
            ProfileNotFoundError: If job posting not found
        """
        logger.info(f"Starting job scraping: {linkedin_url}")
        await self.callback.on_start("Job", linkedin_url)
        
        # Navigate to job page
        await self.navigate_and_wait(linkedin_url)
        await self.callback.on_progress("Navigated to job page", 10)
        
        # Check if page exists
        await self.check_rate_limit()
        
        # Extract job details
        job_title = await self._get_job_title()
        await self.callback.on_progress(f"Got job title: {job_title}", 20)
        
        company = await self._get_company()
        await self.callback.on_progress("Got company name", 30)
        
        location = await self._get_location()
        await self.callback.on_progress("Got location", 40)
        
        posted_date = await self._get_posted_date()
        await self.callback.on_progress("Got posted date", 50)
        
        applicant_count = await self._get_applicant_count()
        await self.callback.on_progress("Got applicant count", 60)
        
        job_description = await self._get_description()
        await self.callback.on_progress("Got job description", 80)
        
        company_url = await self._get_company_url()
        await self.callback.on_progress("Got company URL", 90)
        
        # Create job object
        job = Job(
            linkedin_url=linkedin_url,
            job_title=job_title,
            company=company,
            company_linkedin_url=company_url,
            location=location,
            posted_date=posted_date,
            applicant_count=applicant_count,
            job_description=job_description
        )
        
        await self.callback.on_progress("Scraping complete", 100)
        await self.callback.on_complete("Job", job)
        
        logger.info(f"Successfully scraped job: {job_title}")
        return job
    
    async def _get_job_title(self) -> Optional[str]:
        """Extract job title."""
        try:
            # Try h1 heading
            title_elem = self.page.locator('h1').first
            title = await title_elem.inner_text()
            return title.strip()
        except:
            return None
    
    async def _get_company(self) -> Optional[str]:
        """Extract company name."""
        try:
            # Look for company name link or text
            company_elem = self.page.locator('.job-details-jobs-unified-top-card__company-name').first
            company = await company_elem.inner_text()
            return company.strip()
        except:
            # Fallback: look for any link with "company" in it
            try:
                links = await self.page.locator('a').all()
                for link in links:
                    href = await link.get_attribute('href')
                    if href and '/company/' in href:
                        text = await link.inner_text()
                        if text and len(text.strip()) > 0:
                            return text.strip()
            except:
                pass
            return None
    
    async def _get_company_url(self) -> Optional[str]:
        """Extract company LinkedIn URL."""
        try:
            links = await self.page.locator('a').all()
            for link in links:
                href = await link.get_attribute('href')
                if href and '/company/' in href and 'linkedin.com' in href:
                    # Clean up URL (remove query params)
                    if '?' in href:
                        href = href.split('?')[0]
                    return href
        except:
            pass
        return None
    
    async def _get_location(self) -> Optional[str]:
        """Extract job location."""
        try:
            location_elem = self.page.locator('.job-details-jobs-unified-top-card__bullet').first
            location = await location_elem.inner_text()
            return location.strip()
        except:
            return None
    
    async def _get_posted_date(self) -> Optional[str]:
        """Extract posted date."""
        try:
            # Look for text containing "ago" or date info
            text_elements = await self.page.locator('span').all()
            for elem in text_elements:
                text = await elem.inner_text()
                if 'ago' in text.lower() or 'posted' in text.lower():
                    return text.strip()
        except:
            pass
        return None
    
    async def _get_applicant_count(self) -> Optional[str]:
        """Extract applicant count."""
        try:
            # Look for applicant count text
            text_elements = await self.page.locator('span').all()
            for elem in text_elements:
                text = await elem.inner_text()
                if 'applicant' in text.lower():
                    return text.strip()
        except:
            pass
        return None
    
    async def _get_description(self) -> Optional[str]:
        """Extract job description."""
        try:
            # Look for the description section
            desc_elem = self.page.locator('.jobs-description__content').first
            description = await desc_elem.inner_text()
            return description.strip()
        except:
            # Fallback: try to find article or main content
            try:
                article = self.page.locator('article').first
                description = await article.inner_text()
                return description.strip()
            except:
                pass
            return None
