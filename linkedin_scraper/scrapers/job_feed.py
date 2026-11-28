"""Time-windowed, multi-search job feed scraping.

Uses LinkedIn's guest job-search fragment endpoint because it:
  - honours the location filter (the authenticated search-results page may not),
  - exposes absolute posting dates via ``<time datetime="YYYY-MM-DD">``,
  - supports offset paging (``start=``), recency filtering (``f_TPR=``) and
    date-descending sort (``sortBy=DD``).

Card metadata (title/company/location/date) comes from the search fragment.
Descriptions require visiting each posting page via :class:`JobScraper`.
"""

import asyncio
import logging
import re
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence
from urllib.parse import urlencode

from lxml import html as lxml_html
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..core.exceptions import (
    AuthenticationError,
    RateLimitError,
    ScrapingError,
)
from ..models.job import JobFeedItem
from .base import BaseScraper
from .job import JobScraper

logger = logging.getLogger(__name__)

GUEST_SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)
CANONICAL_JOB_URL = "https://www.linkedin.com/jobs/view/{job_id}"
PAGE_SIZE_HINT = 10
DEFAULT_WINDOW_HOURS = 24

_RELATIVE_RE = re.compile(
    r"(\d+)\s*(minute|hour|day|week|month|year)s?\s*ago", re.IGNORECASE
)
_RATE_LIMIT_PHRASES = (
    "too many requests",
    "rate limit",
    "slow down",
    "exceeded the limit",
    "reached the limit",
)
_CHALLENGE_PHRASES = (
    "security verification",
    "security challenge",
    "verify your identity",
    "captcha",
    "checkpoint",
)
_AUTH_PHRASES = ("sign in", "join linkedin", "authwall", "log in")


@dataclass(frozen=True)
class SavedSearch:
    """A saved job search: keywords plus optional location."""

    keywords: str
    location: Optional[str] = None

    def describe(self) -> str:
        if self.location:
            return f"{self.keywords} @ {self.location}"
        return self.keywords


@dataclass
class FeedCard:
    """One posting discovered in a search-results fragment."""

    job_id: str
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    posted_at: Optional[str] = None  # ISO 8601 date (YYYY-MM-DD) when known
    posted_ts: Optional[datetime] = None  # used for filtering/sorting
    description: Optional[str] = None

    @property
    def url(self) -> str:
        return CANONICAL_JOB_URL.format(job_id=self.job_id)


@dataclass
class FeedResult:
    """Outcome of a feed collection run."""

    items: List[dict]
    reason: Optional[str] = None  # timeout | max-results | max-pages
    warnings: List[str] = field(default_factory=list)
    pages_fetched: int = 0
    search_count: int = 0

    @property
    def partial(self) -> bool:
        return self.reason is not None

    @property
    def timed_out(self) -> bool:
        return self.reason == "timeout"


def _clean(text: Optional[str]) -> str:
    return " ".join((text or "").split())


def parse_search_spec(spec: str) -> SavedSearch:
    """Parse ``KEYWORDS`` or ``KEYWORDS@LOCATION`` into a SavedSearch."""
    if not spec or not spec.strip():
        raise ValueError("Empty search specification.")

    raw = spec.strip()
    if "@" in raw:
        keywords, _, location = raw.rpartition("@")
    else:
        keywords, location = raw, None

    keywords = keywords.strip()
    location = (location.strip() or None) if location is not None else None
    if not keywords:
        raise ValueError(f"Search specification missing keywords: {spec!r}")
    return SavedSearch(keywords=keywords, location=location)


def load_saved_searches(path: str) -> List[SavedSearch]:
    """Load saved searches from a JSON file.

    Accepted shapes::

        ["software engineer @ Toronto", "data engineer"]

        [{"keywords": "software engineer", "location": "Toronto"}]

        {"searches": [...]}  # either of the above list shapes
    """
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"Search file not found: {path}")

    import json

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in search file {path}: {exc}") from exc

    if isinstance(payload, dict):
        payload = payload.get("searches")
    if not isinstance(payload, list):
        raise ValueError(
            f"Search file {path} must contain a list of searches or {{'searches': [...]}}."
        )

    searches: List[SavedSearch] = []
    for entry in payload:
        if isinstance(entry, str):
            searches.append(parse_search_spec(entry))
        elif isinstance(entry, dict):
            keywords = entry.get("keywords")
            if not isinstance(keywords, str) or not keywords.strip():
                raise ValueError(
                    f"Invalid search entry in {path}: missing non-empty 'keywords'."
                )
            location = entry.get("location")
            if location is not None and not isinstance(location, str):
                raise ValueError(
                    f"Invalid 'location' in {path}: expected string or null."
                )
            searches.append(
                SavedSearch(
                    keywords=keywords.strip(),
                    location=(location.strip() or None) if location else None,
                )
            )
        else:
            raise ValueError(
                f"Invalid search entry in {path}: expected string or object."
            )
    return searches


