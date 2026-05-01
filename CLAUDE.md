# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

```bash
pip install -e .
pip install -r requirements-dev.txt
playwright install-deps chromium
```

Before scraping, create a session file via manual login:
```bash
python samples/create_session.py
```

## Common Commands

```bash
# Run all tests
pytest

# Unit tests only (no LinkedIn session needed)
pytest -m "not integration"

# Single test file
pytest tests/test_company_scraper.py -v

# With coverage
pytest --cov=linkedin_scraper

# Format / lint / type-check
black linkedin_scraper/
flake8 linkedin_scraper/
mypy linkedin_scraper/
```

## Architecture

This is an async Python library (v3.0+) for scraping LinkedIn using **Playwright**. v3.0 was a full rewrite from Selenium to Playwright with async/await throughout — old Selenium-based code (v2.x) is not compatible.

### Package layout

```
linkedin_scraper/
├── core/
│   ├── auth.py        # login_with_credentials, login_with_cookie, wait_for_manual_login
│   ├── browser.py     # BrowserManager async context manager (session save/load)
│   ├── exceptions.py  # AuthenticationError, RateLimitError, ProfileNotFoundError, etc.
│   └── utils.py       # retry_async decorator, detect_rate_limit, scroll helpers
├── models/            # Pydantic v2 models: Person, Company, Job, Post, Experience, etc.
├── scrapers/
│   ├── base.py        # BaseScraper: navigation, element helpers, rate-limit checks
│   ├── person.py      # PersonScraper → Person
│   ├── company.py     # CompanyScraper → Company
│   ├── company_posts.py  # CompanyPostsScraper → List[Post]
│   ├── job.py         # JobScraper → Job
│   └── job_search.py  # JobSearchScraper → List[str] (URLs)
└── callbacks.py       # ProgressCallback, ConsoleCallback, SilentCallback, JSONLogCallback
```

### Key patterns

**BrowserManager** is an async context manager that owns the Playwright lifecycle. Pass `browser.page` to scrapers. Use `browser.save_session()` / `browser.load_session()` for cookie persistence.

**Scrapers** inherit from `BaseScraper`, which handles navigation, scrolling, rate-limit detection, and element utilities. Each scraper's `scrape()` method takes a LinkedIn URL and returns a typed Pydantic model.

**Authentication**: LinkedIn blocks headless mode — always use `headless=False`. Integration tests must run in headed mode. Use `is_logged_in()` to verify session validity before scraping.

**Callbacks** are injected into scrapers for progress tracking without coupling. `SilentCallback` is the default no-op. Implement `ProgressCallback` for custom tracking.

**Retry logic**: `@retry_async()` decorator in `core/utils.py` wraps element interactions prone to timeouts, with exponential backoff.

### Typical usage flow

```python
async with BrowserManager(headless=False) as browser:
    await browser.load_session("session.json")
    scraper = PersonScraper(browser.page)
    person = await scraper.scrape("https://linkedin.com/in/username")
```

## Environment Variables

Optional `.env` file for programmatic login:
```
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=yourpassword
```

## Test Markers

- `unit` — fast, no external deps
- `integration` — requires a valid `session.json`
- `slow` — takes 5–30 seconds
- `asyncio_mode = auto` is set in `pytest.ini`
