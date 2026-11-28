"""Semantic CLI exit codes and actionable error formatting."""

from typing import Any, Dict, Tuple

from ..core.exceptions import (
    AuthenticationError,
    ElementNotFoundError,
    NetworkError,
    ProfileNotFoundError,
    RateLimitError,
    ScrapingError,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_AUTH = 3
EXIT_RATE_LIMIT = 4
EXIT_NOT_FOUND = 5
EXIT_NETWORK = 6
EXIT_SCRAPING = 7
EXIT_PARTIAL = 8


class CliUsageError(ValueError):
    """Raised for invalid CLI arguments or malformed target URLs."""


def classify_error(exc: Exception) -> Tuple[int, Dict[str, Any]]:
    """Map an exception to (exit_code, structured_error_payload)."""
    message = str(exc)
    payload: Dict[str, Any] = {
        "error_type": type(exc).__name__,
        "message": message,
        "hint": None,
    }

    if isinstance(exc, CliUsageError):
        payload["hint"] = "Run with --help to see required arguments and URL formats."
        return EXIT_USAGE, payload

    if isinstance(exc, AuthenticationError):
        payload["hint"] = (
            "Refresh auth via `linkedin-scraper auth login --cookie <li_at>`, "
            "`linkedin-scraper auth login --env`, or interactive "
            "`linkedin-scraper auth login --manual`."
        )
        return EXIT_AUTH, payload

    if isinstance(exc, RateLimitError):
        wait = getattr(exc, "suggested_wait_time", 300)
        payload["suggested_wait_seconds"] = wait
        payload["hint"] = (
            f"LinkedIn rate-limited or challenged this session. Wait ~{wait}s before "
            "retrying and avoid rapid consecutive runs."
        )
        return EXIT_RATE_LIMIT, payload

    if isinstance(exc, (ProfileNotFoundError, ElementNotFoundError)):
        payload["hint"] = (
            "Verify the URL exists and is visible to the authenticated LinkedIn account."
        )
        return EXIT_NOT_FOUND, payload

    if isinstance(exc, NetworkError):
        if "Executable doesn't exist" in message or "playwright install" in message.lower():
            payload["hint"] = "Install Chromium for Playwright: `playwright install chromium`."
        else:
            payload["hint"] = "Check network connectivity or retry with `--headed`."
        return EXIT_NETWORK, payload

    if isinstance(exc, ScrapingError):
        payload["hint"] = (
            "If LinkedIn is blocking headless mode, retry with `--headed`. "
            "Otherwise LinkedIn's DOM may have changed."
        )
        return EXIT_SCRAPING, payload

    return EXIT_ERROR, payload


def format_error_text(payload: Dict[str, Any]) -> str:
    """Format a structured error payload for human/agent-readable stderr."""
    lines = [f"Error ({payload['error_type']}): {payload['message']}"]
    if payload.get("hint"):
        lines.append(f"Hint: {payload['hint']}")
    return "\n".join(lines)