def resolve_cutoff(
    now: datetime,
    since: Optional[str] = None,
    since_hours: Optional[float] = None,
    since_days: Optional[float] = None,
) -> datetime:
    """Resolve the time-window lower bound in UTC."""
    if since is not None:
        raw = since.strip()
        try:
            if len(raw) == 10:
                cutoff = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                cutoff = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"Invalid --since value {since!r}; use ISO 8601 (e.g. 2026-11-25 or "
                "2026-11-25T12:00:00Z)."
            ) from exc
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        return cutoff.astimezone(timezone.utc)

    if since_hours is not None:
        if since_hours <= 0:
            raise ValueError("--since-hours must be greater than 0.")
        return now - timedelta(hours=float(since_hours))

    if since_days is not None:
        if since_days <= 0:
            raise ValueError("--since-days must be greater than 0.")
        return now - timedelta(days=float(since_days))

    return now - timedelta(hours=DEFAULT_WINDOW_HOURS)


def build_search_url(search: SavedSearch, start: int, window_seconds: int) -> str:
    """Build the guest search URL for one page of results."""
    params = {
        "keywords": search.keywords,
        "start": int(start),
        "sortBy": "DD",
        "f_TPR": f"r{max(1, int(window_seconds))}",
    }
    if search.location:
        params["location"] = search.location
    return f"{GUEST_SEARCH_URL}?{urlencode(params)}"


def _relative_to_datetime(text: str, now: datetime) -> Optional[datetime]:
    lowered = text.lower()
    if "just now" in lowered or "moment" in lowered:
        return now
    match = _RELATIVE_RE.search(lowered)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    deltas = {
        "minute": timedelta(minutes=amount),
        "hour": timedelta(hours=amount),
        "day": timedelta(days=amount),
        "week": timedelta(weeks=amount),
        "month": timedelta(days=30 * amount),
        "year": timedelta(days=365 * amount),
    }
    return now - deltas[unit]


