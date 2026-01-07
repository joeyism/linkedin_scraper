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
            # LinkedIn's new structure (as of 2024+): Uses info items instead of dt/dd
            info_items = await self.page.locator('.org-top-card-summary-info-list__info-item').all()
            
            for item in info_items:
                text = await item.inner_text()
                text = text.strip()
                text_lower = text.lower()
                
                # Detect what kind of information this is based on content patterns
                if 'employee' in text_lower or 'k+' in text_lower:
                    # Company size (e.g., "10K+ employees", "1,001-5,000 employees")
                    overview['company_size'] = text
                elif ',' in text and any(loc in text for loc in ['Washington', 'California', 'New York', 'Texas', 'United States', 'United Kingdom']):
                    # Headquarters (e.g., "Redmond, Washington", "Mountain View, California")
                    overview['headquarters'] = text
                elif any(ind in text_lower for ind in ['software', 'technology', 'financial', 'healthcare', 'retail', 'manufacturing', 'consulting', 'education']):
                    # Industry (e.g., "Software Development", "Financial Services")
                    overview['industry'] = text
                elif 'follower' in text_lower:
                    # Skip follower count
                    continue
            
            # Try to find website link
            # LinkedIn often puts website in the about section or as a link
            try:
                links = await self.page.locator('a').all()
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
