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
        self._job_card: Optional[dict] = None

    async def _get_job_card(self) -> dict:
        """Extract the structured data from the job top card."""
        if self._job_card is not None:
            return self._job_card

        # The top card hydrates after domcontentloaded; wait until the company,
        # the details line (location · date · applicants) and a distinct title
        # are all present inside the same card.
        try:
            await self.page.wait_for_function("""() => {
                const main = document.querySelector('main');
                if (!main) return false;
                const companyA = main.querySelector('a[aria-label^="Company,"]') ||
                    [...main.querySelectorAll('a[href*="/company/"]')].find(a => (a.innerText || '').trim());
                if (!companyA) return false;
                const ps = [...main.querySelectorAll('p')];
                const detailsP = ps.find(p => /\\bago\\b|clicked apply|applicants?/i.test(p.innerText || ''));
                if (!detailsP) return false;

                const titleParts = (document.title || '').split('|').map(s => s.trim());
                if (titleParts.length >= 3 && /linkedin/i.test(titleParts[titleParts.length - 1])) {
                    return true;
                }

                let top = detailsP;
                for (let i = 0; i < 8 && top && !top.contains(companyA); i++) {
                    top = top.parentElement;
                }
                if (!top || !top.contains(companyA)) return false;

                for (const p of top.querySelectorAll('p')) {
                    if (p === detailsP || companyA.contains(p)) continue;
                    const t = (p.innerText || '').trim();
                    if (!t || t.startsWith('\\u00b7')) continue;
                    if (/^Promoted by|^Responses managed/i.test(t)) continue;
                    if (t.length < 2 || t.length > 200) continue;
                    return true;
                }
                return false;
            }""", timeout=15000)
        except Exception as e:
            logger.debug(f"Job top card wait timed out: {e}")

        try:
            self._job_card = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return {};

                // document.title is "{job title} | {company} | LinkedIn" and is
                // set by the document itself, so it is not subject to the
                // partial-hydration races of the top card DOM.
                let docTitle = null;
                let docTitleCompany = null;
                const titleParts = (document.title || '').split('|').map(s => s.trim());
                if (titleParts.length >= 3 && /linkedin/i.test(titleParts[titleParts.length - 1])) {
                    docTitle = titleParts[0].replace(/^\\(\\d+\\)\\s*/, '');
                    docTitleCompany = titleParts[1];
                }

                let companyA = main.querySelector('a[aria-label^="Company,"]');
                if (!companyA) {
                    companyA = [...main.querySelectorAll('a[href*="/company/"]')]
                        .find(a => (a.innerText || '').trim()) || null;
                }

                const company = docTitleCompany || (companyA ? companyA.innerText.trim().split('\\n')[0].trim() : null);
                let companyUrl = companyA ? companyA.getAttribute('href') : null;
                if (companyUrl) {
                    companyUrl = companyUrl.replace(/\\/(life|posts|jobs|about|home)\\/?$/, '/');
                }

                const allPs = [...main.querySelectorAll('p')];
                let detailsP = allPs.find(p => /\\bago\\b|clicked apply|applicants?/i.test(p.innerText || '')) || null;
                if (!detailsP) {
                    detailsP = allPs.find(p => ((p.innerText || '').match(/\\u00b7/g) || []).length >= 2) || null;
                }

                // Top card = nearest ancestor of the details line containing the
                // company link. This avoids pulling in the "About the company"
                // section when the title has not rendered yet.
                let top = detailsP;
                if (detailsP && companyA) {
                    for (let i = 0; i < 8 && top && !top.contains(companyA); i++) {
                        top = top.parentElement;
                    }
                }
                if (!top || !companyA || !top.contains(companyA)) {
                    top = companyA;
                    for (let i = 0; i < 6 && top; i++) {
                        if (top.querySelectorAll('p').length >= 3) break;
                        top = top.parentElement;
                    }
                }

                const ps = top ? [...top.querySelectorAll('p')] : [];
                let title = null;
                for (const p of ps) {
                    if (p === detailsP) continue;
                    if (companyA && companyA.contains(p)) continue;
                    const t = (p.innerText || '').trim();
                    if (!t || t.startsWith('\\u00b7')) continue;
                    if (/^Promoted by|^Responses managed/i.test(t)) continue;
                    if (t.length < 2 || t.length > 200) continue;
                    title = t;
                    break;
                }

                let location = null, postedDate = null, applicants = null;
                if (detailsP) {
                    const parts = detailsP.innerText.split('\\u00b7').map(s => s.trim()).filter(Boolean);
                    location = parts[0] || null;
                    postedDate = parts[1] || null;
                    applicants = parts[2] || null;
                }

                return {company, companyUrl, title: docTitle || title, location, postedDate, applicants};
            }""") or {}
        except Exception as e:
            logger.debug(f"Error extracting job top card: {e}")
            self._job_card = {}

        return self._job_card
    
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

        # Reset per-page cache so reuse across multiple job URLs is safe.
        self._job_card = None
        
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
        """Extract job title from the top card."""
        card = await self._get_job_card()
        if card.get("title"):
            return card["title"]

        # Fallback to legacy h1 heading
        try:
            title_elem = self.page.locator('h1').first
            await title_elem.wait_for(timeout=5000)
            title = await title_elem.inner_text()
            return title.strip()
        except:
            return None

    async def _get_company(self) -> Optional[str]:
        """Extract company name from the top card."""
        card = await self._get_job_card()
        if card.get("company"):
            return card["company"]

        try:
            # Find company links that have text (not just images)
            company_links = await self.page.locator('a[href*="/company/"]').all()
            for link in company_links:
                text = await link.inner_text()
                text = text.strip()
                # Skip empty or very short text (likely image-only links)
                if text and len(text) > 1 and not text.startswith('logo'):
                    return text
        except:
            pass
        return None

    async def _get_company_url(self) -> Optional[str]:
        """Extract company LinkedIn URL."""
        card = await self._get_job_card()
        if card.get("companyUrl"):
            return card["companyUrl"]

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
        except:
            pass
        return None

    async def _get_location(self) -> Optional[str]:
        """Extract job location from the top card."""
        card = await self._get_job_card()
        if card.get("location"):
            return card["location"]

        try:
            container = self.page.locator('.job-details-jobs-unified-top-card__primary-description-container').first
            if await container.count() > 0:
                text = await container.inner_text()
                parts = text.split('·')
                if parts:
                    return parts[0].strip().split('\n')[0].strip()
        except:
            pass
        return None

    async def _get_posted_date(self) -> Optional[str]:
        """Extract posted date from the top card."""
        card = await self._get_job_card()
        if card.get("postedDate"):
            return card["postedDate"]

        try:
            container = self.page.locator('.job-details-jobs-unified-top-card__primary-description-container').first
            if await container.count() > 0:
                text = await container.inner_text()
                parts = text.split('·')
                if len(parts) > 1:
                    return parts[1].strip().split('\n')[0].strip()
        except:
            pass
        return None

    async def _get_applicant_count(self) -> Optional[str]:
        """Extract applicant count from the top card."""
        card = await self._get_job_card()
        if card.get("applicants"):
            return card["applicants"]

        try:
            container = self.page.locator('.job-details-jobs-unified-top-card__primary-description-container').first
            if await container.count() > 0:
                text = await container.inner_text()
                parts = text.split('·')
                if len(parts) > 2:
                    return parts[2].strip().split('\n')[0].strip()
        except:
            pass
        return None

    async def _get_description(self) -> Optional[str]:
        """Extract job description from the About the job section."""
        try:
            await self.page.wait_for_function("""() => {
                const main = document.querySelector('main');
                if (!main) return false;
                return [...main.querySelectorAll('h2')]
                    .some(h => /about the job/i.test(h.innerText || ''));
            }""", timeout=15000)
        except Exception as e:
            logger.debug(f"About-the-job heading wait timed out: {e}")

        try:
            description = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return null;
                const heading = [...main.querySelectorAll('h2')]
                    .find(h => /about the job/i.test(h.innerText || ''));
                if (!heading) return null;

                let el = heading;
                for (let i = 0; i < 8 && el; i++) {
                    const box = el.querySelector('[data-testid="expandable-text-box"]');
                    if (box && box.innerText.trim()) return box.innerText.trim();
                    el = el.parentElement;
                }
                return null;
            }""")
            if description:
                return description
        except Exception as e:
            logger.debug(f"Error getting job description: {e}")

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
        except:
            pass
        return None
