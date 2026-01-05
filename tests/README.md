# LinkedIn Scraper Tests

This directory contains pytest tests for the linkedin_scraper library.

## Setup

1. Install test dependencies:
```bash
pip install -r requirements.txt
```

2. For integration tests, create a LinkedIn session:
```bash
python setup_session.py
```

This will create `linkedin_session.json` which is required for integration tests.

## Running Tests

### Run all tests
```bash
pytest
```

### Run only unit tests (no LinkedIn session required)
```bash
pytest -m unit
```

### Run only integration tests (requires LinkedIn session)
```bash
pytest -m integration
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_person_scraper.py
```

### Run specific test
```bash
pytest tests/test_person_scraper.py::test_person_scraper_basic
```

### Skip slow tests
```bash
pytest -m "not slow"
```

## Test Structure

```
tests/
├── conftest.py                  # Pytest fixtures and configuration
├── test_person_scraper.py       # PersonScraper tests
├── test_company_scraper.py      # CompanyScraper tests
├── test_job_scraper.py          # Job and JobSearch tests
├── test_browser.py              # BrowserManager tests
└── test_auth.py                 # Authentication tests
```

## Test Markers

- `@pytest.mark.unit` - Unit tests (no external dependencies)
- `@pytest.mark.integration` - Integration tests (requires LinkedIn session)
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.asyncio` - Async tests

## Fixtures

Available fixtures (defined in `conftest.py`):

- `browser` - Provides BrowserManager instance
- `browser_with_session` - Provides BrowserManager with loaded session
- `silent_callback` - Provides SilentCallback for testing
- `test_profile_urls` - Dictionary of test LinkedIn profile URLs
- `test_company_urls` - Dictionary of test company URLs
- `test_job_search_params` - Job search parameters for testing

## Example

```python
import pytest
from linkedin_scraper import PersonScraper

@pytest.mark.integration
@pytest.mark.asyncio
async def test_my_scraper(browser_with_session, silent_callback):
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape("https://linkedin.com/in/profile")
    assert person.name is not None
```

## CI/CD Integration

For CI/CD pipelines, you can:

1. Run only unit tests (no LinkedIn session needed):
```bash
pytest -m unit
```

2. Or mock the session for integration tests (advanced).

## Important Notes

### Headless Mode
Integration tests run with `headless=False` because LinkedIn may block or behave differently in headless mode. This means:
- Browser windows will open during integration tests
- Tests will be slower than headless tests
- You'll see the browser automation in action

If you want headless tests, you need to implement stealth mode or use unit tests only.

### Test Speed
- **Unit tests**: Fast (~1-2 seconds total)
- **Integration tests**: Slow (5-30 seconds per test) due to:
  - Browser launches
  - Network requests to LinkedIn
  - Page rendering and waiting

## Troubleshooting

### "Session file not found"
Run `python setup_session.py` to create a LinkedIn session.

### Tests timing out or hanging
- Integration tests require browser windows (headless=False)
- Make sure you have Xvfb or a display available in headless environments
- Or run only unit tests: `pytest -m unit`

### "Rate limited" or no data returned
LinkedIn may rate limit requests or block scraping. Solutions:
- Add delays between tests
- Run tests individually instead of all at once
- Refresh your session by running `setup_session.py` again

### Playwright not installed
```bash
playwright install chromium
```

### Browser opens but tests fail
- Ensure your session is valid (re-run `setup_session.py`)
- Check if LinkedIn requires re-authentication
- LinkedIn's UI may have changed (selectors need updating)
