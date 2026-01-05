"""Utility functions for scraping operations."""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, TypeVar, cast
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .exceptions import RateLimitError, ElementNotFoundError, NetworkError

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_async(
    max_attempts: int = 3,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for async functions to add retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff: Backoff multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff ** attempt
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}"
                        )
            raise last_exception
        return wrapper
    return decorator


async def detect_rate_limit(page: Page) -> None:
    """
    Detect if LinkedIn has rate limited the session.
    
    Args:
        page: Playwright page object
        
    Raises:
        RateLimitError: If rate limiting is detected
    """
    # Check for common rate limit indicators
    
    # Check URL for security challenges
    current_url = page.url
    if 'linkedin.com/checkpoint' in current_url or 'authwall' in current_url:
        raise RateLimitError(
            "LinkedIn security checkpoint detected. "
            "You may need to verify your identity or wait before continuing.",
            suggested_wait_time=3600  # 1 hour
        )
    
    # Check for CAPTCHA
    try:
        captcha = await page.locator('iframe[title*="captcha" i], iframe[src*="captcha" i]').count()
        if captcha > 0:
            raise RateLimitError(
                "CAPTCHA challenge detected. Manual intervention required.",
                suggested_wait_time=3600
            )
    except Exception:
        pass
    
    # Check for rate limit messages
    try:
        body_text = await page.locator('body').text_content(timeout=1000)
        if body_text:
            body_lower = body_text.lower()
            if any(phrase in body_lower for phrase in [
                'too many requests',
                'rate limit',
                'slow down',
                'try again later'
            ]):
                raise RateLimitError(
                    "Rate limit message detected on page.",
                    suggested_wait_time=1800  # 30 minutes
                )
    except PlaywrightTimeoutError:
        pass


async def wait_for_element_smart(
    page: Page,
    selector: str,
    timeout: float = 5000,
    state: str = "visible",
    error_context: Optional[str] = None
) -> None:
    """
    Wait for an element with better error messages.
    
    Args:
        page: Playwright page object
        selector: CSS selector or text selector
        timeout: Timeout in milliseconds
        state: Element state to wait for (visible, attached, hidden, detached)
        error_context: Additional context for error message
        
    Raises:
        ElementNotFoundError: If element is not found with helpful context
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout, state=state)
    except PlaywrightTimeoutError:
        context = f" when {error_context}" if error_context else ""
        suggestions = _get_selector_suggestions(selector)
        
        raise ElementNotFoundError(
            f"Could not find element with selector '{selector}'{context}. "
            f"This may indicate:\n"
            f"  • The page structure has changed\n"
            f"  • The profile has restricted visibility\n"
            f"  • The content doesn't exist on this page\n"
            f"  • Network slowness (try increasing timeout)\n"
            f"{suggestions}"
        )


def _get_selector_suggestions(selector: str) -> str:
    """Get helpful suggestions based on selector type."""
    if '#' in selector:
        return "Tip: ID selectors may be dynamic. Consider using data attributes or text content."
    elif 'pv-' in selector or 'artdeco' in selector:
        return "Tip: LinkedIn class names change frequently. This selector may need updating."
    return ""


async def extract_text_safe(
    page: Page,
    selector: str,
    default: str = "",
    timeout: float = 2000
) -> str:
    """
    Safely extract text from an element, returning default if not found.
    
    Args:
        page: Playwright page object
        selector: CSS selector
        default: Default value if element not found
        timeout: Timeout in milliseconds
        
    Returns:
        Extracted text or default value
    """
    try:
        element = page.locator(selector).first
        text = await element.text_content(timeout=timeout)
        return text.strip() if text else default
    except PlaywrightTimeoutError:
        logger.debug(f"Element not found: {selector}, returning default: {default}")
        return default
    except Exception as e:
        logger.debug(f"Error extracting text from {selector}: {e}")
        return default


async def scroll_to_bottom(page: Page, pause_time: float = 1.0, max_scrolls: int = 10) -> None:
    """
    Scroll to the bottom of the page smoothly with pauses.
    
    Args:
        page: Playwright page object
        pause_time: Time to pause between scrolls (seconds)
        max_scrolls: Maximum number of scroll attempts
    """
    for i in range(max_scrolls):
        # Get current scroll position
        previous_height = await page.evaluate('document.body.scrollHeight')
        
        # Scroll down
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(pause_time)
        
        # Check if we've reached the bottom
        new_height = await page.evaluate('document.body.scrollHeight')
        if new_height == previous_height:
            logger.debug(f"Reached bottom after {i + 1} scrolls")
            break


async def scroll_to_half(page: Page) -> None:
    """Scroll to middle of page."""
    await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')


async def click_see_more_buttons(page: Page, max_attempts: int = 10) -> int:
    """
    Click all 'Show more' / 'See more' buttons on the page.
    
    Args:
        page: Playwright page object
        max_attempts: Maximum number of buttons to click
        
    Returns:
        Number of buttons clicked
    """
    clicked = 0
    for _ in range(max_attempts):
        try:
            # Look for common "see more" button patterns
            see_more = page.locator('button:has-text("See more"), button:has-text("Show more"), button:has-text("show all")').first
            
            if await see_more.is_visible(timeout=1000):
                await see_more.click()
                await asyncio.sleep(0.5)  # Wait for content to load
                clicked += 1
            else:
                break
        except:
            break
    
    if clicked > 0:
        logger.debug(f"Clicked {clicked} 'see more' buttons")
    
    return clicked


async def handle_modal_close(page: Page) -> bool:
    """
    Close any popup modals that might be blocking content.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if a modal was closed, False otherwise
    """
    try:
        # Look for common close button patterns
        close_button = page.locator(
            'button[aria-label="Dismiss"], '
            'button[aria-label="Close"], '
            'button.artdeco-modal__dismiss'
        ).first
        
        if await close_button.is_visible(timeout=1000):
            await close_button.click()
            await asyncio.sleep(0.5)
            logger.debug("Closed modal")
            return True
    except:
        pass
    
    return False


async def is_page_loaded(page: Page) -> bool:
    """
    Check if page has finished loading.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if page is loaded
    """
    try:
        state = await page.evaluate('document.readyState')
        return state == 'complete'
    except:
        return False
