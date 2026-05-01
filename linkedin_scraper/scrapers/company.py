"""
Company scraper for LinkedIn.

Extracts company information from LinkedIn company pages.
"""
import logging
from typing import Optional
from playwright.async_api import Page

from ..models.company import Company
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
        
        # Extract overview details (navigates to About tab)
        overview = await self._get_overview(linkedin_url)
        await self.callback.on_progress("Got overview details", 50)

        # Create company object
        company = Company(
            linkedin_url=linkedin_url,
            name=name,
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
    
    async def _get_overview(self, linkedin_url: str) -> dict:
        """
        Navigate to the About tab and extract all company information.

        Returns dict with: about_us, website, phone, headquarters, founded,
        industry, company_type, company_size, specialties
        """
        overview = {
            "about_us": None,
            "website": None,
            "phone": None,
            "headquarters": None,
            "founded": None,
            "industry": None,
            "company_type": None,
            "company_size": None,
            "specialties": None,
        }

        label_map = {
            "website": "website",
            "phone": "phone",
            "headquarters": "headquarters",
            "founded": "founded",
            "industry": "industry",
            "industries": "industry",
            "company type": "company_type",
            "type": "company_type",
            "company size": "company_size",
            "size": "company_size",
            "specialties": "specialties",
            "specialty": "specialties",
        }

        try:
            about_url = linkedin_url.rstrip("/") + "/about"
            await self.navigate_and_wait(about_url)

            about = self.page.locator("section").filter(
                has=self.page.get_by_role("heading", name="Overview")
            )

            try:
                overview["about_us"] = (await about.locator("p").first.inner_text()).strip()
            except Exception as e:
                logger.debug(f"Error getting overview text: {e}")

            labels = await about.locator("dt").all()
            for dt in labels:
                key = (await dt.inner_text()).strip().lower()
                dd = dt.locator("xpath=following-sibling::dd[1]")
                if await dd.count() > 0:
                    value = (await dd.inner_text()).strip()
                    field = label_map.get(key)
                    if field:
                        overview[field] = value

        except Exception as e:
            logger.debug(f"Error getting company overview: {e}")

        return overview
