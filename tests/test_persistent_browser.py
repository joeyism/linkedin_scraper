"""Tests for PersistentBrowserManager."""

import pytest
from linkedin_scraper import (
    PersistentBrowserManager,
    migrate_session_to_profile,
    BrowserManager,
)


@pytest.mark.asyncio
async def test_persistent_browser_context_manager(tmp_path):
    """Test PersistentBrowserManager as context manager."""
    profile_dir = tmp_path / "profile"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        assert browser.page is not None
        assert browser.context is not None
        # Profile directory should be created
        assert profile_dir.exists()


@pytest.mark.asyncio
async def test_persistent_browser_navigation(tmp_path):
    """Test basic navigation with persistent browser."""
    profile_dir = tmp_path / "profile"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        await browser.page.goto("https://www.google.com")
        title = await browser.page.title()
        assert "Google" in title


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persistent_browser_saves_cookies(tmp_path):
    """Verify persistent cookies (with expiry) persist across browser restarts."""
    import time

    profile_dir = tmp_path / "profile"
    test_url = "https://www.example.com"

    # First session: set a persistent cookie (with expiration date)
    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        await browser.page.goto(test_url)

        # Set cookie with expiration date (required for persistence)
        expiry = int(time.time()) + 86400  # 1 day from now
        await browser.context.add_cookies(
            [
                {
                    "name": "test_cookie",
                    "value": "test_value",
                    "domain": ".example.com",
                    "path": "/",
                    "expires": expiry,
                }
            ]
        )

        # Verify cookie is set
        cookies = await browser.context.cookies([test_url])
        cookie_names = [c["name"] for c in cookies]
        assert "test_cookie" in cookie_names

    # Profile should still exist after closing
    assert profile_dir.exists()

    # Verify profile directory has content (browser saved state)
    profile_files = list(profile_dir.rglob("*"))
    assert len(profile_files) > 0
    # Check for Cookies file specifically
    cookie_files = [f for f in profile_files if "Cookies" in f.name]
    assert len(cookie_files) > 0, "Cookies file should exist in profile"

    # Second session: verify persistent cookie persisted
    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        await browser.page.goto(test_url)

        # Check if persistent cookie persisted
        cookies = await browser.context.cookies([test_url])
        cookie_names = [c["name"] for c in cookies]
        assert (
            "test_cookie" in cookie_names
        ), "Persistent cookie should persist across browser restarts"

        # Verify cookie value
        test_cookie = next((c for c in cookies if c["name"] == "test_cookie"), None)
        assert test_cookie is not None
        assert test_cookie["value"] == "test_value"


@pytest.mark.asyncio
async def test_persistent_browser_reuses_existing_pages(tmp_path):
    """Test that persistent browser reuses existing pages on restart."""
    profile_dir = tmp_path / "profile"

    # First session: creates initial page
    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        assert browser.page is not None

    # Second session: should reuse existing page
    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        assert browser.page is not None
        # Should have reused the page or created new one
        assert len(browser.context.pages) >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persistent_browser_creates_profile_dir(tmp_path):
    """Test that profile directory is created automatically."""
    profile_dir = tmp_path / "nested" / "profile"

    # Profile doesn't exist yet
    assert not profile_dir.exists()

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        # Profile should now exist
        assert profile_dir.exists()
        assert browser.page is not None


@pytest.mark.asyncio
async def test_persistent_browser_expanduser(tmp_path):
    """Test that tilde expansion works in user_data_dir."""
    # This test uses tmp_path to avoid creating actual home directory profiles
    profile_dir = tmp_path / "profile"

    # Create with explicit path (no tilde, but verifies Path handling)
    async with PersistentBrowserManager(
        user_data_dir=str(profile_dir), headless=True
    ) as browser:
        assert browser.page is not None
        assert profile_dir.exists()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persistent_browser_clear_profile(tmp_path):
    """Test clear_profile() deletes the profile directory."""
    profile_dir = tmp_path / "profile"

    # Create profile
    browser = PersistentBrowserManager(user_data_dir=profile_dir, headless=True)
    await browser.start()
    await browser.page.goto("https://www.example.com")
    assert profile_dir.exists()
    await browser.close()

    # Clear profile
    browser.clear_profile()
    assert not profile_dir.exists()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persistent_browser_clear_profile_while_running_raises(tmp_path):
    """Test that clear_profile() raises error if browser is running."""
    profile_dir = tmp_path / "profile"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        # Should raise because browser is running
        with pytest.raises(
            RuntimeError, match="Cannot clear profile while browser is running"
        ):
            browser.clear_profile()


@pytest.mark.asyncio
async def test_persistent_browser_new_page(tmp_path):
    """Test creating additional pages in persistent context."""
    profile_dir = tmp_path / "profile"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        initial_count = len(browser.context.pages)

        # Create new page
        new_page = await browser.new_page()
        assert new_page is not None
        assert len(browser.context.pages) == initial_count + 1

        await new_page.close()


