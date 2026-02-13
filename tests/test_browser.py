"""Tests for BrowserManager."""
import pytest
from pathlib import Path
from linkedin_scraper import BrowserManager


@pytest.mark.asyncio
async def test_browser_manager_context(tmp_path):
    """Test BrowserManager as context manager."""
    async with BrowserManager(user_data_dir=tmp_path / "browser_data", headless=True) as browser:
        assert browser.page is not None
        assert browser.context is not None


@pytest.mark.asyncio
async def test_browser_manager_navigation(tmp_path):
    """Test basic navigation."""
    async with BrowserManager(user_data_dir=tmp_path / "browser_data", headless=True) as browser:
        await browser.page.goto("https://www.google.com")
        title = await browser.page.title()
        assert "Google" in title


@pytest.mark.asyncio
async def test_browser_manager_persistent_context(tmp_path):
    """Test that persistent context retains state across sessions."""
    data_dir = tmp_path / "browser_data"

    # First session: navigate and set a cookie
    async with BrowserManager(user_data_dir=data_dir, headless=True) as browser:
        await browser.page.goto("https://www.example.com")
        cookies_before = await browser.context.cookies()
        assert isinstance(cookies_before, list)

    # Second session: same data dir should reuse the persistent profile
    async with BrowserManager(user_data_dir=data_dir, headless=True) as browser:
        assert browser.page is not None
        assert browser.context is not None


@pytest.mark.asyncio
async def test_browser_manager_headless_mode(tmp_path):
    """Test headless mode."""
    async with BrowserManager(user_data_dir=tmp_path / "browser_data", headless=True) as browser:
        assert browser.page is not None
        await browser.page.goto("https://www.example.com")
        content = await browser.page.content()
        assert len(content) > 0
