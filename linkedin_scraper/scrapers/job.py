"""
Job scraper for LinkedIn.

Extracts job posting information from LinkedIn job pages.
Uses robust content-based extraction compatible with LinkedIn's
dynamic React rendering (randomized class names).
"""
import logging
import re
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
        super().__init__(page, callback or SilentCallback())

    async def scrape(self, linkedin_url: str) -> Job:
        logger.info(f"Starting job scraping: {linkedin_url}")
        await self.callback.on_start("Job", linkedin_url)

        await self.navigate_and_wait(linkedin_url)
        await self.callback.on_progress("Navigated to job page", 10)

        await self.check_rate_limit()

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

        job = Job(
            linkedin_url=linkedin_url,
            job_title=job_title,
            company=company,
            company_linkedin_url=company_url,
            location=location,
            posted_date=posted_date,
            applicant_count=applicant_count,
            job_description=job_description,
        )

        await self.callback.on_progress("Scraping complete", 100)
        await self.callback.on_complete("Job", job)

        logger.info(f"Successfully scraped job: {job_title}")
        return job

    async def _get_header_text(self) -> Optional[str]:
        """Get the full text of the job header block from the first <main> column."""
        try:
            return await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return null;
                const firstCol = main.querySelector(':scope > div');
                if (!firstCol) return null;
                return firstCol.innerText;
            }""")
        except Exception as e:
            logger.debug(f"Error getting header text: {e}")
            return None

    def _clean(self, text: str) -> str:
        """Remove Unicode formatting characters and normalize whitespace."""
        text = text.replace('\u200e', '').replace('\u200f', '')
        text = text.replace('\u2066', '').replace('\u2067', '').replace('\u2068', '').replace('\u2069', '')
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    async def _get_job_title(self) -> Optional[str]:
        """Extract job title from document.title (most reliable across locales)."""
        try:
            title = await self.page.evaluate("document.title")
            if title:
                title = self._clean(title)
                # "Job Title | Company | LinkedIn"
                parts = title.split('|')
                if parts:
                    return parts[0].strip()
        except:
            pass
        try:
            title_elem = self.page.locator('h1').first
            await title_elem.wait_for(timeout=3000)
            title = await title_elem.inner_text()
            return self._clean(title)
        except:
            pass
        return None

    async def _get_company(self) -> Optional[str]:
        try:
            company_links = await self.page.locator('a[href*="/company/"]').all()
            for link in company_links:
                text = await link.inner_text()
                text = self._clean(text)
                if text and len(text) > 1 and not text.startswith('logo'):
                    return text
        except:
            pass
        return None

    async def _get_company_url(self) -> Optional[str]:
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

    async def _get_metadata_parts(self) -> list[str]:
        """
        Parse the metadata line (Location · Date · Applicants) from the header block.
        Returns a list of up to 3 parts.
        """
        try:
            text = await self._get_header_text()
            if not text:
                return []

            lines = text.split('\n')
            for line in lines:
                line = self._clean(line)
                if '·' in line:
                    parts = [p.strip() for p in line.split('·')]
                    if 2 <= len(parts) <= 4:
                        return parts
        except:
            pass
        return []

    async def _get_location(self) -> Optional[str]:
        parts = await self._get_metadata_parts()
        if parts:
            return parts[0]
        return None

    async def _get_posted_date(self) -> Optional[str]:
        parts = await self._get_metadata_parts()
        if len(parts) > 1:
            date_text = parts[1]
            date_text = date_text.replace('\u0660', '0').replace('\u0661', '1').replace('\u0662', '2').replace('\u0663', '3').replace('\u0664', '4').replace('\u0665', '5').replace('\u0666', '6').replace('\u0667', '7').replace('\u0668', '8').replace('\u0669', '9')
            return date_text
        return None

    async def _get_applicant_count(self) -> Optional[str]:
        parts = await self._get_metadata_parts()
        if len(parts) > 2:
            return parts[2]
        return None

    async def _get_description(self) -> Optional[str]:
        """
        Extract job description. Tries multiple strategies:
        1. Content after an h2 containing "About" (multi-locale)
        2. Element with data-testid="expandable-text-box"
        3. All text from <main> after stripping known header metadata
        """
        await self.wait_and_focus(2)
        try:
            desc = await self._get_description_via_heading()
            if desc:
                logger.debug(f"Description from heading strategy ({len(desc)} chars)")
                return desc
        except Exception as e:
            logger.debug(f"Heading strategy failed: {e}")
        try:
            desc = await self._get_description_via_testid()
            if desc:
                logger.debug(f"Description from testid strategy ({len(desc)} chars)")
                return desc
        except Exception as e:
            logger.debug(f"Testid strategy failed: {e}")
        try:
            desc = await self._get_description_via_main()
            if desc:
                logger.debug(f"Description from main strategy ({len(desc)} chars)")
                return desc
        except Exception as e:
            logger.debug(f"Main strategy failed: {e}")
        return None

    async def _get_description_via_heading(self) -> Optional[str]:
        """Find an h2 with about-related text, return the section content after the heading."""
        return await self.page.evaluate("""() => {
            const headings = document.querySelectorAll('h2');
            for (const h2 of headings) {
                const text = h2.innerText.toLowerCase().trim();
                if (text.includes('about') || text.includes('لمحة') || text.includes('описание') || text.includes('描述') || text.includes('à propos') || text.includes('über')) {
                    const headingText = h2.innerText.trim();
                    const pageText = document.body.innerText;
                    const idx = pageText.indexOf(headingText);
                    if (idx === -1) continue;
                    const after = pageText.substring(idx + headingText.length).trim();
                    const lines = after.split('\\n').filter(l => l.trim());
                    const filtered = [];
                    for (const line of lines) {
                        const clean = line.trim();
                        if (!clean || clean.length < 5) continue;
                        if (/^(تطبيق|حفظ|نشر|عرض ترتيبك|قم بالوصول|تجربة Premium|هل تبحث|إمكانية|حلول|سياسة|إرشادات|المهن|خصوصية|خيارات|جوال|أعمال|مركز|شركة|لديك|إدارة|شفافية|تحديد|اللغة|English|Français|Deutsch|Español|العربية|বাংলা|Čeština|Dansk|Ελληνικά|Suomi|हिंदी|Magyar|Indonesia|Italiano|日本語|한국어|Nederlands|Norsk|Polski|Português|Română|Русский|Svenska|Tagalog|Türkçe|Українська|Tiếng)/i.test(clean)) continue;
                        if (clean.includes('LinkedIn') && clean.length < 30) continue;
                        filtered.push(clean);
                    }
                    if (filtered.length) return filtered.join('\\n\\n');
                }
            }
            return null;
        }""")

    async def _get_description_via_testid(self) -> Optional[str]:
        try:
            box = self.page.locator('[data-testid="expandable-text-box"]').first
            if await box.count() > 0:
                return self._clean(await box.inner_text())
        except:
            pass
        return None

    async def _get_description_via_main(self) -> Optional[str]:
        """Fallback: grab text from <main> after filtering out header/UI noise."""
        return await self.page.evaluate("""() => {
            const main = document.querySelector('main');
            if (!main) return null;
            const allText = main.innerText;
            const lines = allText.split('\\n').filter(l => l.trim());
            const seen = new Set();
            const filtered = [];
            for (const line of lines) {
                const clean = line.trim();
                if (!clean || clean.length < 5) continue;
                const key = clean.substring(0, 30);
                if (seen.has(key)) continue;
                seen.add(key);
                filtered.push(clean);
            }
            return filtered.join('\\n\\n');
        }""")
