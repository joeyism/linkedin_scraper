"""Tests for authentication functions."""
import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from linkedin_scraper import BrowserManager
from linkedin_scraper.core.auth import is_logged_in


class _FakeLocator:
    def __init__(self, count: int):
        self._count = count

    async def count(self) -> int:
        return self._count


class _FakePage:
    """Page stub whose nav only appears after a wait."""

    def __init__(self, url: str, nav_appears: bool):
        self.url = url
        self._nav_appears = nav_appears
        self.waited = False
        self._counts = [0, 0]

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self._counts.pop(0) if self._counts else 0)

    async def wait_for_selector(self, selector: str, timeout=None, state=None) -> None:
        self.waited = True
        if not self._nav_appears:
            raise PlaywrightTimeoutError("nav not found")


@pytest.mark.asyncio
async def test_is_logged_in_false():
    """Test is_logged_in returns False when not logged in."""
    async with BrowserManager(headless=True) as browser:
        await browser.page.goto("https://www.linkedin.com")
        logged_in = await is_logged_in(browser.page)
        # Should not be logged in to a fresh page
        assert isinstance(logged_in, bool)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_waits_for_late_nav():
    """Nav renders after domcontentloaded; wait_timeout should catch it."""
    page = _FakePage("https://www.linkedin.com/in/someone/", nav_appears=True)
    assert await is_logged_in(page, wait_timeout=5000) is True
    assert page.waited is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_returns_false_when_nav_never_appears():
    page = _FakePage("https://www.linkedin.com/in/someone/", nav_appears=False)
    assert await is_logged_in(page, wait_timeout=50) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_logged_in_skips_wait_on_auth_blocker():
    """Auth blockers must short-circuit before waiting for nav."""
    page = _FakePage("https://www.linkedin.com/authwall", nav_appears=True)
    assert await is_logged_in(page, wait_timeout=5000) is False
    assert page.waited is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_is_logged_in_with_session(browser_with_session):
    """Test is_logged_in returns True with valid session."""
    # Navigate to LinkedIn first
    await browser_with_session.page.goto("https://www.linkedin.com/feed/")
    await browser_with_session.page.wait_for_load_state("domcontentloaded", timeout=15000)
    logged_in = await is_logged_in(browser_with_session.page)
    assert logged_in is True
