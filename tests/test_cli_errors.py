"""Unit tests for CLI exit codes and actionable error formatting."""
import pytest

from linkedin_scraper.cli.errors import (
    EXIT_AUTH,
    EXIT_NETWORK,
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_RATE_LIMIT,
    EXIT_SCRAPING,
    EXIT_USAGE,
    CliUsageError,
    classify_error,
    format_error_text,
)
from linkedin_scraper.core.exceptions import (
    AuthenticationError,
    ElementNotFoundError,
    NetworkError,
    ProfileNotFoundError,
    RateLimitError,
    ScrapingError,
)


@pytest.mark.unit
def test_classify_auth_error_includes_recovery_hint():
    code, payload = classify_error(AuthenticationError("Not logged in"))
    assert code == EXIT_AUTH
    assert payload["error_type"] == "AuthenticationError"
    assert "auth login" in payload["hint"]


@pytest.mark.unit
def test_classify_rate_limit_includes_wait_seconds():
    code, payload = classify_error(RateLimitError("Too many requests", suggested_wait_time=900))
    assert code == EXIT_RATE_LIMIT
    assert payload["suggested_wait_seconds"] == 900
    assert "900" in payload["hint"]


@pytest.mark.unit
def test_classify_not_found_errors():
    for exc in (ProfileNotFoundError("404"), ElementNotFoundError("missing")):
        code, payload = classify_error(exc)
        assert code == EXIT_NOT_FOUND
        assert payload["error_type"] == type(exc).__name__


@pytest.mark.unit
def test_classify_missing_playwright_browser_hint():
    exc = NetworkError("Failed to start browser: Executable doesn't exist at /cache/chromium")
    code, payload = classify_error(exc)
    assert code == EXIT_NETWORK
    assert "playwright install chromium" in payload["hint"]


@pytest.mark.unit
def test_classify_usage_and_scraping_errors():
    assert classify_error(CliUsageError("bad url"))[0] == EXIT_USAGE
    assert classify_error(ScrapingError("dom changed"))[0] == EXIT_SCRAPING
    assert EXIT_OK == 0


@pytest.mark.unit
def test_format_error_text_contains_message_and_hint():
    _, payload = classify_error(AuthenticationError("expired"))
    text = format_error_text(payload)
    assert "AuthenticationError" in text
    assert "expired" in text
    assert "Hint:" in text
