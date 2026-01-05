"""Custom exceptions for LinkedIn scraper."""


class LinkedInScraperException(Exception):
    """Base exception for LinkedIn scraper."""
    pass


class AuthenticationError(LinkedInScraperException):
    """Raised when authentication fails."""
    pass


class RateLimitError(LinkedInScraperException):
    """Raised when rate limiting is detected."""
    
    def __init__(self, message: str, suggested_wait_time: int = 300):
        super().__init__(message)
        self.suggested_wait_time = suggested_wait_time


class ElementNotFoundError(LinkedInScraperException):
    """Raised when an expected element is not found."""
    pass


class ProfileNotFoundError(LinkedInScraperException):
    """Raised when a profile/page returns 404."""
    pass


class NetworkError(LinkedInScraperException):
    """Raised when network-related issues occur."""
    pass


class ScrapingError(LinkedInScraperException):
    """Raised when scraping fails for various reasons."""
    pass
