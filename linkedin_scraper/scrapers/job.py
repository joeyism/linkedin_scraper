"""
Job scraper for LinkedIn.

Extracts job posting information from LinkedIn job pages.
"""
import logging
from typing import Optional
from patchright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from ..models.job import Job
from ..callbacks import ProgressCallback
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
            page: Patchright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback)
    
    async def scrape(self, linkedin_url: str) -> Job:
        """
        Scrape a LinkedIn job posting.
        
        Args:
            linkedin_url: URL of the LinkedIn job posting
            
        Returns:
            Job object with scraped data
            
        Raises:
            ScrapingError: If scraping fails
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
        """Extract job title from h1 heading."""
        try:
            title_elem = self.page.locator('h1').first
            title = await title_elem.inner_text()
            return title.strip()
        except PlaywrightTimeoutError:
            return None
        except Exception as e:
            logger.debug(f"Error extracting job title: {e}")
            return None
    
    async def _get_company(self) -> Optional[str]:
        """Extract company name from company link."""
        try:
            # Find company links that have text (not just images)
            company_links = await self.page.locator('a[href*="/company/"]').all()
            for link in company_links:
                text = await link.inner_text()
                text = text.strip()
                # Skip empty or very short text (likely image-only links)
                if text and len(text) > 1 and not text.startswith('logo'):
                    return text
        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error extracting company name: {e}")
        return None
    
    async def _get_company_url(self) -> Optional[str]:
        """Extract company LinkedIn URL."""
        try:
            company_link = self.page.locator('a[href*="/company/"]').first
            if await company_link.count() > 0:
                href = await company_link.get_attribute('href')
                if href:
                    if '?' in href:
                        href = href.split('?')[0]
                    if not href.startswith('http'):
                        href = f"https://www.linkedin.com{href}"
                    return href
        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error extracting company URL: {e}")
        return None
    
    async def _get_location(self) -> Optional[str]:
        """Extract job location from job details panel."""
        try:
            job_panel = self.page.locator('h1').first.locator('xpath=ancestor::*[5]')
            if await job_panel.count() > 0:
                text_elements = await job_panel.locator('span, div').all()
                for elem in text_elements:
                    text = await elem.inner_text()
                    if text and (',' in text or 'Remote' in text or 'United States' in text):
                        text = text.strip()
                        if len(text) > 3 and len(text) < 100 and not text.startswith('$'):
                            return text
        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error extracting job location: {e}")
        return None
    
    async def _get_posted_date(self) -> Optional[str]:
        """Extract posted date from job details."""
        try:
            text_elements = await self.page.locator('span, div').all()
            for elem in text_elements:
                text = await elem.inner_text()
                if text and ('ago' in text.lower() or 'day' in text.lower() or 'week' in text.lower() or 'hour' in text.lower()):
                    text = text.strip()
                    if len(text) < 50:
                        return text
        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error extracting posted date: {e}")
        return None
    
    async def _get_applicant_count(self) -> Optional[str]:
        """Extract applicant count from job details."""
        try:
            main_content = self.page.locator('main').first
            if await main_content.count() > 0:
                text_elements = await main_content.locator('span, div').all()
                for elem in text_elements:
                    text = await elem.inner_text()
                    text = text.strip()
                    if text and len(text) < 50:
                        text_lower = text.lower()
                        if 'applicant' in text_lower or 'people clicked' in text_lower or 'applied' in text_lower:
                            return text
        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error extracting applicant count: {e}")
        return None
    
    async def _get_description(self) -> Optional[str]:
        """Extract job description from article or about section."""
        try:
            about_heading = self.page.locator('h2:has-text("About the job")').first
            if await about_heading.count() > 0:
                article = about_heading.locator('xpath=ancestor::article[1]')
                if await article.count() > 0:
                    description = await article.inner_text()
                    return description.strip()
            
            article = self.page.locator('article').first
            if await article.count() > 0:
                description = await article.inner_text()
                return description.strip()
        except PlaywrightTimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Error extracting job description: {e}")
        return None
