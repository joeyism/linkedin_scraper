"""Authentication functions for LinkedIn."""

import asyncio
import logging
import os
from typing import Optional, Tuple
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv

from .exceptions import AuthenticationError
from .utils import detect_rate_limit

logger = logging.getLogger(__name__)


async def warm_up_browser(page: Page) -> None:
    """
    Visit normal sites to gather cookies and appear more human-like.
    
    This helps avoid LinkedIn security checkpoints by establishing
    a normal browsing pattern before visiting LinkedIn.
    
    Args:
        page: Playwright page object
    """
    sites = [
        'https://www.google.com',
        'https://www.wikipedia.org',
        'https://www.github.com',
    ]
    
    logger.info("Warming up browser by visiting normal sites...")
    
    for site in sites:
        try:
            await page.goto(site, wait_until='domcontentloaded', timeout=10000)
            await asyncio.sleep(1)  # Brief pause
            logger.debug(f"Visited {site}")
        except Exception as e:
            logger.debug(f"Could not visit {site}: {e}")
            continue
    
    logger.info("Browser warm-up complete")


def load_credentials_from_env() -> Tuple[Optional[str], Optional[str]]:
    """
    Load LinkedIn credentials from .env file.
    
    Supports both LINKEDIN_EMAIL/LINKEDIN_USERNAME and LINKEDIN_PASSWORD.
    
    Returns:
        Tuple of (email, password) or (None, None) if not found
    """
    load_dotenv()
    
    # Support both LINKEDIN_EMAIL and LINKEDIN_USERNAME
    email = os.getenv('LINKEDIN_EMAIL') or os.getenv('LINKEDIN_USERNAME')
    password = os.getenv('LINKEDIN_PASSWORD')
    
    return email, password


