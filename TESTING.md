# LinkedIn Scraper - Testing Guide

## 📊 Test Summary

This package includes comprehensive tests to ensure reliability and correctness.

**Test Categories:**
- ✅ Unit tests (fast, no LinkedIn required)
- ⚠️ Integration tests (require LinkedIn session)

---

## 🧪 Running Tests

### Quick Unit Tests (Recommended)

Run fast unit tests that don't require LinkedIn authentication:

```bash
pytest tests/ -v -m "not integration"
```

**Expected result:** All unit tests pass in ~5 seconds

**What's tested:**
- Data model conversions (to_dict, to_json)
- Browser context management
- Session save/load
- Navigation utilities
- Basic functionality without network calls

---

### Full Test Suite (Requires LinkedIn Session)

Some tests require actual LinkedIn scraping and take longer:

```bash
# First, create a valid session
# (See README for session setup instructions)

# Run all tests including integration tests
pytest tests/ -v
```

⚠️ **Note:** Integration tests:
- Require valid `linkedin_session.json`
- Make real network calls to LinkedIn
- Take 2-5 minutes per test
- May hit rate limits if run too frequently

---

## 📋 Test Files

### Unit Tests
- `test_browser.py` - Browser management and session handling
- `test_person_scraper.py` - Person data model tests
- `test_company_scraper.py` - Company data model tests
- `test_job_scraper.py` - Job data model tests
- `test_auth.py` - Authentication utilities (non-network tests)

### Integration Tests
Integration tests in the same files above test actual LinkedIn scraping when run with a valid session.

---

## 🎯 Test Commands Reference

```bash
# Run only unit tests (fast)
pytest -m "not integration" -v

# Run specific test file
pytest tests/test_person_scraper.py -v

# Run specific test
pytest tests/test_person_scraper.py::test_person_model_to_dict -v

# Run with coverage
pytest --cov=linkedin_scraper -v

# Run with verbose output
pytest -v -s
```

---

## 🔍 Writing New Tests

When contributing tests:

1. **Unit tests** - Test data models, utilities, and logic without network calls
2. **Integration tests** - Mark with `@pytest.mark.integration` decorator
3. **Documentation** - Add docstrings explaining what the test validates
4. **Assertions** - Use clear, descriptive assertion messages

Example:

```python
import pytest

def test_person_model():
    """Test Person model serialization"""
    person = Person(name="John Doe", location="New York")
    assert person.name == "John Doe"
    assert person.to_dict()["name"] == "John Doe"

@pytest.mark.integration
async def test_person_scraper_real():
    """Test actual LinkedIn profile scraping"""
    # Requires valid session
    async with BrowserManager() as browser:
        await browser.load_session("linkedin_session.json")
        scraper = PersonScraper(browser.page)
        person = await scraper.scrape("https://linkedin.com/in/...")
        assert person.name is not None
```

---

## ⚠️ Known Limitations

### LinkedIn Rate Limiting
Running integration tests multiple times in succession may trigger LinkedIn's rate limiting. If this happens:
- Wait 10-15 minutes before running tests again
- Use `pytest -m "not integration"` for development

### Session Expiration
LinkedIn sessions expire after a few hours. If integration tests fail with authentication errors:
```bash
# Refresh your session (see README for setup instructions)
```

### Browser Detection
LinkedIn actively blocks headless browsers:
- Tests run in headed mode (browser window opens)
- This is expected behavior for LinkedIn scrapers
- Headless mode will fail on real LinkedIn pages

---

## 📊 Continuous Integration

For CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run unit tests
  run: pytest -m "not integration" -v

# Integration tests should be run separately with secrets
- name: Run integration tests
  run: pytest -m integration -v
  env:
    LINKEDIN_SESSION: ${{ secrets.LINKEDIN_SESSION }}
```

---

## 🎓 Test Architecture

Tests are organized by component:

```
tests/
├── conftest.py          # Shared fixtures
├── test_auth.py         # Authentication tests
├── test_browser.py      # Browser management tests
├── test_person_scraper.py   # Person scraping tests
├── test_company_scraper.py  # Company scraping tests
└── test_job_scraper.py      # Job scraping tests
```

---

## 💡 Tips

1. **Fast feedback loop**: Use unit tests during development
   ```bash
   pytest -m "not integration" --tb=short
   ```

2. **Debug test failures**: Use `-s` flag to see print statements
   ```bash
   pytest tests/test_person_scraper.py -v -s
   ```

3. **Test one thing**: Run specific tests while debugging
   ```bash
   pytest tests/test_person_scraper.py::test_person_model_to_dict -v
   ```

---

## ✅ Contributing Tests

When submitting PRs:

1. Ensure all existing tests pass
2. Add tests for new functionality
3. Mark integration tests appropriately
4. Update this document if test structure changes

---

**Last Updated:** January 2026
