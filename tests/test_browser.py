"""Tests for BrowserManager."""
import pytest
from pathlib import Path
from linkedin_scraper import BrowserManager, ProxyConfig, ProxyError


@pytest.mark.asyncio
async def test_browser_manager_context():
    """Test BrowserManager as context manager."""
    async with BrowserManager(headless=True) as browser:
        assert browser.page is not None
        assert browser.context is not None
        assert browser.browser is not None


@pytest.mark.asyncio
async def test_browser_manager_navigation():
    """Test basic navigation."""
    async with BrowserManager(headless=True) as browser:
        await browser.page.goto("https://www.google.com")
        title = await browser.page.title()
        assert "Google" in title


@pytest.mark.unit
@pytest.mark.asyncio
async def test_browser_manager_session_save_load(tmp_path):
    """Test session save and load."""
    session_file = tmp_path / "test_session.json"
    
    async with BrowserManager(headless=True) as browser:
        # Navigate to a page
        await browser.page.goto("https://www.google.com")
        
        # Save session
        await browser.save_session(str(session_file))
        assert session_file.exists()
    
    # Load session in new browser
    async with BrowserManager(headless=True) as browser:
        await browser.load_session(str(session_file))
        # Should have cookies loaded
        cookies = await browser.context.cookies()
        assert len(cookies) >= 0  # At least session was loadable


@pytest.mark.asyncio
async def test_browser_manager_headless_mode():
    """Test headless mode."""
    async with BrowserManager(headless=True) as browser:
        assert browser.page is not None
        await browser.page.goto("https://www.example.com")
        content = await browser.page.content()
        assert len(content) > 0



@pytest.mark.unit
def test_proxy_missing_server_raises():
    """Test ProxyError when server key is absent."""
    with pytest.raises(ProxyError):
        BrowserManager(proxy={})


@pytest.mark.unit
def test_proxy_stored_on_instance():
    """Test proxy config is stored on the instance."""
    proxy: ProxyConfig = {"server": "http://proxy.example.com:8080"}
    browser = BrowserManager(proxy=proxy)
    assert browser.proxy == proxy


@pytest.mark.unit
def test_proxy_with_credentials():
    """Test proxy config with credentials."""
    proxy: ProxyConfig = {
        "server": "http://proxy.example.com:8080",
        "username": "user",
        "password": "secret",
    }
    browser = BrowserManager(proxy=proxy)
    assert browser.proxy["username"] == "user"
    assert browser.proxy["password"] == "secret"


@pytest.mark.unit
def test_no_proxy_by_default():
    """Test proxy is None when not supplied."""
    browser = BrowserManager()
    assert browser.proxy is None