async def login_with_credentials(
    page: Page,
    email: Optional[str] = None,
    password: Optional[str] = None,
    timeout: int = 30000,
    warm_up: bool = True
) -> None:
    """
    Login to LinkedIn using email and password.
    
    Args:
        page: Playwright page object
        email: LinkedIn email (if None, tries to load from .env)
        password: LinkedIn password (if None, tries to load from .env)
        timeout: Timeout in milliseconds
        warm_up: Whether to warm up browser by visiting normal sites first
        
    Raises:
        AuthenticationError: If login fails
    """
    # Load from .env if not provided
    if not email or not password:
        env_email, env_password = load_credentials_from_env()
        email = email or env_email
        password = password or env_password
    
    if not email or not password:
        raise AuthenticationError(
            "LinkedIn credentials not provided. "
            "Either pass email/password parameters or set LINKEDIN_EMAIL "
            "and LINKEDIN_PASSWORD in your .env file."
        )
    
    # Warm up browser first to appear more human-like
    if warm_up:
        await warm_up_browser(page)
    
    logger.info("Logging in to LinkedIn...")
    
    try:
        # Navigate to login page
        await page.goto('https://www.linkedin.com/login', wait_until='domcontentloaded')
        
        # Check for rate limiting
        await detect_rate_limit(page)
        
        # Wait for login form
        try:
            await page.wait_for_selector('#username', timeout=timeout, state='visible')
        except PlaywrightTimeoutError:
            raise AuthenticationError(
                "Login form not found. LinkedIn may have changed their page structure "
                "or the site is experiencing issues."
            )
        
        # Fill in credentials
        await page.fill('#username', email)
        await page.fill('#password', password)
        
        logger.debug("Credentials entered")
        
        # Click sign in button
        await page.click('button[type="submit"]')
        
        # Wait for navigation
        try:
            await page.wait_for_url(
                lambda url: 'feed' in url or 'checkpoint' in url or 'authwall' in url,
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            # Check if we're still on login page
            if 'login' in page.url:
                raise AuthenticationError(
                    "Login failed. Please check your credentials. "
                    "The page did not navigate after clicking sign in."
                )
        
        # Check for various post-login states
        current_url = page.url
        
        # Check for security checkpoint
        if 'checkpoint' in current_url or 'challenge' in current_url:
            raise AuthenticationError(
                "LinkedIn security checkpoint detected. "
                "You may need to verify your identity manually. "
                "Consider using session persistence after manual verification. "
                f"Current URL: {current_url}"
            )
        
        # Check for auth wall
        if 'authwall' in current_url:
            raise AuthenticationError(
                "Authentication wall encountered. "
                "LinkedIn may be blocking automated access. "
                f"Current URL: {current_url}"
            )
        
        # Verify we're logged in by checking for global nav
        try:
            await page.wait_for_selector(
                '.global-nav__primary-link, [data-control-name="nav.settings"]',
                timeout=5000,
                state='attached'
            )
            logger.info("✓ Successfully logged in to LinkedIn")
        except PlaywrightTimeoutError:
            # We might still be logged in, just can't find the nav element
            logger.warning(
                "Could not verify login by finding navigation element. "
                "Proceeding anyway..."
            )
    
    except PlaywrightTimeoutError as e:
        raise AuthenticationError(
            f"Login timed out: {e}. "
            "This could indicate network issues or LinkedIn blocking the request."
        )
    except Exception as e:
        if isinstance(e, AuthenticationError):
            raise
        raise AuthenticationError(f"Unexpected error during login: {e}")


async def login_with_cookie(page: Page, cookie_value: str) -> None:
    """
    Login to LinkedIn using li_at cookie.
    
    Args:
        page: Playwright page object
        cookie_value: Value of li_at cookie
        
    Raises:
        AuthenticationError: If cookie login fails
    """
    logger.info("Logging in with cookie...")
    
    try:
        # Set the cookie
        await page.context.add_cookies([{
            "name": "li_at",
            "value": cookie_value,
            "domain": ".linkedin.com",
            "path": "/"
        }])
        
        # Navigate to feed to verify
        await page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded')
        
        # Check if we're redirected to login (cookie invalid)
        if 'login' in page.url or 'authwall' in page.url:
            raise AuthenticationError(
                "Cookie authentication failed. The cookie may be expired or invalid."
            )
        
        # Verify login by checking for nav element
        try:
            await page.wait_for_selector(
                '.global-nav__primary-link, [data-control-name="nav.settings"]',
                timeout=5000,
                state='attached'
            )
            logger.info("✓ Successfully authenticated with cookie")
        except PlaywrightTimeoutError:
            logger.warning(
                "Could not verify cookie login. "
                "Proceeding anyway..."
            )
    
    except Exception as e:
        if isinstance(e, AuthenticationError):
            raise
        raise AuthenticationError(f"Cookie authentication error: {e}")


async def is_logged_in(page: Page) -> bool:
    """
    Check if currently logged in to LinkedIn.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if logged in, False otherwise
    """
    try:
        # Check for global nav which only appears when logged in
        count = await page.locator('.global-nav__primary-link, [data-control-name="nav.settings"]').count()
        return count > 0
    except Exception:
        return False


async def wait_for_manual_login(page: Page, timeout: int = 300000) -> None:
    """
    Wait for user to manually complete login (useful for 2FA, CAPTCHA, etc.).
    
    Args:
        page: Playwright page object
        timeout: Timeout in milliseconds (default: 5 minutes)
        
    Raises:
        AuthenticationError: If timeout or login not completed
    """
    logger.info(
        "⏳ Please complete the login process manually in the browser. "
        "Waiting up to 5 minutes..."
    )
    
    start_time = asyncio.get_event_loop().time()
    
    while True:
        # Check if logged in
        if await is_logged_in(page):
            logger.info("✓ Manual login completed successfully")
            return
        
        # Check timeout
        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        if elapsed > timeout:
            raise AuthenticationError(
                "Manual login timeout. Please try again and complete login faster."
            )
        
        # Wait a bit before checking again
        await asyncio.sleep(1)