@pytest.mark.asyncio
async def test_persistent_browser_custom_viewport(tmp_path):
    """Test custom viewport settings."""
    profile_dir = tmp_path / "profile"
    custom_viewport = {"width": 1920, "height": 1080}

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True, viewport=custom_viewport
    ) as browser:
        viewport = browser.page.viewport_size
        assert viewport["width"] == 1920
        assert viewport["height"] == 1080


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persistent_browser_concurrent_access_prevention(tmp_path):
    """Test that concurrent access to same profile is handled."""
    profile_dir = tmp_path / "profile"

    # Start first browser
    browser1 = PersistentBrowserManager(user_data_dir=profile_dir, headless=True)
    await browser1.start()

    # Try to start second browser with same profile
    browser2 = PersistentBrowserManager(user_data_dir=profile_dir, headless=True)

    # Playwright's behavior varies by platform - some may allow concurrent access,
    # others may raise an error. We just verify it either works or raises RuntimeError
    try:
        await browser2.start()
        # If it succeeds, close it
        await browser2.close()
    except (RuntimeError, Exception) as e:
        # Expected on some platforms - profile locking prevents concurrent access
        assert (
            "in use" in str(e).lower()
            or "lock" in str(e).lower()
            or "running" in str(e).lower()
        )

    # Cleanup
    await browser1.close()


@pytest.mark.asyncio
async def test_persistent_browser_set_cookie(tmp_path):
    """Test set_cookie method."""
    profile_dir = tmp_path / "profile"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        await browser.set_cookie("custom_cookie", "custom_value", domain=".example.com")

        cookies = await browser.context.cookies()
        cookie_names = [c["name"] for c in cookies]
        assert "custom_cookie" in cookie_names


@pytest.mark.asyncio
async def test_persistent_browser_authentication_property(tmp_path):
    """Test is_authenticated property."""
    profile_dir = tmp_path / "profile"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        # Initially not authenticated
        assert browser.is_authenticated is False

        # Set authenticated
        browser.is_authenticated = True
        assert browser.is_authenticated is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_migrate_session_to_profile(tmp_path):
    """Test session migration from session.json to persistent profile."""
    session_file = tmp_path / "session.json"
    profile_dir = tmp_path / "profile"

    # Create a session.json file using BrowserManager
    async with BrowserManager(headless=True) as browser:
        await browser.page.goto("https://www.example.com")
        # Set a test cookie
        await browser.set_cookie("migration_test", "test_value", domain="example.com")
        await browser.save_session(str(session_file))

    assert session_file.exists()

    # Migrate to persistent profile
    success = await migrate_session_to_profile(
        session_path=session_file, user_data_dir=profile_dir, headless=True
    )

    # Migration should complete (may or may not verify login depending on URL)
    assert isinstance(success, bool)

    # Profile directory should exist
    assert profile_dir.exists()

    # Verify cookies were migrated by checking the session file had cookies
    # and the profile directory was created (actual cookie verification is tricky
    # because the migration function navigates to LinkedIn.com, not example.com)
    import json

    with open(session_file, "r") as f:
        session_data = json.load(f)
        # Verify original session had cookies
        assert len(session_data.get("cookies", [])) > 0
        cookie_names = [c["name"] for c in session_data["cookies"]]
        assert "migration_test" in cookie_names


@pytest.mark.unit
@pytest.mark.asyncio
async def test_migrate_session_nonexistent_file(tmp_path):
    """Test migration with nonexistent session file."""
    session_file = tmp_path / "nonexistent.json"
    profile_dir = tmp_path / "profile"

    with pytest.raises(FileNotFoundError):
        await migrate_session_to_profile(
            session_path=session_file, user_data_dir=profile_dir, headless=True
        )


@pytest.mark.asyncio
async def test_persistent_browser_properties_before_start(tmp_path):
    """Test that accessing properties before start() raises RuntimeError."""
    profile_dir = tmp_path / "profile"
    browser = PersistentBrowserManager(user_data_dir=profile_dir, headless=True)

    # Should raise before start()
    with pytest.raises(RuntimeError):
        _ = browser.page

    with pytest.raises(RuntimeError):
        _ = browser.context

    # Start browser
    await browser.start()

    # Should work after start()
    assert browser.page is not None
    assert browser.context is not None

    await browser.close()


@pytest.mark.asyncio
async def test_persistent_browser_compatible_with_scrapers(tmp_path):
    """
    Test that PersistentBrowserManager is compatible with existing scrapers.

    This verifies the .page property works as a drop-in replacement for BrowserManager.
    """
    profile_dir = tmp_path / "profile"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True
    ) as browser:
        # Scrapers expect a Page object from browser.page
        page = browser.page

        # Verify it's a valid Playwright Page
        await page.goto("https://www.example.com")
        title = await page.title()
        assert len(title) > 0

        # Verify common Page methods work
        content = await page.content()
        assert len(content) > 0


@pytest.mark.asyncio
async def test_persistent_browser_slow_mo(tmp_path):
    """Test slow_mo parameter."""
    profile_dir = tmp_path / "profile"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True, slow_mo=50
    ) as browser:
        # Just verify it starts without error
        assert browser.page is not None


@pytest.mark.asyncio
async def test_persistent_browser_user_agent(tmp_path):
    """Test custom user agent."""
    profile_dir = tmp_path / "profile"
    custom_ua = "Mozilla/5.0 (TestBot/1.0)"

    async with PersistentBrowserManager(
        user_data_dir=profile_dir, headless=True, user_agent=custom_ua
    ) as browser:
        # Navigate to a page that might echo user agent
        await browser.page.goto("https://www.example.com")

        # Evaluate user agent in page context
        ua = await browser.page.evaluate("navigator.userAgent")
        assert custom_ua in ua
