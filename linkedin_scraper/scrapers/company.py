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
        
        # The About tab holds the overview fields (website, size, etc.).
        about_url = self._build_about_url(linkedin_url)
        await self.navigate_and_wait(about_url)
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
    
    def _build_about_url(self, company_url: str) -> str:
        """Build the About tab URL for a company page."""
        base = company_url.rstrip("/")
        for suffix in ("/about", "/home", "/posts", "/jobs", "/life", "/people"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        return f"{base}/about/"

    async def _get_name(self) -> str:
        """Extract company name."""
        try:
            name = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                const el = main ? main.querySelector('h1, h2') : null;
                return el ? el.innerText.trim() : null;
            }""")
            if name:
                return name
        except Exception as e:
            logger.warning(f"Error getting company name: {e}")

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
            about = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return null;

                let scope = main;
                const overview = [...main.querySelectorAll('h2')]
                    .find(h => h.innerText.trim() === 'Overview');
                if (overview) {
                    let el = overview;
                    for (let i = 0; i < 5 && el; i++) {
                        const longP = [...el.querySelectorAll('p')]
                            .find(p => p.innerText.trim().length > 120);
                        if (longP) { scope = el; break; }
                        el = el.parentElement;
                    }
                }

                let best = null;
                for (const p of scope.querySelectorAll('p')) {
                    const t = p.innerText.trim();
                    if (t.length > 120 && (!best || t.length > best.length)) {
                        best = t;
                    }
                }
                return best;
            }""")
            if about:
                return about.strip()
        except Exception as e:
            logger.debug(f"Error getting about section: {e}")

        # Fallback: legacy "About us" section
        try:
            sections = await self.page.locator('section').all()
            for section in sections:
                section_text = await section.inner_text()
                if 'About us' in section_text[:50]:
                    paragraphs = await section.locator('p').all()
                    if paragraphs:
                        about = await paragraphs[0].inner_text()
                        return about.strip()
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
            # Current LinkedIn About tab: label/value pairs rendered as <p>.
            data = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return {};
                const labels = {
                    'Website': 'website',
                    'Industry': 'industry',
                    'Company size': 'company_size',
                    'Headquarters': 'headquarters',
                    'Type': 'company_type',
                    'Founded': 'founded',
                    'Specialties': 'specialties',
                    'Phone': 'phone'
                };
                const out = {};
                for (const p of main.querySelectorAll('p')) {
                    const label = (p.innerText || '').trim();
                    const key = labels[label];
                    if (!key || out[key]) continue;
                    const row = p.parentElement ? p.parentElement.parentElement : null;
                    if (!row) continue;
                    const valueDiv = row.children[1];
                    if (!valueDiv) continue;
                    const value = (valueDiv.innerText || '').trim();
                    if (value) out[key] = value.split('\\n')[0].trim();
                }
                return out;
            }""")

            for key, value in (data or {}).items():
                if key in overview:
                    overview[key] = value

            # Try to find website link if the label parsing missed it
            # LinkedIn often puts website in the about section or as a link
            if not overview.get("website"):
                try:
                    links = await self.page.locator('main a').all()
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and 'linkedin' not in href and ('http' in href or 'www.' in href):
                            link_text = await link.inner_text()
                            # Skip navigation links, look for actual website URLs
                            if link_text and any(word in link_text.lower() for word in ['learn more', 'website', 'visit']):
                                overview['website'] = href
                                break
                except Exception as e:
                    logger.debug(f"Error finding website: {e}")

            # Fallback: Try old dt/dd structure (for backwards compatibility)
            if not any(overview.values()):
                dt_elements = await self.page.locator('dt').all()
                
                for dt in dt_elements:
                    label = await dt.inner_text()
                    label = label.strip().lower()
                    
                    dd = dt.locator('xpath=following-sibling::dd[1]')
                    value = await dd.inner_text() if await dd.count() > 0 else None
                    
                    if value:
                        value = value.strip()
                        
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
                        elif 'specialt' in label:
                            overview['specialties'] = value
            
        except Exception as e:
            logger.debug(f"Error getting company overview: {e}")
        
        return overview
