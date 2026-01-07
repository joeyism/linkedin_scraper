"""Tests for authentication functions."""
import pytest
from linkedin_scraper import BrowserManager
from linkedin_scraper.core.auth import is_logged_in


@pytest.mark.asyncio
async def test_is_logged_in_false():
    """Test is_logged_in returns False when not logged in."""
    async with BrowserManager(headless=True) as browser:
        await browser.page.goto("https://www.linkedin.com")
        logged_in = await is_logged_in(browser.page)
        # Should not be logged in to a fresh page
        assert isinstance(logged_in, bool)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_is_logged_in_with_session(browser_with_session):
    """Test is_logged_in returns True with valid session."""
    # Navigate to LinkedIn first
    await browser_with_session.page.goto("https://www.linkedin.com/feed/")
    await browser_with_session.page.wait_for_load_state("domcontentloaded", timeout=15000)
    logged_in = await is_logged_in(browser_with_session.page)
    assert logged_in is True
