"""LinkedIn Scraper - Async Playwright-based scraper for LinkedIn."""

# Version
__version__ = "3.0.1"

# Core modules
from .core import (
    BrowserManager,
    login_with_credentials,
    login_with_cookie,
    is_logged_in,
    wait_for_manual_login,
    load_credentials_from_env,
    # Exceptions
    LinkedInScraperException,
    AuthenticationError,
    RateLimitError,
    ElementNotFoundError,
    ProfileNotFoundError,
    NetworkError,
    ScrapingError,
)

# Scrapers
from .scrapers import (
    PersonScraper,
    CompanyScraper,
    JobScraper,
    JobSearchScraper,
)

# Callbacks
from .callbacks import (
    ProgressCallback,
    ConsoleCallback,
    SilentCallback,
    JSONLogCallback,
    MultiCallback,
)

# Models
from .models import (
    Person,
    Experience,
    Education,
    Contact,
    Accomplishment,
    Company,
    CompanySummary,
    Employee,
    Job,
)

__all__ = [
    # Version
    '__version__',
    # Core
    'BrowserManager',
    'login_with_credentials',
    'login_with_cookie',
    'is_logged_in',
    'wait_for_manual_login',
    'load_credentials_from_env',
    # Scrapers
    'PersonScraper',
    'CompanyScraper',
    'JobScraper',
    'JobSearchScraper',
    # Exceptions
    'LinkedInScraperException',
    'AuthenticationError',
    'RateLimitError',
    'ElementNotFoundError',
    'ProfileNotFoundError',
    'NetworkError',
    'ScrapingError',
    # Callbacks
    'ProgressCallback',
    'ConsoleCallback',
    'SilentCallback',
    'JSONLogCallback',
    'MultiCallback',
    # Models
    'Person',
    'Experience',
    'Education',
    'Contact',
    'Accomplishment',
    'Company',
    'CompanySummary',
    'Employee',
    'Job',
]
