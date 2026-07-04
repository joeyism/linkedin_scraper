"""LinkedIn Scraper - Async Playwright-based scraper for LinkedIn."""

# Version
__version__ = "3.1.2"

# Core modules
from .core import (
    BrowserManager,
    login_with_credentials,
    login_with_cookie,
    is_logged_in,
    wait_for_manual_login,
    load_credentials_from_env,
    get_chrome_linkedin_cookies,
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
    CompanyPostsScraper,
    AvatarScraper,
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
    Interest,
    Company,
    CompanySummary,
    Employee,
    Job,
    Post,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "BrowserManager",
    "login_with_credentials",
    "login_with_cookie",
    "is_logged_in",
    "wait_for_manual_login",
    "load_credentials_from_env",
    "get_chrome_linkedin_cookies",
    # Scrapers
    "PersonScraper",
    "CompanyScraper",
    "JobScraper",
    "JobSearchScraper",
    "CompanyPostsScraper",
    "AvatarScraper",
    # Exceptions
    "LinkedInScraperException",
    "AuthenticationError",
    "RateLimitError",
    "ElementNotFoundError",
    "ProfileNotFoundError",
    "NetworkError",
    "ScrapingError",
    # Callbacks
    "ProgressCallback",
    "ConsoleCallback",
    "SilentCallback",
    "JSONLogCallback",
    "MultiCallback",
    # Models
    "Person",
    "Experience",
    "Education",
    "Contact",
    "Accomplishment",
    "Interest",
    "Company",
    "CompanySummary",
    "Employee",
    "Job",
    "Post",
]