def _posted_timestamp(
    time_el, now: datetime
) -> tuple[Optional[str], Optional[datetime]]:
    """Return (ISO date, timestamp) for a search-card <time> element.

    Semantics: LinkedIn's ``<time datetime=...>`` attribute is the *original*
    first-posted date, while the visible relative label may reflect a later
    repost/re-list date. We use the original date for ``postedAt``, filtering
    and sorting because LinkedIn's own ``f_TPR`` filter and date-descending
    sort are keyed on it; this keeps the feed window and page boundary
    consistent. A repost therefore does not change ``postedAt`` and is not
    duplicated (dedupe is by posting id); an old posting reposted recently is
    still outside a short window. ``<time datetime>`` has day resolution
    (YYYY-MM-DD); we interpret it as end-of-day UTC for filtering so jobs on
    the cutoff date are included. If the attribute is missing we fall back to
    the relative label (months=30d, years=365d, day resolution). If both are
    missing, ``postedAt`` is omitted.
    """
    iso = (time_el.get("datetime") or "").strip()
    relative_text = _clean(time_el.text_content())

    if iso:
        iso_date = iso[:10] if len(iso) >= 10 else iso
        try:
            if len(iso) == 10:
                day = datetime.strptime(iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                boundary_ts = day + timedelta(days=1) - timedelta(seconds=1)
            else:
                parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                boundary_ts = parsed.astimezone(timezone.utc)
            return iso_date, boundary_ts
        except ValueError:
            pass

    relative_ts = _relative_to_datetime(relative_text, now)
    if relative_ts is not None:
        return relative_ts.date().isoformat(), relative_ts

    return None, None


def parse_search_fragment(html_text: str, now: Optional[datetime] = None) -> List[FeedCard]:
    """Parse a guest search fragment into FeedCards (deduped by job id)."""
    now = now or datetime.now(timezone.utc)
    if not html_text or not html_text.strip():
        return []

    try:
        root = lxml_html.fromstring(html_text)
    except (lxml_html.etree.ParserError, ValueError) as exc:
        raise ScrapingError(f"Could not parse job search response: {exc}") from exc

    cards: List[FeedCard] = []
    seen: set[str] = set()

    for li in root.xpath("//li[.//div[@data-entity-urn]]"):
        urn_values = li.xpath(".//div[@data-entity-urn]/@data-entity-urn")
        if not urn_values:
            continue
        match = re.search(r"urn:li:jobPosting:(\d+)", urn_values[0])
        if not match:
            continue
        job_id = match.group(1)
        if job_id in seen:
            continue

        title_values = li.xpath(".//h3//text()")
        title = _clean(" ".join(title_values)) or None
        if not title:
            title_values = li.xpath(".//a[1]//span//text()")
            title = _clean(" ".join(title_values)) or None

        company_values = li.xpath(".//h4//a//text()") or li.xpath(".//h4//text()")
        company = _clean(" ".join(company_values)) or None

        posted_at: Optional[str] = None
        posted_ts: Optional[datetime] = None
        location: Optional[str] = None

        time_els = li.xpath(".//time")
        if time_els:
            time_el = time_els[0]
            posted_at, posted_ts = _posted_timestamp(time_el, now)
            container = time_el.getparent()
            if container is not None:
                spans = [s for s in container.iterchildren("span")]
                if spans:
                    location = _clean(spans[0].text_content()) or None

        if location is None:
            location_values = li.xpath(".//span[contains(@class, 'location')]//text()")
            location = _clean(" ".join(location_values)) or None

        seen.add(job_id)
        cards.append(
            FeedCard(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                posted_at=posted_at,
                posted_ts=posted_ts,
            )
        )

    return cards


def _merge_card(existing: FeedCard, incoming: FeedCard) -> None:
    if not existing.title:
        existing.title = incoming.title
    if not existing.company:
        existing.company = incoming.company
    if not existing.location:
        existing.location = incoming.location
    if not existing.posted_at:
        existing.posted_at = incoming.posted_at
    if not existing.posted_ts:
        existing.posted_ts = incoming.posted_ts
    if not existing.description:
        existing.description = incoming.description


def finalize_items(cards: Iterable[FeedCard]) -> List[dict]:
    """Dedupe by job id, sort by date descending, and build flat dicts."""
    merged: dict[str, FeedCard] = {}
    for card in cards:
        if card.job_id in merged:
            _merge_card(merged[card.job_id], card)
        else:
            merged[card.job_id] = card

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    ordered = sorted(
        merged.values(),
        key=lambda c: (c.posted_ts or epoch, c.job_id),
        reverse=True,
    )

    items: List[dict] = []
    for card in ordered:
        item = JobFeedItem(
            title=_clean(card.title) or None,
            url=card.url,
            company=_clean(card.company) or None,
            location=_clean(card.location) or None,
            postedAt=card.posted_at,
            description=(card.description.strip() if card.description else None),
        )
        items.append(item.to_dict())
    return items


class JobFeedScraper(BaseScraper):
    """Collect a deduped, time-windowed feed across multiple saved searches."""

    def __init__(
        self,
        page: Page,
        callback: Optional[ProgressCallback] = None,
        detail_scraper: Optional[JobScraper] = None,
        fetch_page: Optional[Callable[[str, int], object]] = None,
    ):
        super().__init__(page, callback or SilentCallback())
        self.detail_scraper = detail_scraper or JobScraper(page)
        self._fetch_page = fetch_page or self._default_fetch

    async def _default_fetch(self, url: str, timeout_ms: int):
        await self.page.goto(
            url, wait_until="domcontentloaded", timeout=max(1000, int(timeout_ms))
        )
        try:
            await self.page.wait_for_load_state(
                "domcontentloaded", timeout=max(1000, int(timeout_ms))
            )
        except Exception:
            pass
        return await self.page.content()

    def _check_blocked(self) -> None:
        url = (getattr(self.page, "url", "") or "").lower()
        if "/login" in url or "authwall" in url or "uas/login" in url:
            raise AuthenticationError(
                "LinkedIn redirected the job search to a login/authwall page."
            )
        if "checkpoint" in url or "challenge" in url:
            raise AuthenticationError(
                "LinkedIn security challenge (checkpoint) blocked the job search."
            )

    def _scan_blocked_text(self, text: str) -> None:
        lowered = _clean(text).lower()
        if any(phrase in lowered for phrase in _AUTH_PHRASES + _CHALLENGE_PHRASES):
            raise AuthenticationError(
                "LinkedIn presented an authentication/security challenge for the job search."
            )
        if any(phrase in lowered for phrase in _RATE_LIMIT_PHRASES):
            raise RateLimitError(
                "LinkedIn rate-limited the job search.",
                suggested_wait_time=1800,
            )

    def _text_of(self, html_text: str) -> str:
        try:
            return lxml_html.fromstring(html_text).text_content()
        except Exception:
            return html_text

    def _classify_empty_response(self, html_text: str) -> None:
        lowered = _clean(self._text_of(html_text)).lower()
        if "no matching" in lowered or "no results" in lowered:
            return
        if len(html_text) > 5000:
            raise ScrapingError(
                "Could not parse job search response; LinkedIn's DOM may have changed."
            )

    async def collect(
        self,
        searches: Sequence[SavedSearch],
        cutoff: datetime,
        *,
        timeout: float = 600,
        max_results: int = 200,
        max_pages: int = 20,
        page_delay: float = 2.0,
        detail_delay: float = 1.0,
        now: Optional[datetime] = None,
    ) -> FeedResult:
        now = now or datetime.now(timezone.utc)
        window_seconds = max(1, int((now - cutoff).total_seconds()))
        deadline = _time.monotonic() + max(1.0, float(timeout))

        collected: dict[str, FeedCard] = {}
        warnings: List[str] = []
        stop_reason: Optional[str] = None  # timeout | max-results | max-pages
        completed = False
        page_cap_reached = False
        pages_fetched = 0
        detail_attempts = 0
        detail_failures = 0

        stop_all = False
        for search in searches:
            if stop_all:
                break
            start = 0
            page_index = 0
            while True:
                if page_index >= max_pages:
                    page_cap_reached = True
                    break
                if _time.monotonic() >= deadline:
                    stop_reason = "timeout"
                    warnings.append(
                        f"timeout reached while paging '{search.describe()}'"
                    )
                    stop_all = True
                    break
                if len(collected) >= max_results:
                    if stop_reason is None:
                        stop_reason = "max-results"
                    break

                url = build_search_url(search, start, window_seconds)
                remaining_ms = max(1000, int((deadline - _time.monotonic()) * 1000))
                if remaining_ms <= 1000:
                    stop_reason = "timeout"
                    warnings.append("timeout reached before fetching next search page")
                    stop_all = True
                    break

                logger.debug(f"Fetching feed page: {url}")
                try:
                    html_text = await self._fetch_page(url, remaining_ms)
                except Exception as exc:
                    if _time.monotonic() >= deadline:
                        stop_reason = "timeout"
                        warnings.append(
                            f"timeout reached fetching search page: {exc}"
                        )
                        stop_all = True
                        break
                    raise ScrapingError(f"Failed to fetch job search page: {exc}") from exc

                pages_fetched += 1
                if self.page is not None:
                    self._check_blocked()

                if not html_text or not html_text.strip():
                    completed = True
                    break

                self._scan_blocked_text(self._text_of(html_text))

                cards = parse_search_fragment(html_text, now)
                if not cards:
                    completed = True
                    self._classify_empty_response(html_text)
                    break

                # Use the raw number of cards on the page for the next offset
                # (in-fragment dedupe can shrink `cards`).
                raw_count = max(len(cards), html_text.count("data-entity-urn"))
                page_max_ts = max(
                    (c.posted_ts or cutoff) for c in cards
                )
                new_ids = 0
                limit_hit = False
                for card in cards:
                    if card.posted_ts is not None and card.posted_ts < cutoff:
                        continue
                    if card.job_id in collected:
                        _merge_card(collected[card.job_id], card)
                        continue
                    if len(collected) >= max_results:
                        limit_hit = True
                        break
                    if _time.monotonic() >= deadline:
                        stop_reason = "timeout"
                        warnings.append("timeout reached before fetching job details")
                        stop_all = True
                        break

                    new_ids += 1
                    detail_attempts += 1
                    try:
                        job = await self.detail_scraper.scrape(card.url)
                        card.description = job.job_description
                        if not card.title:
                            card.title = job.job_title
                        if not card.company:
                            card.company = job.company
                        if not card.location:
                            card.location = job.location
                    except (RateLimitError, AuthenticationError):
                        raise
                    except Exception as exc:
                        detail_failures += 1
                        warnings.append(
                            f"detail scrape failed for {card.url}: {exc}"
                        )
                    collected[card.job_id] = card

                    if detail_delay and len(collected) < max_results:
                        await asyncio.sleep(detail_delay)

                if stop_all:
                    break
                if limit_hit:
                    if stop_reason is None:
                        stop_reason = "max-results"
                    stop_all = True
                    break

                # Sorted descending: once an entire page is older than the
                # window, every subsequent page is older too.
                if page_max_ts < cutoff:
                    completed = True
                    break
                if new_ids == 0:
                    completed = True
                    break
                if raw_count <= 0:
                    completed = True
                    break

                start += raw_count
                page_index += 1
                if page_delay:
                    await asyncio.sleep(page_delay)

        if stop_reason is None and page_cap_reached and not completed:
            stop_reason = "max-pages"

        if detail_attempts >= 3 and detail_failures == detail_attempts and collected:
            raise ScrapingError(
                "Scraping job details failed for every posting; LinkedIn's job DOM may "
                "have changed."
            )

        return FeedResult(
            items=finalize_items(collected.values()),
            reason=stop_reason,
            warnings=warnings,
            pages_fetched=pages_fetched,
            search_count=len(searches),
        )
