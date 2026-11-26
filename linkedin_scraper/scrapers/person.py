"""Person/Profile scraper for LinkedIn."""

import logging
import re
from typing import Optional
from urllib.parse import urljoin
from playwright.async_api import Page

from .base import BaseScraper
from ..models import Person, Experience, Education, Accomplishment, Interest, Contact
from ..callbacks import ProgressCallback, SilentCallback
from ..core.exceptions import ScrapingError

logger = logging.getLogger(__name__)


class PersonScraper(BaseScraper):
    """Async scraper for LinkedIn person profiles."""

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize person scraper.

        Args:
            page: Playwright page object
            callback: Progress callback
        """
        super().__init__(page, callback)

    async def scrape(self, linkedin_url: str) -> Person:
        """
        Scrape a LinkedIn person profile.

        Args:
            linkedin_url: LinkedIn profile URL

        Returns:
            Person object with all scraped data

        Raises:
            AuthenticationError: If not logged in
            ScrapingError: If scraping fails
        """
        await self.callback.on_start("person", linkedin_url)

        try:
            # Navigate to profile first (this loads the page with our session)
            await self.navigate_and_wait(linkedin_url)
            await self.callback.on_progress("Navigated to profile", 10)

            # Now check if logged in
            await self.ensure_logged_in()

            # Wait for main content
            await self.page.wait_for_selector("main", timeout=10000)
            await self.wait_and_focus(1)

            # Get name and location
            name, location = await self._get_name_and_location()
            await self.callback.on_progress(f"Got name: {name}", 20)

            # Check open to work
            open_to_work = await self._check_open_to_work()

            # Get about
            about = await self._get_about()
            await self.callback.on_progress("Got about section", 30)

            # Scroll to load content
            await self.scroll_page_to_half()
            await self.scroll_page_to_bottom(pause_time=0.5, max_scrolls=3)

            # Get experiences
            experiences = await self._get_experiences(linkedin_url)
            await self.callback.on_progress(f"Got {len(experiences)} experiences", 60)

            educations = await self._get_educations(linkedin_url)
            await self.callback.on_progress(f"Got {len(educations)} educations", 50)

            interests = await self._get_interests(linkedin_url)
            await self.callback.on_progress(f"Got {len(interests)} interests", 65)

            accomplishments = await self._get_accomplishments(linkedin_url)
            await self.callback.on_progress(
                f"Got {len(accomplishments)} accomplishments", 85
            )

            contacts = await self._get_contacts(linkedin_url)
            await self.callback.on_progress(f"Got {len(contacts)} contacts", 95)

            person = Person(
                linkedin_url=linkedin_url,
                name=name,
                location=location,
                about=about,
                open_to_work=open_to_work,
                experiences=experiences,
                educations=educations,
                interests=interests,
                accomplishments=accomplishments,
                contacts=contacts,
            )

            await self.callback.on_progress("Scraping complete", 100)
            await self.callback.on_complete("person", person)

            return person

        except Exception as e:
            await self.callback.on_error(e)
            raise ScrapingError(f"Failed to scrape person profile: {e}")

    async def _get_name_and_location(self) -> tuple[str, Optional[str]]:
        """Extract name and location from the profile top card."""
        try:
            data = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return null;

                const contact = main.querySelector('a[href*="/overlay/contact-info"]');
                let section = contact ? contact.closest('section') : null;
                if (!section) section = main.querySelector('section');

                const nameEl = section ? section.querySelector('h1, h2') : main.querySelector('h1, h2');
                const name = nameEl ? nameEl.innerText.trim() : '';

                let location = null;
                let headline = null;

                if (contact) {
                    const row = contact.closest('div');
                    if (row) {
                        for (const p of row.querySelectorAll('p')) {
                            const t = p.innerText.trim();
                            if (t && t !== '\\u00b7' && !/contact info/i.test(t)) {
                                location = t;
                                break;
                            }
                        }
                    }
                }

                if (nameEl && section) {
                    for (const p of section.querySelectorAll('p')) {
                        const t = p.innerText.trim();
                        if (!t || t.startsWith('\\u00b7')) continue;
                        const follows = nameEl.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING;
                        if (!follows) continue;
                        if (/contact info/i.test(t)) continue;
                        if (location && t === location) continue;
                        headline = t;
                        break;
                    }
                }

                return {name, location, headline};
            }""")
        except Exception as e:
            logger.warning(f"Error getting name/location: {e}")
            data = None

        if data and data.get("name"):
            return data["name"], data.get("location") or None

        # Fallback to legacy selectors
        try:
            name = await self.safe_extract_text("h1", default="Unknown")
            location = await self.safe_extract_text(
                ".text-body-small.inline.t-black--light.break-words", default=""
            )
            return name, location if location else None
        except Exception as e:
            logger.warning(f"Error getting name/location: {e}")
            return "Unknown", None

    async def _check_open_to_work(self) -> bool:
        """Check if profile has an open-to-work badge."""
        try:
            return await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return false;
                if ((main.innerText || '').includes('#OPEN_TO_WORK')) return true;
                return !!main.querySelector('img[alt*="open to work" i]');
            }""")
        except Exception:
            return False

    async def _get_about(self) -> Optional[str]:
        """Extract about section."""
        try:
            text = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return null;
                const headings = [...main.querySelectorAll('h2')];
                const about = headings.find(h => h.innerText.trim() === 'About');
                if (about) {
                    let el = about;
                    for (let i = 0; i < 4 && el; i++) {
                        const box = el.querySelector('[data-testid="expandable-text-box"]');
                        if (box && box.innerText.trim()) return box.innerText.trim();
                        el = el.parentElement;
                    }
                }
                const box = main.querySelector('[data-testid="expandable-text-box"]');
                return box ? box.innerText.trim() : null;
            }""")
            return text or None
        except Exception as e:
            logger.debug(f"Error getting about section: {e}")
            return None

    async def _get_experiences(self, base_url: str) -> list[Experience]:
        """Extract experiences from the dedicated experience details page."""
        experiences: list[Experience] = []

        try:
            exp_url = urljoin(base_url, "details/experience")
            await self.navigate_and_wait(exp_url)
            await self.page.wait_for_selector("main", timeout=10000)
            await self.wait_and_focus(1.5)
            await self.scroll_page_to_half()
            await self.scroll_page_to_bottom(pause_time=0.5, max_scrolls=5)

            items = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return [];
                const out = [];
                const seen = new Set();
                for (const a of main.querySelectorAll('a[href*="/company/"]')) {
                    if (!a.querySelector('p')) continue;
                    const href = a.getAttribute('href');
                    const texts = [...a.querySelectorAll('p')]
                        .map(p => p.innerText.trim())
                        .filter(Boolean);
                    if (texts.length < 2) continue;
                    const key = href + '|' + texts.join('|');
                    if (seen.has(key)) continue;
                    seen.add(key);
                    out.push({href, texts});
                }
                return out;
            }""")

            for item in items:
                texts = item.get("texts") or []
                if len(texts) < 2:
                    continue
                position_title = texts[0]
                institution_name = texts[1]
                work_times = texts[2] if len(texts) > 2 else ""
                location = texts[3] if len(texts) > 3 else None

                from_date, to_date, duration = self._parse_work_times(work_times)
                experiences.append(
                    Experience(
                        position_title=position_title,
                        institution_name=institution_name,
                        linkedin_url=item.get("href"),
                        from_date=from_date,
                        to_date=to_date,
                        duration=duration,
                        location=location,
                        description=None,
                    )
                )

        except Exception as e:
            logger.warning(
                f"Error getting experiences: {e}. "
                "The experience section may not be available or the page structure has changed."
            )

        return experiences

    
    async def _parse_main_page_experience(self, item) -> Optional[Experience]:
        """Parse experience from main profile page list item with [logo_link, details_link] structure."""
        try:
            links = await item.locator('a').all()
            if len(links) < 2:
                return None
            
            company_url = await links[0].get_attribute('href')
            detail_link = links[1]
            
            unique_texts = await self._extract_unique_texts_from_element(detail_link)
            
            if len(unique_texts) < 2:
                return None
            
            position_title = unique_texts[0]
            company_name = unique_texts[1]
            work_times = unique_texts[2] if len(unique_texts) > 2 else ""
            
            from_date, to_date, duration = self._parse_work_times(work_times)
            
            return Experience(
                position_title=position_title,
                institution_name=company_name,
                linkedin_url=company_url,
                from_date=from_date,
                to_date=to_date,
                duration=duration,
                location=None,
                description=None,
            )
            
        except Exception as e:
            logger.debug(f"Error parsing main page experience: {e}")
            return None
    
    async def _extract_unique_texts_from_element(self, element) -> list[str]:
        """Extract unique text content from nested elements, avoiding duplicates from parent/child overlap."""
        text_elements = await element.locator('span[aria-hidden="true"], div > span').all()
        
        if not text_elements:
            text_elements = await element.locator('span, div').all()
        
        seen_texts = set()
        unique_texts = []
        
        for el in text_elements:
            text = await el.text_content()
            if text and text.strip():
                text = text.strip()
                if text not in seen_texts and len(text) < 200 and not any(text in t or t in text for t in seen_texts if len(t) > 3):
                    seen_texts.add(text)
                    unique_texts.append(text)
        
        return unique_texts

    async def _parse_experience_item(self, item):
        """Parse experience item. Returns Experience or list for nested positions."""
        try:
            links = await item.locator('a, link').all()
            if len(links) >= 2:
                company_url = await links[0].get_attribute('href')
                detail_link = links[1]
                
                generics = await detail_link.locator('generic, span, div').all()
                texts = []
                for g in generics:
                    text = await g.text_content()
                    if text and text.strip() and len(text.strip()) < 200:
                        texts.append(text.strip())
                
                unique_texts = list(dict.fromkeys(texts))
                
                if len(unique_texts) >= 2:
                    position_title = unique_texts[0]
                    company_name = unique_texts[1]
                    work_times = unique_texts[2] if len(unique_texts) > 2 else ""
                    location = unique_texts[3] if len(unique_texts) > 3 else ""
                    
                    from_date, to_date, duration = self._parse_work_times(work_times)
                    
                    return Experience(
                        position_title=position_title,
                        institution_name=company_name,
                        linkedin_url=company_url,
                        from_date=from_date,
                        to_date=to_date,
                        duration=duration,
                        location=location,
                        description=None,
                    )
            
            entity = item.locator('div[data-view-name="profile-component-entity"]').first
            if await entity.count() == 0:
                return None

            children = await entity.locator("> *").all()
            if len(children) < 2:
                return None

            company_link = children[0].locator("a").first
            company_url = await company_link.get_attribute("href")

            detail_container = children[1]
            detail_children = await detail_container.locator("> *").all()

            if len(detail_children) == 0:
                return None

            has_nested_positions = False
            if len(detail_children) > 1:
                nested_list = await detail_children[1].locator(".pvs-list__container").count()
                has_nested_positions = nested_list > 0

            if has_nested_positions:
                return await self._parse_nested_experience(item, company_url, detail_children)
            else:
                first_detail = detail_children[0]
                nested_elements = await first_detail.locator("> *").all()

                if len(nested_elements) == 0:
                    return None

                span_container = nested_elements[0]
                outer_spans = await span_container.locator("> *").all()

                position_title = ""
                company_name = ""
                work_times = ""
                location = ""

                if len(outer_spans) >= 1:
                    aria_span = outer_spans[0].locator('span[aria-hidden="true"]').first
                    position_title = await aria_span.text_content()
                if len(outer_spans) >= 2:
                    aria_span = outer_spans[1].locator('span[aria-hidden="true"]').first
                    company_name = await aria_span.text_content()
                if len(outer_spans) >= 3:
                    aria_span = outer_spans[2].locator('span[aria-hidden="true"]').first
                    work_times = await aria_span.text_content()
                if len(outer_spans) >= 4:
                    aria_span = outer_spans[3].locator('span[aria-hidden="true"]').first
                    location = await aria_span.text_content()

                from_date, to_date, duration = self._parse_work_times(work_times)

                description = ""
                if len(detail_children) > 1:
                    description = await detail_children[1].inner_text()

                return Experience(
                    position_title=position_title.strip(),
                    institution_name=company_name.strip(),
                    linkedin_url=company_url,
                    from_date=from_date,
                    to_date=to_date,
                    duration=duration,
                    location=location.strip(),
                    description=description.strip() if description else None,
                )

        except Exception as e:
            logger.debug(f"Error parsing experience: {e}")
            return None

    async def _parse_nested_experience(
        self, item, company_url: str, detail_children
    ) -> list[Experience]:
        """
        Parse nested experience positions (multiple roles at the same company).
        Returns a list of Experience objects.
        """
        experiences = []

        try:
            # Get company name from first detail
            first_detail = detail_children[0]
            nested_elements = await first_detail.locator("> *").all()
            if len(nested_elements) == 0:
                return []

            span_container = nested_elements[0]
            outer_spans = await span_container.locator("> *").all()

            # First span is company name for nested positions
            company_name = ""
            if len(outer_spans) >= 1:
                aria_span = outer_spans[0].locator('span[aria-hidden="true"]').first
                company_name = await aria_span.text_content()

            # Get the nested list from detail_children[1]
            nested_container = detail_children[1].locator(".pvs-list__container").first
            nested_items = await nested_container.locator(
                ".pvs-list__paged-list-item"
            ).all()

            for nested_item in nested_items:
                try:
                    # Each nested item has a link with position details
                    link = nested_item.locator("a").first
                    link_children = await link.locator("> *").all()

                    if len(link_children) == 0:
                        continue

                    # Navigate to get the spans
                    first_child = link_children[0]
                    nested_els = await first_child.locator("> *").all()
                    if len(nested_els) == 0:
                        continue

                    spans_container = nested_els[0]
                    position_spans = await spans_container.locator("> *").all()

                    # Extract position details
                    position_title = ""
                    work_times = ""
                    location = ""

                    if len(position_spans) >= 1:
                        aria_span = (
                            position_spans[0].locator('span[aria-hidden="true"]').first
                        )
                        position_title = await aria_span.text_content()
                    if len(position_spans) >= 2:
                        aria_span = (
                            position_spans[1].locator('span[aria-hidden="true"]').first
                        )
                        work_times = await aria_span.text_content()
                    if len(position_spans) >= 3:
                        aria_span = (
                            position_spans[2].locator('span[aria-hidden="true"]').first
                        )
                        location = await aria_span.text_content()

                    # Parse dates
                    from_date, to_date, duration = self._parse_work_times(work_times)

                    # Get description if available
                    description = ""
                    if len(link_children) > 1:
                        description = await link_children[1].inner_text()

                    experiences.append(
                        Experience(
                            position_title=position_title.strip(),
                            institution_name=company_name.strip(),
                            linkedin_url=company_url,
                            from_date=from_date,
                            to_date=to_date,
                            duration=duration,
                            location=location.strip(),
                            description=description.strip() if description else None,
                        )
                    )

                except Exception as e:
                    logger.debug(f"Error parsing nested position: {e}")
                    continue

        except Exception as e:
            logger.debug(f"Error parsing nested experience: {e}")

        return experiences

    def _parse_work_times(
        self, work_times: str
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse work times string into from_date, to_date, duration.

        Examples:
        - "2000 - Present · 26 yrs 1 mo" -> ("2000", "Present", "26 yrs 1 mo")
        - "Jan 2020 - Dec 2022 · 2 yrs" -> ("Jan 2020", "Dec 2022", "2 yrs")
        - "2015 – Present" -> ("2015", "Present", None)
        """
        if not work_times:
            return None, None, None

        try:
            # Split by · to separate date range from duration
            parts = work_times.split("·")
            times = parts[0].strip() if len(parts) > 0 else ""
            duration = parts[1].strip() if len(parts) > 1 else None

            # Parse dates - split on hyphen or en/em dash
            match = re.split(r"\s*[-–—]\s*", times, maxsplit=1)
            from_date = match[0].strip()
            to_date = match[1].strip() if len(match) > 1 else ""

            return from_date, to_date, duration
        except Exception as e:
            logger.debug(f"Error parsing work times '{work_times}': {e}")
            return None, None, None


    async def _get_educations(self, base_url: str) -> list[Education]:
        """Extract educations from the dedicated education details page."""
        educations: list[Education] = []

        try:
            edu_url = urljoin(base_url, "details/education")
            await self.navigate_and_wait(edu_url)
            await self.page.wait_for_selector("main", timeout=10000)
            await self.wait_and_focus(2)
            await self.scroll_page_to_half()
            await self.scroll_page_to_bottom(pause_time=0.5, max_scrolls=5)

            items = await self.page.evaluate("""() => {
                const main = document.querySelector('main');
                if (!main) return [];
                const out = [];
                const seen = new Set();
                for (const a of main.querySelectorAll('a[href*="/school/"]')) {
                    if (!a.querySelector('p')) continue;
                    const href = a.getAttribute('href');
                    const texts = [...a.querySelectorAll('p')]
                        .map(p => p.innerText.trim())
                        .filter(Boolean);
                    if (!texts.length) continue;
                    const key = href + '|' + texts.join('|');
                    if (seen.has(key)) continue;
                    seen.add(key);
                    out.push({href, texts});
                }
                return out;
            }""")

            for item in items:
                texts = item.get("texts") or []
                if not texts:
                    continue
                institution_name = texts[0]
                degree = None
                times = ""
                if len(texts) >= 3:
                    degree = texts[1]
                    times = texts[2]
                elif len(texts) == 2:
                    second = texts[1]
                    if any(c.isdigit() for c in second) or "–" in second or "-" in second:
                        times = second
                    else:
                        degree = second

                from_date, to_date = self._parse_education_times(times)
                educations.append(
                    Education(
                        institution_name=institution_name,
                        degree=degree,
                        linkedin_url=item.get("href"),
                        from_date=from_date,
                        to_date=to_date,
                        description=None,
                    )
                )

        except Exception as e:
            logger.warning(
                f"Error getting educations: {e}. "
                "The education section may not be publicly visible or the page structure has changed."
            )

        return educations

    
    async def _parse_main_page_education(self, item) -> Optional[Education]:
        """Parse education from main profile page list item with [logo_link, details_link] structure."""
        try:
            links = await item.locator('a').all()
            if not links:
                return None
            
            institution_url = await links[0].get_attribute('href')
            detail_link = links[1] if len(links) > 1 else links[0]
            
            unique_texts = await self._extract_unique_texts_from_element(detail_link)
            
            if not unique_texts:
                return None
            
            institution_name = unique_texts[0]
            degree = None
            times = ""
            
            if len(unique_texts) == 3:
                degree = unique_texts[1]
                times = unique_texts[2]
            elif len(unique_texts) == 2:
                second = unique_texts[1]
                if " - " in second or any(c.isdigit() for c in second):
                    times = second
                else:
                    degree = second
            
            from_date, to_date = self._parse_education_times(times)
            
            return Education(
                institution_name=institution_name,
                degree=degree.strip() if degree else None,
                linkedin_url=institution_url,
                from_date=from_date,
                to_date=to_date,
                description=None,
            )
            
        except Exception as e:
            logger.debug(f"Error parsing main page education: {e}")
            return None

    async def _parse_education_item(self, item) -> Optional[Education]:
        """Parse a single education item."""
        try:
            links = await item.locator('a, link').all()
            if len(links) >= 1:
                institution_url = await links[0].get_attribute('href')
                
                detail_link = links[1] if len(links) >= 2 else links[0]
                generics = await detail_link.locator('generic, span, div').all()
                texts = []
                for g in generics:
                    text = await g.text_content()
                    if text and text.strip() and len(text.strip()) < 200:
                        texts.append(text.strip())
                
                unique_texts = list(dict.fromkeys(texts))
                
                if unique_texts:
                    institution_name = unique_texts[0]
                    degree = None
                    times = ""
                    
                    if len(unique_texts) == 3:
                        degree = unique_texts[1]
                        times = unique_texts[2]
                    elif len(unique_texts) == 2:
                        second = unique_texts[1]
                        if " - " in second or second.isdigit() or any(c.isdigit() for c in second):
                            times = second
                        else:
                            degree = second
                    
                    from_date, to_date = self._parse_education_times(times)
                    
                    return Education(
                        institution_name=institution_name,
                        degree=degree.strip() if degree else None,
                        linkedin_url=institution_url,
                        from_date=from_date,
                        to_date=to_date,
                        description=None,
                    )
            
            entity = item.locator('div[data-view-name="profile-component-entity"]').first
            if await entity.count() == 0:
                return None

            children = await entity.locator("> *").all()
            if len(children) < 2:
                return None

            institution_link = children[0].locator("a").first
            institution_url = await institution_link.get_attribute("href")

            detail_container = children[1]
            detail_children = await detail_container.locator("> *").all()

            if len(detail_children) == 0:
                return None

            first_detail = detail_children[0]
            nested_elements = await first_detail.locator("> *").all()

            if len(nested_elements) == 0:
                return None

            span_container = nested_elements[0]
            outer_spans = await span_container.locator("> *").all()

            institution_name = ""
            degree = None
            times = ""

            if len(outer_spans) >= 1:
                aria_span = outer_spans[0].locator('span[aria-hidden="true"]').first
                institution_name = await aria_span.text_content()

            if len(outer_spans) == 3:
                aria_span = outer_spans[1].locator('span[aria-hidden="true"]').first
                degree = await aria_span.text_content()
                aria_span = outer_spans[2].locator('span[aria-hidden="true"]').first
                times = await aria_span.text_content()
            elif len(outer_spans) == 2:
                aria_span = outer_spans[1].locator('span[aria-hidden="true"]').first
                times = await aria_span.text_content()

            from_date, to_date = self._parse_education_times(times)

            description = ""
            if len(detail_children) > 1:
                description = await detail_children[1].inner_text()

            return Education(
                institution_name=institution_name.strip(),
                degree=degree.strip() if degree else None,
                linkedin_url=institution_url,
                from_date=from_date,
                to_date=to_date,
                description=description.strip() if description else None,
            )

        except Exception as e:
            logger.debug(f"Error parsing education: {e}")
            return None

    def _parse_education_times(self, times: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse education times string into from_date, to_date.

        Examples:
        - "1973 - 1977" -> ("1973", "1977")
        - "2015" -> ("2015", "2015")
        - "" -> (None, None)
        """
        if not times:
            return None, None

        try:
            # Split on hyphen or en/em dash to get from and to dates
            parts = re.split(r"\s*[-–—]\s*", times, maxsplit=1)
            from_date = parts[0].strip()
            to_date = parts[1].strip() if len(parts) > 1 else from_date

            return from_date, to_date
        except Exception as e:
            logger.debug(f"Error parsing education times '{times}': {e}")
            return None, None

    async def _get_interests(self, base_url: str) -> list[Interest]:
        """Extract interests from the dedicated interests details page."""
        interests: list[Interest] = []
        seen: set[tuple[str, str]] = set()

        try:
            interests_url = urljoin(base_url, "details/interests/")
            await self.navigate_and_wait(interests_url)
            await self.page.wait_for_selector("main", timeout=10000)
            await self.wait_and_focus(1.5)

            categories = ["Top Voices", "Companies", "Newsletters", "Schools"]
            for category_name in categories:
                label = self.page.locator(f'label:has-text("{category_name}")').first
                if await label.count() == 0:
                    continue
                try:
                    await label.click()
                except Exception as e:
                    logger.debug(f"Could not open interest category {category_name}: {e}")
                    continue

                await self.wait_and_focus(1.5)

                items = await self.page.evaluate("""() => {
                    const main = document.querySelector('main');
                    if (!main) return [];
                    const out = [];
                    const seen = new Set();
                    for (const a of main.querySelectorAll('a[href]')) {
                        const href = a.getAttribute('href');
                        if (!/\\/(in|company|school|newsletter|showcase)\\//.test(href)) continue;
                        const text = (a.innerText || '').trim();
                        if (!text) continue;
                        const name = text.split('\\n')[0].trim();
                        if (!name || seen.has(href)) continue;
                        seen.add(href);
                        out.push({href, name});
                    }
                    return out;
                }""")

                category = self._map_interest_tab_to_category(category_name)
                for item in items:
                    key = (item["href"], category)
                    if key in seen:
                        continue
                    seen.add(key)
                    interests.append(
                        Interest(
                            name=item["name"],
                            category=category,
                            linkedin_url=item["href"],
                        )
                    )

        except Exception as e:
            logger.warning(f"Error getting interests: {e}")

        return interests

    
    async def _parse_interest_item(self, item, category: str) -> Optional[Interest]:
        """Parse a single interest item from profile or details page."""
        try:
            link = item.locator("a, link").first
            if await link.count() == 0:
                return None
            href = await link.get_attribute("href")

            unique_texts = await self._extract_unique_texts_from_element(item)
            name = unique_texts[0] if unique_texts else None

            if name and href:
                return Interest(
                    name=name,
                    category=category,
                    linkedin_url=href,
                )
            return None
        except Exception as e:
            logger.debug(f"Error parsing interest: {e}")
            return None

    def _map_interest_tab_to_category(self, tab_name: str) -> str:
        tab_lower = tab_name.lower()
        if "compan" in tab_lower:
            return "company"
        elif "group" in tab_lower:
            return "group"
        elif "school" in tab_lower:
            return "school"
        elif "newsletter" in tab_lower:
            return "newsletter"
        elif "voice" in tab_lower or "influencer" in tab_lower:
            return "influencer"
        else:
            return tab_lower
    async def _get_accomplishments(self, base_url: str) -> list[Accomplishment]:
        accomplishments: list[Accomplishment] = []
        seen_titles: set[str] = set()

        accomplishment_sections = [
            ("certifications", "certification"),
            ("honors", "honor"),
            ("publications", "publication"),
            ("patents", "patent"),
            ("courses", "course"),
            ("projects", "project"),
            ("languages", "language"),
            ("organizations", "organization"),
        ]

        for url_path, category in accomplishment_sections:
            try:
                section_url = urljoin(base_url, f"details/{url_path}/")
                await self.navigate_and_wait(section_url)
                await self.page.wait_for_selector("main", timeout=10000)
                await self.wait_and_focus(1)

                nothing_to_see = await self.page.locator(
                    'text="Nothing to see for now"'
                ).count()
                if nothing_to_see > 0:
                    continue

                items = await self.page.evaluate("""() => {
                    const lc = document.querySelector('main [data-component-type="LazyColumn"]');
                    if (!lc) return [];
                    const out = [];
                    const seen = new Set();
                    for (const mount of lc.children) {
                        for (const item of mount.querySelectorAll('div')) {
                            const texts = [...item.querySelectorAll('p')]
                                .map(p => p.innerText.trim())
                                .filter(Boolean);
                            if (texts.length < 2) continue;
                            const key = texts.join('|');
                            if (seen.has(key)) continue;
                            seen.add(key);
                            const box = item.querySelector('[data-testid="expandable-text-box"]');
                            const link = item.querySelector('a[href*="credential"], a[href*="verify"]');
                            out.push({
                                texts,
                                description: box ? box.innerText.trim() : '',
                                url: link ? link.getAttribute('href') : null,
                            });
                        }
                    }
                    return out;
                }""")

                for item in items:
                    parsed = self._parse_accomplishment(
                        item.get("texts") or [],
                        category,
                        item.get("description") or None,
                        item.get("url"),
                    )
                    if parsed and parsed.title not in seen_titles:
                        seen_titles.add(parsed.title)
                        accomplishments.append(parsed)

            except Exception as e:
                logger.debug(f"Error getting {category}s: {e}")
                continue

        return accomplishments

    def _parse_accomplishment(
        self,
        texts: list[str],
        category: str,
        description: Optional[str] = None,
        credential_url: Optional[str] = None,
    ) -> Optional[Accomplishment]:
        if not texts:
            return None

        title = texts[0]
        if not title or len(title) > 300:
            return None

        issuer = None
        issued_date = None
        credential_id = None

        for text in texts[1:]:
            if text.startswith("Credential ID"):
                credential_id = text.replace("Credential ID", "").strip()
                continue
            if text.startswith("Associated with"):
                continue
            if "·" in text:
                parts = text.split("·", 1)
                first = parts[0].replace("Issued by", "").strip()
                if first and not issuer:
                    issuer = first
                if len(parts) > 1 and not issued_date:
                    issued_date = parts[1].strip()
                continue
            if text.startswith("Issued by") and not issuer:
                issuer = text.replace("Issued by", "").strip()
                continue
            if text.startswith("Issued ") and not issued_date:
                issued_date = text.replace("Issued", "").strip()
                continue
            if not issuer:
                issuer = text

        return Accomplishment(
            category=category,
            title=title,
            issuer=issuer,
            issued_date=issued_date,
            credential_id=credential_id,
            credential_url=credential_url,
            description=description,
        )


    async def _parse_accomplishment_item(
        self, item, category: str
    ) -> Optional[Accomplishment]:
        try:
            entity = item.locator(
                'div[data-view-name="profile-component-entity"]'
            ).first
            if await entity.count() > 0:
                spans = await entity.locator('span[aria-hidden="true"]').all()
            else:
                spans = await item.locator('span[aria-hidden="true"]').all()

            title = ""
            issuer = ""
            issued_date = ""
            credential_id = ""

            for i, span in enumerate(spans[:5]):
                text = await span.text_content()
                if not text:
                    continue
                text = text.strip()

                if len(text) > 500:
                    continue

                if i == 0:
                    title = text
                elif "Issued by" in text:
                    parts = text.split("·")
                    issuer = parts[0].replace("Issued by", "").strip()
                    if len(parts) > 1:
                        issued_date = parts[1].strip()
                elif "Issued " in text and not issued_date:
                    issued_date = text.replace("Issued ", "")
                elif "Credential ID" in text:
                    credential_id = text.replace("Credential ID ", "")
                elif i == 1 and not issuer:
                    issuer = text
                elif (
                    any(
                        month in text
                        for month in [
                            "Jan",
                            "Feb",
                            "Mar",
                            "Apr",
                            "May",
                            "Jun",
                            "Jul",
                            "Aug",
                            "Sep",
                            "Oct",
                            "Nov",
                            "Dec",
                        ]
                    )
                    and not issued_date
                ):
                    if "·" in text:
                        parts = text.split("·")
                        issued_date = parts[0].strip()
                    else:
                        issued_date = text

            link = item.locator('a[href*="credential"], a[href*="verify"]').first
            credential_url = (
                await link.get_attribute("href") if await link.count() > 0 else None
            )

            if not title or len(title) > 200:
                return None

            return Accomplishment(
                category=category,
                title=title,
                issuer=issuer if issuer else None,
                issued_date=issued_date if issued_date else None,
                credential_id=credential_id if credential_id else None,
                credential_url=credential_url,
            )

        except Exception as e:
            logger.debug(f"Error parsing accomplishment: {e}")
            return None

    async def _get_contacts(self, base_url: str) -> list[Contact]:
        """Extract contact info by opening the contact-info dialog."""
        contacts: list[Contact] = []

        try:
            # Make sure we're on the main profile before opening the overlay.
            await self.navigate_and_wait(base_url)
            await self.wait_and_focus(1)

            contact_link = self.page.locator(
                'main a[href*="/overlay/contact-info"]'
            ).first
            if await contact_link.count() == 0:
                logger.debug("Contact info link not found")
                return contacts

            await contact_link.click()
            await self.wait_and_focus(2)

            try:
                await self.page.wait_for_selector(
                    'dialog[open], [role="dialog"]', timeout=10000
                )
            except Exception:
                logger.debug("Contact info dialog did not open")
                return contacts

            items = await self.page.evaluate("""() => {
                const dialog = document.querySelector('dialog[open], [role="dialog"]');
                if (!dialog) return [];
                const content = dialog.querySelector('[data-testid="dialog-content"]') || dialog;
                const lc = content.querySelector('[data-component-type="LazyColumn"]');
                const roots = lc ? [...lc.children] : [];
                const out = [];

                for (const mount of roots) {
                    for (const item of mount.querySelectorAll('div')) {
                        const ps = [...item.querySelectorAll('p')]
                            .map(p => p.innerText.trim())
                            .filter(Boolean);
                        if (ps.length < 2) continue;
                        const label = ps[0];
                        const valueText = ps.slice(1).join(' ');
                        const link = item.querySelector('p a[href]') || item.querySelector('a[href]');
                        out.push({
                            label,
                            value: valueText,
                            href: link ? link.getAttribute('href') : null,
                        });
                    }
                }

                // Deduplicate by label + value, keeping the first (outermost) entry.
                const seen = new Set();
                return out.filter(x => {
                    const key = x.label + '|' + x.value;
                    if (seen.has(key)) return false;
                    seen.add(key);
                    return true;
                });
            }""")

            for item in items:
                contact_type = self._map_contact_heading_to_type(item["label"])
                if not contact_type:
                    continue

                value = item.get("value") or ""
                href = item.get("href") or ""
                label = None
                if "(" in value and value.rstrip().endswith(")"):
                    label = value[value.index("(") + 1 : value.rstrip().rindex(")")].strip()
                    value = value[: value.index("(")].strip()

                if contact_type == "linkedin" and href:
                    value = href
                elif contact_type == "email" and href.startswith("mailto:"):
                    value = href.replace("mailto:", "").strip()

                if value:
                    contacts.append(
                        Contact(type=contact_type, value=value, label=label)
                    )

        except Exception as e:
            logger.warning(f"Error getting contacts: {e}")

        return contacts

    
    def _map_contact_heading_to_type(self, heading: str) -> Optional[str]:
        """Map contact section heading to contact type."""
        heading = heading.lower()
        if "profile" in heading:
            return "linkedin"
        elif "website" in heading:
            return "website"
        elif "email" in heading:
            return "email"
        elif "phone" in heading:
            return "phone"
        elif "twitter" in heading or "x.com" in heading:
            return "twitter"
        elif "birthday" in heading:
            return "birthday"
        elif "address" in heading:
            return "address"
        return None
