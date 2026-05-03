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

        fields = await self._scrape_about(linkedin_url)
        await self.callback.on_progress("Scraped About page", 80)

        company = Company(linkedin_url=linkedin_url, **fields)

        await self.callback.on_progress("Scraping complete", 100)
        await self.callback.on_complete("company", company)

        logger.info(f"Successfully scraped company: {company.name}")
        return company

    async def _scrape_about(self, linkedin_url: str) -> dict:
        """
        Navigate to the About tab and extract company name and all overview fields.

        Returns dict with: name, about_us, website, phone, headquarters, founded,
        industry, company_type, company_size, specialties
        """
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

        result = {field: None for field in ["name", "about_us"] + list(set(label_map.values()))}

        try:
            about_url = linkedin_url.rstrip("/") + "/about"
            await self.navigate_and_wait(about_url)
            await self.check_rate_limit()

            try:
                result["name"] = (await self.page.locator("h1").first.inner_text()).strip()
            except Exception as e:
                logger.warning(f"Error getting company name: {e}")
                result["name"] = "Unknown Company"

            about = self.page.locator("section").filter(
                has=self.page.get_by_role("heading", name="Overview")
            )

            try:
                result["about_us"] = (await about.locator("p").first.inner_text()).strip()
            except Exception as e:
                logger.debug(f"Error getting overview text: {e}")

            for dt in await about.locator("dt").all():
                key = (await dt.inner_text()).strip().lower()
                dd = dt.locator("xpath=following-sibling::dd[1]")
                if await dd.count() > 0:
                    field = label_map.get(key)
                    if field:
                        result[field] = (await dd.inner_text()).strip()

        except Exception as e:
            logger.debug(f"Error scraping About page: {e}")

        return result
