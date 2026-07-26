"""Person/Profile scraper for LinkedIn."""

from __future__ import annotations

import logging
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from urllib.parse import urlparse
from playwright.async_api import Page

from .base import BaseScraper
from ..models import Person, Experience, Education, Accomplishment, Interest, Contact
from ..callbacks import ProgressCallback
from ..core.exceptions import ScrapingError
from ._person_links import (
    classify_link,
    contact_type_from_heading,
    merge_contacts,
    profile_detail_url,
    unwrap_href,
)
from ._person_parsing import (
    _looks_like_job_title,
    is_education_metadata,
    is_valid_institution,
    item_text_and_url,
    looks_like_date_line,
    looks_like_degree,
    parse_education_times,
    parse_education_lines,
    parse_educations_text,
    parse_experience_lines,
    parse_experiences_text,
    parse_work_times,
    section_lines,
)

logger = logging.getLogger(__name__)

# Profile section headings that appear as <h2> but are not the person's name
_SECTION_HEADINGS = {
    "About",
    "Featured",
    "Activity",
    "Experience",
    "Education",
    "Skills",
    "Interests",
    "Analytics",
    "Explore Premium profiles",
    "People also viewed",
    "Ad Options",
}


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

    async def _wait_for_detail_section(self, heading: str) -> None:
        """Wait for a details page section, falling back to bare main."""
        try:
            await self.page.wait_for_selector(
                f'main:has-text("{heading}")', timeout=5000
            )
        except Exception:
            await self.page.wait_for_selector("main", timeout=5000)

    @staticmethod
    def _section_lines(text: str, header: str, stop_headers: Set[str]) -> List[str]:
        """Return non-empty lines after `header` until a stop header/footer."""
        return section_lines(text, header, stop_headers)

    @staticmethod
    def _unwrap_href(href: str) -> str:
        """Unwrap LinkedIn safety/redirect URLs to the real destination."""
        return unwrap_href(href)

    @classmethod
    def _classify_link(cls, href: str, label: Optional[str] = None) -> Contact:
        """Classify an outbound URL into a typed Contact."""
        return classify_link(href, label)

    async def scrape(
        self,
        linkedin_url: str,
        *,
        include_interests: bool = True,
        include_accomplishments: bool = True,
    ) -> Person:
        """
        Scrape a LinkedIn person profile.

        Args:
            linkedin_url: LinkedIn profile URL
            include_interests: Also scrape interests tabs (enabled by default)
            include_accomplishments: Also scrape certifications/honors/etc.
                (enabled by default for backward compatibility)

        Returns:
            Person object with scraped data

        Raises:
            AuthenticationError: If not logged in
            ScrapingError: If scraping fails
        """
        await self.callback.on_start("person", linkedin_url)

        try:
            await self.navigate_and_wait(linkedin_url)
            await self.callback.on_progress("Navigated to profile", 10)
            await self.ensure_logged_in()
            await self.page.wait_for_selector("main", timeout=10000)

            name, location = await self._get_name_and_location()
            await self.callback.on_progress(f"Got name: {name}", 20)

            open_to_work = await self._check_open_to_work()
            about = await self._get_about()
            await self.callback.on_progress("Got about section", 30)

            # Capture Featured / custom links while still on the main profile
            profile_links = await self._extract_outbound_links()

            experiences = await self._get_experiences(linkedin_url)
            await self.callback.on_progress(f"Got {len(experiences)} experiences", 55)

            educations = await self._get_educations(linkedin_url)
            await self.callback.on_progress(f"Got {len(educations)} educations", 70)

            interests: List[Interest] = []
            if include_interests:
                interests = await self._get_interests(linkedin_url)
                await self.callback.on_progress(f"Got {len(interests)} interests", 80)

            accomplishments: List[Accomplishment] = []
            if include_accomplishments:
                accomplishments = await self._get_accomplishments(linkedin_url)
                await self.callback.on_progress(
                    f"Got {len(accomplishments)} accomplishments", 90
                )

            contacts = await self._get_contacts(linkedin_url)
            contacts = self._merge_contacts(contacts, profile_links)
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

    async def _get_name_and_location(self) -> Tuple[str, Optional[str]]:
        """Extract name and location from profile."""
        try:
            name = await self.safe_extract_text("h1", default="")
            if not name:
                for h2 in await self.page.locator("h2").all():
                    txt = (await h2.text_content() or "").strip()
                    if (
                        txt
                        and txt not in _SECTION_HEADINGS
                        and "notification" not in txt.lower()
                    ):
                        name = txt
                        break

            location = None
            if name:
                main_text = await self.page.locator("main").first.inner_text()
                location = self._location_from_header_lines(main_text, name)

            return name if name else "Unknown", location
        except Exception as e:
            logger.warning(f"Error getting name/location: {e}")
            return "Unknown", None

    @staticmethod
    def _location_from_header_lines(text: str, name: str) -> Optional[str]:
        """
        Location sits after name/(pronouns)/headline and before Contact info.
        Taking the last header line avoids picking suggested-profile headlines.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        header: List[str] = []
        past_name = False
        for line in lines:
            if not past_name:
                if line == name:
                    past_name = True
                continue
            lower = line.lower()
            if (
                lower.startswith("contact")
                or "follower" in lower
                or "connection" in lower
            ):
                break
            if line in {"·", "•"}:
                continue
            # Pronouns like "He/Him"
            if (
                "/" in line
                and len(line) <= 20
                and any(p in line for p in ("Him", "Her", "Them"))
            ):
                continue
            header.append(line)
        # [headline, location] or just [location]
        if not header:
            return None
        return header[-1]

    async def _check_open_to_work(self) -> bool:
        """Check if profile has open to work badge."""
        try:
            # Look for open to work indicator
            img_title = await self.get_attribute_safe(
                ".pv-top-card-profile-picture img", "title", default=""
            )
            return "#OPEN_TO_WORK" in img_title.upper()
        except:
            return False

    async def _get_about(self) -> Optional[str]:
        """Extract about section from profile sections."""
        try:
            for section in await self.page.locator("section").all():
                txt = await section.inner_text()
                lines = [line.strip() for line in txt.splitlines() if line.strip()]
                if not lines or lines[0] != "About":
                    continue
                # Stop before UI chrome like "… more" / next section bleed
                body = []
                for line in lines[1:]:
                    if line in _SECTION_HEADINGS or line in {"… more", "... more"}:
                        break
                    body.append(line)
                if body:
                    return "\n".join(body).strip()
            return None
        except Exception as e:
            logger.debug(f"Error getting about section: {e}")
            return None

    async def _get_experiences(self, base_url: str) -> List[Experience]:
        """Extract experiences from the details/experience page (complete list)."""
        try:
            return await self._fetch_experiences_from_details(base_url)
        except Exception as e:
            logger.warning(
                f"Error getting experiences: {e}. The experience section may not be available or the page structure has changed."
            )
            return []

    async def _fetch_experiences_from_details(self, base_url: str) -> List[Experience]:
        """Scrape complete experience cards, with text as a fallback."""
        exp_url = profile_detail_url(base_url, "details/experience/")
        await self.navigate_and_wait(exp_url)
        await self._wait_for_detail_section("Experience")
        await self.scroll_page_to_bottom(pause_time=0.3, max_scrolls=4)

        experiences = await self._parse_experience_cards()
        if experiences:
            return self._dedupe_experiences(experiences)

        # Prefer full details-page text over truncated main-profile cards.
        page_text = await self.page.locator("main").first.inner_text()
        experiences = self._parse_experiences_from_text(page_text)
        if experiences:
            experiences = await self._attach_organization_urls(experiences, "/company/")
            return self._dedupe_experiences(experiences)

        await self.navigate_and_wait(base_url)
        experiences = await self._parse_experience_cards()
        return self._dedupe_experiences(experiences)

    async def _parse_experience_cards(self) -> List[Experience]:
        """Parse visible DOM cards, including grouped company roles."""
        experiences = []
        last_org_url = None
        items = await self.page.locator(
            'main [data-view-name="profile-component-entity"], '
            "main .pvs-list__paged-list-item"
        ).all()
        for item in items:
            try:
                lines, company_url = await item_text_and_url(item, "/company/")
                if company_url is None:
                    _, company_url = await item_text_and_url(item, "/school/")
                if company_url:
                    last_org_url = company_url
                else:
                    # Nested role cards often omit the company/school link.
                    company_url = last_org_url
                parsed = parse_experience_lines(lines, company_url)
                experiences.extend(parsed)
            except Exception as exc:
                logger.debug("Error parsing experience card: %s", exc)
        return experiences

    async def _attach_organization_urls(self, items: list, url_fragment: str) -> list:
        """Attach company/school URLs from page links when text parsing omitted them."""
        link_map = {}
        try:
            for link in await self.page.locator(
                'a[href*="{}"]'.format(url_fragment)
            ).all():
                href = (await link.get_attribute("href") or "").strip()
                text = (await link.text_content() or "").strip()
                if not href or not text:
                    continue
                if href.startswith("/"):
                    href = "https://www.linkedin.com{}".format(href)
                link_map[text.lower()] = href
        except Exception as exc:
            logger.debug("Error collecting organization URLs: %s", exc)
            return items

        enriched = []
        for item in items:
            if item.linkedin_url or not item.institution_name:
                enriched.append(item)
                continue
            name = item.institution_name.lower()
            matched_href: Optional[str] = link_map.get(name)
            if matched_href is None:
                for text, candidate in link_map.items():
                    if name in text or text in name:
                        matched_href = candidate
                        break
            if matched_href:
                item = item.model_copy(update={"linkedin_url": matched_href})
            enriched.append(item)
        return enriched

    @staticmethod
    def _dedupe_experiences(experiences: List[Experience]) -> List[Experience]:
        """Remove duplicate cards emitted by overlapping LinkedIn selectors."""
        by_identity: Dict[
            Tuple[Optional[str], Optional[str], Optional[str], FrozenSet[str]],
            Experience,
        ] = {}
        for experience in experiences:
            # frozenset collapses swapped title/company duplicates.
            identity = (
                experience.from_date,
                experience.to_date,
                experience.duration,
                frozenset(
                    value
                    for value in (
                        experience.position_title,
                        experience.institution_name,
                    )
                    if value
                ),
            )
            existing = by_identity.get(identity)
            if existing is None:
                by_identity[identity] = experience
                continue

            prefer_new = False
            if experience.linkedin_url and not existing.linkedin_url:
                prefer_new = True
            elif _looks_like_job_title(
                experience.position_title or ""
            ) and not _looks_like_job_title(existing.position_title or ""):
                prefer_new = True
            if prefer_new:
                by_identity[identity] = experience
        return list(by_identity.values())

    def _parse_experiences_from_text(self, text: str) -> List[Experience]:
        """Parse experience entries from details-page inner_text()."""
        return parse_experiences_text(text)

    async def _extract_unique_texts_from_element(self, element) -> List[str]:
        """Extract unique text content from nested elements, avoiding duplicates from parent/child overlap."""
        text_elements = await element.locator(
            'span[aria-hidden="true"], div > span'
        ).all()

        if not text_elements:
            text_elements = await element.locator("span, div").all()

        seen_texts: Set[str] = set()
        unique_texts = []

        for el in text_elements:
            text = await el.text_content()
            if text and text.strip():
                text = text.strip()
                if (
                    text not in seen_texts
                    and len(text) < 200
                    and not any(
                        text in t or t in text for t in seen_texts if len(t) > 3
                    )
                ):
                    seen_texts.add(text)
                    unique_texts.append(text)

        return unique_texts

    def _parse_work_times(
        self, work_times: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse work times string into from_date, to_date, duration.

        Examples:
        - "2000 - Present · 26 yrs 1 mo" -> ("2000", "Present", "26 yrs 1 mo")
        - "Jan 2020 - Dec 2022 · 2 yrs" -> ("Jan 2020", "Dec 2022", "2 yrs")
        - "2015 - Present" -> ("2015", "Present", None)
        """
        try:
            return parse_work_times(work_times)
        except Exception as e:
            logger.debug(f"Error parsing work times '{work_times}': {e}")
            return None, None, None

    async def _get_educations(self, base_url: str) -> List[Education]:
        """Extract educations from the details/education page (complete list)."""
        try:
            return await self._fetch_educations_from_details(base_url)
        except Exception as e:
            logger.warning(
                f"Error getting educations: {e}. The education section may not be publicly visible or the page structure has changed."
            )
            return []

    async def _fetch_educations_from_details(self, base_url: str) -> List[Education]:
        """Scrape complete education cards, with text as a fallback."""
        edu_url = profile_detail_url(base_url, "details/education/")
        await self.navigate_and_wait(edu_url)
        await self._wait_for_detail_section("Education")
        await self.scroll_page_to_bottom(pause_time=0.3, max_scrolls=3)

        educations = await self._parse_education_cards()
        if educations:
            return self._dedupe_educations(educations)

        # Prefer full details-page text over truncated main-profile cards.
        page_text = await self.page.locator("main").first.inner_text()
        educations = self._parse_educations_from_text(page_text)
        if educations:
            educations = await self._attach_organization_urls(educations, "/school/")
            return self._dedupe_educations(educations)

        await self.navigate_and_wait(base_url)
        educations = await self._parse_education_cards()
        return self._dedupe_educations(educations)

    async def _parse_education_cards(self) -> List[Education]:
        """Parse visible education cards and preserve school links when present."""
        educations = []
        items = await self.page.locator(
            'main [data-view-name="profile-component-entity"], '
            "main .pvs-list__paged-list-item"
        ).all()
        for item in items:
            try:
                lines, institution_url = await item_text_and_url(item, "/school/")
                education = parse_education_lines(lines, institution_url)
                if education:
                    educations.append(education)
            except Exception as exc:
                logger.debug("Error parsing education card: %s", exc)
        return educations

    @staticmethod
    def _dedupe_educations(educations: List[Education]) -> List[Education]:
        """Remove duplicate cards emitted by overlapping selectors."""
        by_key = {}
        for education in educations:
            key = (
                education.institution_name,
                education.degree,
                education.from_date,
                education.to_date,
            )
            by_key[key] = education
        return list(by_key.values())

    def _parse_educations_from_text(self, text: str) -> List[Education]:
        """Parse education entries from details-page inner_text()."""
        return parse_educations_text(text)

    @staticmethod
    def _is_education_metadata(line: str) -> bool:
        return is_education_metadata(line)

    @staticmethod
    def _looks_like_date_line(line: str) -> bool:
        return looks_like_date_line(line)

    @staticmethod
    def _looks_like_degree(line: str) -> bool:
        return looks_like_degree(line)

    @classmethod
    def _is_valid_institution(cls, line: str) -> bool:
        return is_valid_institution(line)

    def _parse_education_times(self, times: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse education times string into from_date, to_date.

        Examples:
        - "1973 - 1977" -> ("1973", "1977")
        - "2015" -> ("2015", "2015")
        - "" -> (None, None)
        """
        try:
            return parse_education_times(times)
        except Exception as e:
            logger.debug(f"Error parsing education times '{times}': {e}")
            return None, None

    async def _get_interests(self, base_url: str) -> list[Interest]:
        """Extract interests from the main profile page Interests section with tablist."""
        interests = []

        try:
            interests_heading = self.page.locator('h2:has-text("Interests")').first
            
            if await interests_heading.count() > 0:
                interests_section = interests_heading.locator('xpath=ancestor::*[.//tablist or .//*[@role="tablist"]][1]')
                if await interests_section.count() == 0:
                    interests_section = interests_heading.locator('xpath=ancestor::*[4]')
                
                tabs = await interests_section.locator('[role="tab"], tab').all() if await interests_section.count() > 0 else []
                
                if tabs:
                    for tab in tabs:
                        try:
                            tab_name = await tab.text_content()
                            if not tab_name:
                                continue
                            tab_name = tab_name.strip()
                            category = self._map_interest_tab_to_category(tab_name)

                            await tab.click()
                            await self.wait_and_focus(0.5)

                            tabpanel = interests_section.locator('[role="tabpanel"]').first
                            if await tabpanel.count() > 0:
                                list_items = await tabpanel.locator('li, listitem').all()
                                
                                for item in list_items:
                                    try:
                                        interest = await self._parse_interest_item(item, category)
                                        if interest:
                                            interests.append(interest)
                                    except Exception as e:
                                        logger.debug(f"Error parsing interest item: {e}")
                                        continue
                        except Exception as e:
                            logger.debug(f"Error processing interest tab: {e}")
                            continue
            
            if not interests:
                interests_url = urljoin(base_url, "details/interests/")
                await self.navigate_and_wait(interests_url)
                await self.page.wait_for_selector("main", timeout=10000)
                await self.wait_and_focus(1.5)

                tabs = await self.page.locator('[role="tab"], tab').all()

                if not tabs:
                    logger.debug("No interests tabs found on profile")
                    return interests

                for tab in tabs:
                    try:
                        tab_name = await tab.text_content()
                        if not tab_name:
                            continue
                        tab_name = tab_name.strip()
                        category = self._map_interest_tab_to_category(tab_name)

                        await tab.click()
                        await self.wait_and_focus(0.8)

                        tabpanel = self.page.locator('[role="tabpanel"], tabpanel').first
                        list_items = await tabpanel.locator("listitem, li, .pvs-list__paged-list-item").all()

                        for item in list_items:
                            try:
                                interest = await self._parse_interest_item(item, category)
                                if interest:
                                    interests.append(interest)
                            except Exception as e:
                                logger.debug(f"Error parsing interest item: {e}")
                                continue

                    except Exception as e:
                        logger.debug(f"Error processing interest tab: {e}")
                        continue

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
        accomplishments = []

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

                main_list = self.page.locator(
                    ".pvs-list__container, main ul, main ol"
                ).first
                if await main_list.count() == 0:
                    continue

                items = await main_list.locator(".pvs-list__paged-list-item").all()
                if not items:
                    items = await main_list.locator("> li").all()

                seen_titles = set()
                for item in items:
                    try:
                        accomplishment = await self._parse_accomplishment_item(
                            item, category
                        )
                        if accomplishment and accomplishment.title not in seen_titles:
                            seen_titles.add(accomplishment.title)
                            accomplishments.append(accomplishment)
                    except Exception as e:
                        logger.debug(f"Error parsing {category} item: {e}")
                        continue

            except Exception as e:
                logger.debug(f"Error getting {category}s: {e}")
                continue

        return accomplishments

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

    async def _get_contacts(self, base_url: str) -> List[Contact]:
        """Extract linked and plain-text fields from the contact-info dialog."""
        contacts = []
        try:
            contact_url = profile_detail_url(base_url, "overlay/contact-info/")
            await self.navigate_and_wait(contact_url)
            try:
                await self.page.wait_for_selector("main, [role='dialog']", timeout=5000)
            except Exception:
                pass

            dialog = self.page.locator('dialog, [role="dialog"]').first
            if await dialog.count() > 0:
                for heading in await dialog.locator("h3").all():
                    heading_text = (await heading.text_content() or "").strip()
                    contact_type = contact_type_from_heading(heading_text)
                    if not contact_type:
                        continue
                    container = heading.locator("xpath=..")
                    links = await container.locator("a[href]").all()
                    if links:
                        for link in links:
                            raw_href = (await link.get_attribute("href") or "").strip()
                            text = (await link.text_content() or "").strip()
                            if not raw_href:
                                continue
                            href = unwrap_href(raw_href)
                            label = await self._contact_label(container)
                            if href.startswith("mailto:"):
                                value = href[7:]
                            elif href.startswith("tel:"):
                                value = href[4:]
                            elif contact_type in {"linkedin", "website", "twitter"}:
                                value = href
                            else:
                                value = text or href
                            if contact_type == "website":
                                contacts.append(classify_link(value, label))
                            else:
                                contacts.append(
                                    Contact(
                                        type=contact_type,
                                        value=value,
                                        label=label,
                                    )
                                )
                    else:
                        plain_value = self._plain_contact_value(
                            await container.inner_text(), heading_text
                        )
                        if plain_value:
                            contacts.append(
                                Contact(type=contact_type, value=plain_value)
                            )

            outbound = await self._extract_outbound_links()
            return merge_contacts(contacts, outbound)
        except Exception as e:
            logger.warning(f"Error getting contacts: {e}")
            return contacts

    @staticmethod
    async def _contact_label(container) -> Optional[str]:
        """Return labels such as Mobile, Personal, or Work."""
        for element in await container.locator("span, generic").all():
            text = (await element.text_content() or "").strip()
            if text.startswith("(") and text.endswith(")"):
                return text[1:-1].strip() or None
        return None

    @staticmethod
    def _plain_contact_value(text: str, heading: str) -> Optional[str]:
        """Remove a contact heading while retaining a non-linked value."""
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and line.strip().lower() != heading.lower()
        ]
        return "\n".join(lines).strip() or None

    @staticmethod
    def _map_contact_heading_to_type(heading: str) -> Optional[str]:
        """Backward-compatible wrapper around the internal heading mapper."""
        return contact_type_from_heading(heading)
