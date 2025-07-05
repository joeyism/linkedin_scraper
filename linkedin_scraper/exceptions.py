"""
Custom exceptions for LinkedIn scraper.

This module defines specific exception types for different error scenarios
to provide better error handling and reporting.
"""


class LinkedInScraperError(Exception):
    """Base exception for LinkedIn scraper."""

    pass


class LoginError(LinkedInScraperError):
    """Base login error."""

    pass


class CredentialsNotFoundError(LoginError):
    """No credentials available in non-interactive mode."""

    pass


class InvalidCredentialsError(LoginError):
    """Invalid email/password combination."""

    pass


class CaptchaRequiredError(LoginError):
    """LinkedIn requires captcha verification."""

    def __init__(self, captcha_url: str | None = None) -> None:
        self.captcha_url = captcha_url
        super().__init__(f"Captcha required: {captcha_url}")


class TwoFactorAuthError(LoginError):
    """Two-factor authentication required."""

    pass


class RateLimitError(LoginError):
    """Too many login attempts."""

    pass


class SecurityChallengeError(LoginError):
    """LinkedIn security challenge required."""

    def __init__(
        self, challenge_url: str | None = None, message: str | None = None
    ) -> None:
        self.challenge_url = challenge_url
        self.message = message
        super().__init__(f"Security challenge required: {message or challenge_url}")


class LoginTimeoutError(LoginError):
    """Login process timed out."""

    pass


class DriverInitializationError(LinkedInScraperError):
    """Failed to initialize Chrome WebDriver."""

    pass
