"""
Job search scraper for LinkedIn.

Searches for jobs on LinkedIn and extracts job URLs.
"""
import logging
from typing import Optional, List
from urllib.parse import urlencode
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from .base import BaseScraper

logger = logging.getLogger(__name__)


class JobSearchScraper(BaseScraper):
    """
    Scraper for LinkedIn job search results.
    
    Example:
        async with BrowserManager() as browser:
            scraper = JobSearchScraper(browser.page)
            job_urls = await scraper.search(
                keywords="software engineer",
                location="San Francisco",
                limit=10
            )
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize job search scraper.
        
        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())
    
    async def search(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 25
    ) -> List[str]:
        """
        Search for jobs on LinkedIn.
        
        Args:
            keywords: Job search keywords (e.g., "software engineer")
            location: Job location (e.g., "San Francisco, CA")
            limit: Maximum number of job URLs to return
            
        Returns:
            List of job posting URLs
        """
        logger.info(f"Starting job search: keywords='{keywords}', location='{location}'")
        
        # Build search URL
        search_url = self._build_search_url(keywords, location)
        await self.callback.on_start("JobSearch", search_url)
        
        # Navigate to search results
        await self.navigate_and_wait(search_url)
        await self.callback.on_progress("Navigated to search results", 20)
        
        # Wait for job listings to load
        await self.page.wait_for_selector('.jobs-search__results-list', timeout=10000)
        await self.wait_and_focus(1)
        
        # Scroll to load more results
        await self.scroll_page_to_bottom(pause_time=1, max_scrolls=3)
        await self.callback.on_progress("Loaded job listings", 50)
        
        # Extract job URLs
        job_urls = await self._extract_job_urls(limit)
        await self.callback.on_progress(f"Found {len(job_urls)} job URLs", 90)
        
        await self.callback.on_progress("Search complete", 100)
        await self.callback.on_complete("JobSearch", job_urls)
        
        logger.info(f"Job search complete: found {len(job_urls)} jobs")
        return job_urls
    
    def _build_search_url(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None
    ) -> str:
        """Build LinkedIn job search URL with parameters."""
        base_url = "https://www.linkedin.com/jobs/search/"
        
        params = {}
        if keywords:
            params['keywords'] = keywords
        if location:
            params['location'] = location
        
        if params:
            return f"{base_url}?{urlencode(params)}"
        return base_url
    
    async def _extract_job_urls(self, limit: int) -> List[str]:
        """
        Extract job URLs from search results.
        
        Args:
            limit: Maximum number of URLs to extract
            
        Returns:
            List of job posting URLs
        """
        job_urls = []
        
        try:
            # Find all job cards/links
            job_links = await self.page.locator('a[href*="/jobs/view/"]').all()
            
            seen_urls = set()
            for link in job_links:
                if len(job_urls) >= limit:
                    break
                
                try:
                    href = await link.get_attribute('href')
                    if href and '/jobs/view/' in href:
                        # Clean URL (remove query params)
                        clean_url = href.split('?')[0] if '?' in href else href
                        
                        # Ensure full URL
                        if not clean_url.startswith('http'):
                            clean_url = f"https://www.linkedin.com{clean_url}"
                        
                        # Avoid duplicates
                        if clean_url not in seen_urls:
                            job_urls.append(clean_url)
                            seen_urls.add(clean_url)
                except Exception as e:
                    logger.debug(f"Error extracting job URL: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error extracting job URLs: {e}")
        
        return job_urls
