"""
Company scraper for LinkedIn.

Extracts company information from LinkedIn company pages.
"""
import logging
from typing import Optional
from playwright.async_api import Page

from ..models.company import Company
from ..core.exceptions import ProfileNotFoundError
from ..callbacks import ProgressCallback, SilentCallback
from .base import BaseScraper

logger = logging.getLogger(__name__)


class CompanyScraper(BaseScraper):
    """
    Scraper for LinkedIn company pages.
    
    Example:
        async with BrowserManager() as browser:
            scraper = CompanyScraper(browser.page)
            company = await scraper.scrape("https://www.linkedin.com/company/microsoft/")
            print(company.to_json())
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize company scraper.
        
        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())
    
    async def scrape(self, linkedin_url: str) -> Company:
        """
        Scrape a LinkedIn company page.
        
        Args:
            linkedin_url: URL of the LinkedIn company page
            
        Returns:
            Company object with scraped data
            
        Raises:
            ProfileNotFoundError: If company page not found
        """
        logger.info(f"Starting company scraping: {linkedin_url}")
        await self.callback.on_start("company", linkedin_url)
        
        # Navigate to company page
        await self.navigate_and_wait(linkedin_url)
        await self.callback.on_progress("Navigated to company page", 10)
        
        # Check if page exists
        await self.check_rate_limit()
        
        # Extract basic info
        name = await self._get_name()
        await self.callback.on_progress(f"Got company name: {name}", 20)
        
        about_us = await self._get_about()
        await self.callback.on_progress("Got about section", 30)
        
        # Extract overview details
        overview = await self._get_overview()
        await self.callback.on_progress("Got overview details", 50)
        
        # Create company object
        company = Company(
            linkedin_url=linkedin_url,
            name=name,
            about_us=about_us,
            **overview
        )
        
        await self.callback.on_progress("Scraping complete", 100)
        await self.callback.on_complete("company", company)
        
        logger.info(f"Successfully scraped company: {name}")
        return company
    
    async def _get_name(self) -> str:
        """Extract company name."""
        try:
            # Try main heading
            name_elem = self.page.locator('h1').first
            name = await name_elem.inner_text()
            return name.strip()
        except Exception as e:
            logger.warning(f"Error getting company name: {e}")
            return "Unknown Company"
    
    async def _get_about(self) -> Optional[str]:
        """Extract about/description section."""
        try:
            # Look for "About us" section
            sections = await self.page.locator('section').all()
            
            for section in sections:
                section_text = await section.inner_text()
                if 'About us' in section_text[:50]:
                    # Get the content paragraph
                    paragraphs = await section.locator('p').all()
                    if paragraphs:
                        about = await paragraphs[0].inner_text()
                        return about.strip()
            
            return None
        except Exception as e:
            logger.debug(f"Error getting about section: {e}")
            return None
    
    async def _get_overview(self) -> dict:
        """
        Extract company overview details (website, industry, size, etc.).
        
        Returns dict with: website, phone, headquarters, founded, industry,
        company_type, company_size, specialties
        """
        overview = {
            "website": None,
            "phone": None,
            "headquarters": None,
            "founded": None,
            "industry": None,
            "company_type": None,
            "company_size": None,
            "specialties": None
        }
        
        try:
            # Look for the overview section with company details
            # LinkedIn shows these in a dl (definition list) format
            dt_elements = await self.page.locator('dt').all()
            
            for dt in dt_elements:
                label = await dt.inner_text()
                label = label.strip().lower()
                
                # Get the corresponding dd (value)
                dd = dt.locator('xpath=following-sibling::dd[1]')
                value = await dd.inner_text() if await dd.count() > 0 else None
                
                if value:
                    value = value.strip()
                
                # Map labels to fields
                if 'website' in label:
                    overview['website'] = value
                elif 'phone' in label:
                    overview['phone'] = value
                elif 'headquarters' in label or 'location' in label:
                    overview['headquarters'] = value
                elif 'founded' in label:
                    overview['founded'] = value
                elif 'industry' in label or 'industries' in label:
                    overview['industry'] = value
                elif 'company type' in label or 'type' in label:
                    overview['company_type'] = value
                elif 'company size' in label or 'size' in label:
                    overview['company_size'] = value
                elif 'specialt' in label:  # specialties/specialty
                    overview['specialties'] = value
            
        except Exception as e:
            logger.debug(f"Error getting company overview: {e}")
        
        return overview
