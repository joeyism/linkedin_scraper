"""Tests for core utility functions."""
import pytest

from linkedin_scraper.core.exceptions import RateLimitError
from linkedin_scraper.core.utils import detect_rate_limit


class _FakeLocator:
    def __init__(self, count: int):
        self._count = count

    async def count(self) -> int:
        return self._count


class _FakePage:
    """Minimal stand-in for a Playwright page."""

    def __init__(self, url: str, visible_text: str = "", captcha: int = 0, evaluate_error: bool = False):
        self.url = url
        self._visible_text = visible_text
        self._captcha = captcha
        self._evaluate_error = evaluate_error

    def locator(self, selector: str) -> _FakeLocator:
        if "captcha" in selector:
            return _FakeLocator(self._captcha)
        return _FakeLocator(0)

    async def evaluate(self, script: str) -> str:
        if self._evaluate_error:
            raise RuntimeError("evaluation failed")
        return self._visible_text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_ignores_script_payload():
    """Generic error strings inside page JSON must not trigger a rate limit."""
    page = _FakePage(
        url="https://www.linkedin.com/in/someone/",
        visible_text="Bill Gates | Chair, Gates Foundation",
    )
    await detect_rate_limit(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_detects_visible_message():
    page = _FakePage(
        url="https://www.linkedin.com/feed/",
        visible_text="Too many requests. Please slow down.",
    )
    with pytest.raises(RateLimitError):
        await detect_rate_limit(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_detects_checkpoint_url():
    page = _FakePage(url="https://www.linkedin.com/checkpoint/challenge/123")
    with pytest.raises(RateLimitError):
        await detect_rate_limit(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_detects_captcha():
    page = _FakePage(url="https://www.linkedin.com/feed/", captcha=1)
    with pytest.raises(RateLimitError):
        await detect_rate_limit(page)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_detect_rate_limit_survives_evaluate_failure():
    page = _FakePage(url="https://www.linkedin.com/feed/", evaluate_error=True)
    await detect_rate_limit(page)
