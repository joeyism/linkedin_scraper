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

        # Normalize the URL and construct /about URL for more details
        base_url = linkedin_url.rstrip('/')
        if '/about' in base_url:
            about_url = base_url
            base_url = base_url.replace('/about', '')
        else:
            about_url = f"{base_url}/about/"

        # Navigate to the /about page first (has more detailed info)
        await self.navigate_and_wait(about_url)
        await self.callback.on_progress("Navigated to company about page", 10)

        # Check if page exists
        await self.check_rate_limit()

        # Extract basic info
        name = await self._get_name()
        await self.callback.on_progress(f"Got company name: {name}", 20)

        about_us = await self._get_about()
        await self.callback.on_progress("Got about section", 30)

        # Extract overview details from /about page
        overview = await self._get_overview()
        await self.callback.on_progress("Got overview details", 50)

        # Create company object
        company = Company(
            linkedin_url=base_url,  # Return the canonical URL without /about
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
            # Try the about module description on the /about page
            # Selector: section.org-about-module__margin-bottom > p.break-words
            about_selector = 'section.org-about-module__margin-bottom p.break-words'
            about_elem = self.page.locator(about_selector).first
            if await about_elem.count() > 0:
                about = await about_elem.inner_text()
                return about.strip()

            # Fallback: Try the about module description class directly
            about_elem = self.page.locator('.org-about-module__description p, .organization-about-module__content-consistant-cards-description').first
            if await about_elem.count() > 0:
                about = await about_elem.inner_text()
                return about.strip()

            # Last resort: Look for any section with description-like paragraph
            sections = await self.page.locator('section').all()
            for section in sections:
                paragraphs = await section.locator('p.break-words, p.text-body-medium').all()
                if paragraphs:
                    about = await paragraphs[0].inner_text()
                    if len(about) > 50:  # Only accept meaningful descriptions
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
            # Primary approach: Parse dl.overflow-hidden with dt/dd pairs on /about page
            # The dt contains labels (localized), dd contains values
            # We infer field types from value patterns since labels are localized
            await self._parse_dl_definition_list(overview)

            # Secondary approach: Parse top card info items on main page
            if not any([overview['industry'], overview['company_size']]):
                await self._parse_top_card_info(overview)

            # Try to find website from links if not found
            if not overview['website']:
                await self._find_website_link(overview)

        except Exception as e:
            logger.debug(f"Error getting company overview: {e}")

        return overview

    async def _parse_dl_definition_list(self, overview: dict) -> None:
        """Parse the dl.overflow-hidden definition list structure on /about pages."""
        try:
            # Get all dt elements within the overflow-hidden dl
            dt_elements = await self.page.locator('dl.overflow-hidden dt').all()

            for dt in dt_elements:
                try:
                    # Get the following dd sibling
                    dd = dt.locator('xpath=following-sibling::dd[1]')
                    if await dd.count() == 0:
                        continue

                    value = await dd.inner_text()
                    value = value.strip()
                    if not value:
                        continue

                    # Also get the label for pattern matching
                    label = await dt.inner_text()
                    label = label.strip().lower()

                    # Infer field type from value patterns and label keywords
                    # Website: contains http/https or common domain patterns
                    if ('http' in value.lower() or 'www.' in value.lower() or
                        '.com' in value.lower() or '.io' in value.lower() or '.org' in value.lower()):
                        if not overview['website']:
                            # Try to extract actual URL from link
                            link = dd.locator('a').first
                            if await link.count() > 0:
                                href = await link.get_attribute('href')
                                overview['website'] = href or value
                            else:
                                overview['website'] = value

                    # Company size: contains employee count patterns
                    elif any(pattern in value.lower() for pattern in ['employee', '직원', '명', 'k+', ',000']):
                        if not overview['company_size']:
                            # Clean up the size value (remove "X members" part)
                            size_lines = value.split('\n')
                            overview['company_size'] = size_lines[0].strip()

                    # Founded: typically a year (4 digits)
                    elif value.isdigit() and len(value) == 4:
                        if not overview['founded']:
                            overview['founded'] = value

                    # Headquarters: contains location patterns (city, state/country)
                    elif (',' in value and len(value) < 100) or any(loc in value for loc in
                        ['Washington', 'California', 'New York', 'Texas', 'London', 'Tokyo', 'Singapore',
                         'San Francisco', 'Seattle', 'Boston', 'Austin', 'Berlin', 'Paris']):
                        if not overview['headquarters']:
                            overview['headquarters'] = value

                    # Phone: contains phone number patterns
                    elif any(c.isdigit() for c in value) and any(c in value for c in ['+', '-', '(', ')']):
                        phone_digits = sum(c.isdigit() for c in value)
                        if phone_digits >= 7 and phone_digits <= 15:
                            if not overview['phone']:
                                overview['phone'] = value

                    # Industry: Use label-based detection since industry values vary widely
                    # Common industry label keywords across languages
                    elif any(kw in label for kw in ['industry', 'industries', '업계', '산업', '業界', 'industrie', 'branche']):
                        if not overview['industry']:
                            overview['industry'] = value

                    # Company type: Use label-based detection
                    elif any(kw in label for kw in ['type', '유형', 'タイプ', 'typ']):
                        if not overview['company_type']:
                            overview['company_type'] = value

                    # Specialties: Use label-based detection
                    elif any(kw in label for kw in ['special', '전문', '専門', 'spécial']):
                        if not overview['specialties']:
                            overview['specialties'] = value

                except Exception as e:
                    logger.debug(f"Error parsing dt/dd pair: {e}")
                    continue

        except Exception as e:
            logger.debug(f"Error parsing definition list: {e}")

    async def _parse_top_card_info(self, overview: dict) -> None:
        """Parse the top card info items on the main company page."""
        try:
            info_items = await self.page.locator('.org-top-card-summary-info-list__info-item').all()

            for item in info_items:
                text = await item.inner_text()
                text = text.strip()
                text_lower = text.lower()

                # Skip follower counts
                if 'follower' in text_lower or '팔로워' in text or 'フォロワー' in text:
                    continue

                # Company size: employee count patterns
                if any(pattern in text_lower for pattern in ['employee', '직원', '명', 'k+', ',000']):
                    if not overview['company_size']:
                        overview['company_size'] = text

                # Industry: If not size/follower, likely industry
                elif not overview['industry'] and len(text) < 100:
                    # Check if it looks like an industry (not a number, not too short)
                    if len(text) > 3 and not text.isdigit():
                        overview['industry'] = text

        except Exception as e:
            logger.debug(f"Error parsing top card info: {e}")

    async def _find_website_link(self, overview: dict) -> None:
        """Find the company website link."""
        try:
            # Look for website link in the dl definition list first
            website_links = await self.page.locator('dl.overflow-hidden dd a[href*="http"]').all()
            for link in website_links:
                href = await link.get_attribute('href')
                if href and 'linkedin' not in href.lower():
                    overview['website'] = href
                    return

            # Fallback: Look for external links in the about section
            about_links = await self.page.locator('section.org-about-module__margin-bottom a[href*="http"]').all()
            for link in about_links:
                href = await link.get_attribute('href')
                if href and 'linkedin' not in href.lower():
                    overview['website'] = href
                    return

        except Exception as e:
            logger.debug(f"Error finding website link: {e}")
