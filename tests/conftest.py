"""
Pytest configuration and fixtures for linkedin_scraper tests.
"""
import pytest
import asyncio
from pathlib import Path
from linkedin_scraper import BrowserManager
from linkedin_scraper.callbacks import SilentCallback


# Session file path
SESSION_FILE = Path(__file__).parent.parent / "linkedin_session.json"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def browser():
    """
    Fixture that provides a BrowserManager instance.
    Automatically loads session if available.
    
    Note: Uses headless=False for LinkedIn compatibility.
    LinkedIn may block or behave differently in headless mode.
    """
    async with BrowserManager(headless=False) as browser_manager:
        # Try to load session if it exists
        if SESSION_FILE.exists():
            await browser_manager.load_session(str(SESSION_FILE))
        yield browser_manager


@pytest.fixture
async def browser_with_session():
    """
    Fixture that provides a BrowserManager with loaded session.
    Skips test if session file doesn't exist.
    
    Note: Uses headless=False for LinkedIn compatibility.
    LinkedIn may block or behave differently in headless mode.
    """
    if not SESSION_FILE.exists():
        pytest.skip("Session file not found. See README for session setup instructions.")
    
    async with BrowserManager(headless=False) as browser_manager:
        await browser_manager.load_session(str(SESSION_FILE))
        yield browser_manager


@pytest.fixture
def silent_callback():
    """Fixture that provides a SilentCallback for testing without output."""
    return SilentCallback()


# Test profile URLs
@pytest.fixture
def test_profile_urls():
    """Fixture that provides test LinkedIn profile URLs."""
    return {
        "bill_gates": "https://www.linkedin.com/in/williamhgates/",
        "satya_nadella": "https://www.linkedin.com/in/satyanadella/",
        "reid_hoffman": "https://www.linkedin.com/in/reidhoffman/"
    }


@pytest.fixture
def test_company_urls():
    """Fixture that provides test LinkedIn company URLs."""
    return {
        "microsoft": "https://www.linkedin.com/company/microsoft/",
        "google": "https://www.linkedin.com/company/google/",
        "apple": "https://www.linkedin.com/company/apple/"
    }


@pytest.fixture
def test_job_search_params():
    """Fixture that provides test job search parameters."""
    return {
        "keywords": "software engineer",
        "location": "San Francisco, CA",
        "limit": 5
    }


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring LinkedIn session"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
