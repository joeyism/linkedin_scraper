"""Person/Profile scraper for LinkedIn."""

import logging
from typing import Optional
from urllib.parse import urljoin
from playwright.async_api import Page

from .base import BaseScraper
from ..models import Person, Experience, Education, Accomplishment
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
            await self.page.wait_for_selector('main', timeout=10000)
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
            
            # Get educations
            educations = await self._get_educations(linkedin_url)
            await self.callback.on_progress(f"Got {len(educations)} educations", 80)
            
            # Build Person model
            person = Person(
                linkedin_url=linkedin_url,
                name=name,
                location=location,
                about=about,
                open_to_work=open_to_work,
                experiences=experiences,
                educations=educations,
            )
            
            await self.callback.on_progress("Scraping complete", 100)
            await self.callback.on_complete("person", person)
            
            return person
            
        except Exception as e:
            await self.callback.on_error(e)
            raise ScrapingError(f"Failed to scrape person profile: {e}")
    
    async def _get_name_and_location(self) -> tuple[str, Optional[str]]:
        """Extract name and location from profile."""
        try:
            name = await self.safe_extract_text('h1', default="Unknown")
            location = await self.safe_extract_text('.text-body-small.inline.t-black--light.break-words', default="")
            return name, location if location else None
        except Exception as e:
            logger.warning(f"Error getting name/location: {e}")
            return "Unknown", None
    
    async def _check_open_to_work(self) -> bool:
        """Check if profile has open to work badge."""
        try:
            # Look for open to work indicator
            img_title = await self.get_attribute_safe('.pv-top-card-profile-picture img', 'title', default="")
            return "#OPEN_TO_WORK" in img_title.upper()
        except:
            return False
    
    async def _get_about(self) -> Optional[str]:
        """Extract about section."""
        try:
            # Find the profile card that contains "About"
            profile_cards = await self.page.locator('[data-view-name="profile-card"]').all()
            
            for card in profile_cards:
                card_text = await card.inner_text()
                # Check if this card contains "About" heading
                if card_text.strip().startswith('About'):
                    # Get the span with aria-hidden to avoid duplication
                    about_spans = await card.locator('span[aria-hidden="true"]').all()
                    # Skip the first span (it's the "About" heading), get the content
                    if len(about_spans) > 1:
                        about_text = await about_spans[1].text_content()
                        return about_text.strip() if about_text else None
            
            return None
        except Exception as e:
            logger.debug(f"Error getting about section: {e}")
            return None
    
    async def _get_experiences(self, base_url: str) -> list[Experience]:
        """
        Navigate to experience page and scrape experiences.
        
        Args:
            base_url: Base LinkedIn profile URL
            
        Returns:
            List of Experience objects
        """
        experiences = []
        
        try:
            # Navigate to experience detail page
            exp_url = urljoin(base_url, "details/experience")
            await self.navigate_and_wait(exp_url)
            
            # Wait for content
            await self.page.wait_for_selector('main', timeout=10000)
            await self.wait_and_focus(1)
            
            # Scroll to load all content
            await self.scroll_page_to_half()
            await self.scroll_page_to_bottom(pause_time=0.5, max_scrolls=5)
            
            # Find the main list
            main_list = self.page.locator('.pvs-list__container').first
            await main_list.wait_for(timeout=10000)
            
            # Get all experience items
            items = await main_list.locator('.pvs-list__paged-list-item').all()
            
            for item in items:
                try:
                    # _parse_experience_item can return a single Experience or a list
                    result = await self._parse_experience_item(item)
                    if result:
                        if isinstance(result, list):
                            experiences.extend(result)
                        else:
                            experiences.append(result)
                except Exception as e:
                    logger.debug(f"Error parsing experience item: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"Error getting experiences: {e}. The experience section may not be available or the page structure has changed.")
        
        return experiences
    
    async def _parse_experience_item(self, item):
        """
        Parse a single experience item. Can return a single Experience or a list of Experiences
        for nested positions (multiple roles at same company).
        
        LinkedIn DOM Structure:
        - entity (div[data-view-name="profile-component-entity"])
          - child 0: company logo + link
          - child 1: position details
            - detail_child 0: summary
              - nested 0
                - span 0: position title (or company name if nested)
                - span 1: company name (or total duration if nested)
                - span 2: work times
                - span 3: location (optional)
            - detail_child 1: description OR nested positions list
        """
        try:
            # Get the entity div
            entity = item.locator('div[data-view-name="profile-component-entity"]').first
            
            # Get direct children (logo, details)
            children = await entity.locator('> *').all()
            if len(children) < 2:
                return None
            
            # Child 0: Get company URL from logo link
            company_link = children[0].locator('a').first
            company_url = await company_link.get_attribute('href')
            
            # Child 1: Get position details
            detail_container = children[1]
            detail_children = await detail_container.locator('> *').all()
            
            if len(detail_children) == 0:
                return None
            
            # Check if detail_children[1] contains nested positions
            has_nested_positions = False
            if len(detail_children) > 1:
                nested_list = await detail_children[1].locator('.pvs-list__container').count()
                has_nested_positions = nested_list > 0
            
            if has_nested_positions:
                # Parse nested positions (multiple roles at same company)
                return await self._parse_nested_experience(item, company_url, detail_children)
            else:
                # Single position - use standard parsing
                first_detail = detail_children[0]
                nested_elements = await first_detail.locator('> *').all()
                
                if len(nested_elements) == 0:
                    return None
                
                # Get the container with the spans
                span_container = nested_elements[0]
                outer_spans = await span_container.locator('> *').all()
                
                # Extract text from each span element
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
                
                # Parse dates
                from_date, to_date, duration = self._parse_work_times(work_times)
                
                # Get description if available (from detail_children[1])
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
                    description=description.strip() if description else None
                )
            
        except Exception as e:
            logger.debug(f"Error parsing experience: {e}")
            return None
    
    async def _parse_nested_experience(self, item, company_url: str, detail_children) -> list[Experience]:
        """
        Parse nested experience positions (multiple roles at the same company).
        Returns a list of Experience objects.
        """
        experiences = []
        
        try:
            # Get company name from first detail
            first_detail = detail_children[0]
            nested_elements = await first_detail.locator('> *').all()
            if len(nested_elements) == 0:
                return []
            
            span_container = nested_elements[0]
            outer_spans = await span_container.locator('> *').all()
            
            # First span is company name for nested positions
            company_name = ""
            if len(outer_spans) >= 1:
                aria_span = outer_spans[0].locator('span[aria-hidden="true"]').first
                company_name = await aria_span.text_content()
            
            # Get the nested list from detail_children[1]
            nested_container = detail_children[1].locator('.pvs-list__container').first
            nested_items = await nested_container.locator('.pvs-list__paged-list-item').all()
            
            for nested_item in nested_items:
                try:
                    # Each nested item has a link with position details
                    link = nested_item.locator('a').first
                    link_children = await link.locator('> *').all()
                    
                    if len(link_children) == 0:
                        continue
                    
                    # Navigate to get the spans
                    first_child = link_children[0]
                    nested_els = await first_child.locator('> *').all()
                    if len(nested_els) == 0:
                        continue
                    
                    spans_container = nested_els[0]
                    position_spans = await spans_container.locator('> *').all()
                    
                    # Extract position details
                    position_title = ""
                    work_times = ""
                    location = ""
                    
                    if len(position_spans) >= 1:
                        aria_span = position_spans[0].locator('span[aria-hidden="true"]').first
                        position_title = await aria_span.text_content()
                    if len(position_spans) >= 2:
                        aria_span = position_spans[1].locator('span[aria-hidden="true"]').first
                        work_times = await aria_span.text_content()
                    if len(position_spans) >= 3:
                        aria_span = position_spans[2].locator('span[aria-hidden="true"]').first
                        location = await aria_span.text_content()
                    
                    # Parse dates
                    from_date, to_date, duration = self._parse_work_times(work_times)
                    
                    # Get description if available
                    description = ""
                    if len(link_children) > 1:
                        description = await link_children[1].inner_text()
                    
                    experiences.append(Experience(
                        position_title=position_title.strip(),
                        institution_name=company_name.strip(),
                        linkedin_url=company_url,
                        from_date=from_date,
                        to_date=to_date,
                        duration=duration,
                        location=location.strip(),
                        description=description.strip() if description else None
                    ))
                    
                except Exception as e:
                    logger.debug(f"Error parsing nested position: {e}")
                    continue
            
        except Exception as e:
            logger.debug(f"Error parsing nested experience: {e}")
        
        return experiences
    
    def _parse_work_times(self, work_times: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse work times string into from_date, to_date, duration.
        
        Examples:
        - "2000 - Present · 26 yrs 1 mo" -> ("2000", "Present", "26 yrs 1 mo")
        - "Jan 2020 - Dec 2022 · 2 yrs" -> ("Jan 2020", "Dec 2022", "2 yrs")
        - "2015 - Present" -> ("2015", "Present", None)
        """
        if not work_times:
            return None, None, None
        
        try:
            # Split by · to separate date range from duration
            parts = work_times.split("·")
            times = parts[0].strip() if len(parts) > 0 else ""
            duration = parts[1].strip() if len(parts) > 1 else None
            
            # Parse dates - split by " - " to get from and to
            if " - " in times:
                date_parts = times.split(" - ")
                from_date = date_parts[0].strip()
                to_date = date_parts[1].strip() if len(date_parts) > 1 else ""
            else:
                from_date = times
                to_date = ""
            
            return from_date, to_date, duration
        except Exception as e:
            logger.debug(f"Error parsing work times '{work_times}': {e}")
            return None, None, None
    
    async def _get_educations(self, base_url: str) -> list[Education]:
        """
        Navigate to education page and scrape educations.
        
        Args:
            base_url: Base LinkedIn profile URL
            
        Returns:
            List of Education objects
        """
        educations = []
        
        try:
            # Navigate to education detail page
            edu_url = urljoin(base_url, "details/education")
            await self.navigate_and_wait(edu_url)
            
            # Wait for content
            await self.page.wait_for_selector('main', timeout=10000)
            await self.wait_and_focus(1)
            
            # Scroll to load all content
            await self.scroll_page_to_half()
            await self.scroll_page_to_bottom(pause_time=0.5, max_scrolls=5)
            
            # Find the main list
            main_list = self.page.locator('.pvs-list__container').first
            await main_list.wait_for(timeout=10000)
            
            # Get all education items
            items = await main_list.locator('.pvs-list__paged-list-item').all()
            
            for item in items:
                try:
                    edu = await self._parse_education_item(item)
                    if edu:
                        educations.append(edu)
                except Exception as e:
                    logger.debug(f"Error parsing education item: {e}")
                    continue
            
        except Exception as e:
            logger.warning(f"Error getting educations: {e}. The education section may not be publicly visible or the page structure has changed.")
        
        return educations
    
    async def _parse_education_item(self, item) -> Optional[Education]:
        """
        Parse a single education item.
        
        LinkedIn DOM Structure (similar to experience):
        - entity (div[data-view-name="profile-component-entity"])
          - child 0: institution logo + link
          - child 1: education details
            - detail_child 0
              - nested 0
                - span 0: institution name
                - span 1: degree (optional)
                - span 2: dates (optional)
        """
        try:
            # Get the entity div
            entity = item.locator('div[data-view-name="profile-component-entity"]').first
            
            # Get direct children (logo, details)
            children = await entity.locator('> *').all()
            if len(children) < 2:
                return None
            
            # Child 0: Get institution URL from logo link
            institution_link = children[0].locator('a').first
            institution_url = await institution_link.get_attribute('href')
            
            # Child 1: Get education details
            detail_container = children[1]
            detail_children = await detail_container.locator('> *').all()
            
            if len(detail_children) == 0:
                return None
            
            first_detail = detail_children[0]
            nested_elements = await first_detail.locator('> *').all()
            
            if len(nested_elements) == 0:
                return None
            
            # Get the container with the spans
            span_container = nested_elements[0]
            outer_spans = await span_container.locator('> *').all()
            
            # Extract text from each span element (using aria-hidden to avoid duplicates)
            # LinkedIn structure varies:
            # - 3 spans: institution, degree, dates
            # - 2 spans: institution, dates (no degree)
            # - 1 span: institution only
            institution_name = ""
            degree = None
            times = ""
            
            if len(outer_spans) >= 1:
                aria_span = outer_spans[0].locator('span[aria-hidden="true"]').first
                institution_name = await aria_span.text_content()
            
            if len(outer_spans) == 3:
                # Has degree
                aria_span = outer_spans[1].locator('span[aria-hidden="true"]').first
                degree = await aria_span.text_content()
                aria_span = outer_spans[2].locator('span[aria-hidden="true"]').first
                times = await aria_span.text_content()
            elif len(outer_spans) == 2:
                # No degree, just dates
                aria_span = outer_spans[1].locator('span[aria-hidden="true"]').first
                times = await aria_span.text_content()
            
            # Parse dates
            from_date, to_date = self._parse_education_times(times)
            
            # Get description if available (from detail_children[1])
            description = ""
            if len(detail_children) > 1:
                description = await detail_children[1].inner_text()
            
            return Education(
                institution_name=institution_name.strip(),
                degree=degree.strip() if degree else None,
                linkedin_url=institution_url,
                from_date=from_date,
                to_date=to_date,
                description=description.strip() if description else None
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
            # Split by " - " to get from and to dates
            if " - " in times:
                parts = times.split(" - ")
                from_date = parts[0].strip()
                to_date = parts[1].strip() if len(parts) > 1 else ""
            else:
                # Single year
                from_date = times.strip()
                to_date = times.strip()
            
            return from_date, to_date
        except Exception as e:
            logger.debug(f"Error parsing education times '{times}': {e}")
            return None, None
