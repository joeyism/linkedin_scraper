"""Browser lifecycle management for Playwright."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)

from .exceptions import NetworkError

logger = logging.getLogger(__name__)


class BrowserManager:
    """Async context manager for Playwright browser lifecycle."""

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        **launch_options: Any,
    ):
        """
        Initialize browser manager.

        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down operations by specified milliseconds
            viewport: Browser viewport size (default: 1280x720)
            user_agent: Custom user agent string
            **launch_options: Additional Playwright launch options
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        self.launch_options = launch_options

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_authenticated = False

    async def __aenter__(self) -> "BrowserManager":
        """Start browser and create context."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close browser and cleanup."""
        await self.close()

    async def start(self) -> None:
        """Start Playwright and launch browser."""
        try:
            self._playwright = await async_playwright().start()

            # Launch browser
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless, slow_mo=self.slow_mo, **self.launch_options
            )

            logger.info(f"Browser launched (headless={self.headless})")

            # Create context
            context_options: Dict[str, Any] = {
                "viewport": self.viewport,
            }

            if self.user_agent:
                context_options["user_agent"] = self.user_agent

            self._context = await self._browser.new_context(**context_options)

            # Create initial page
            self._page = await self._context.new_page()

            logger.info("Browser context and page created")

        except Exception as e:
            await self.close()
            raise NetworkError(f"Failed to start browser: {e}")

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        try:
            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            logger.info("Browser closed")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def new_page(self) -> Page:
        """
        Create a new page in the current context.

        Returns:
            New Playwright page
        """
        if not self._context:
            raise RuntimeError("Browser context not initialized. Call start() first.")

        page = await self._context.new_page()
        return page

    @property
    def page(self) -> Page:
        """
        Get the main page.

        Returns:
            Main Playwright page
        """
        if not self._page:
            raise RuntimeError(
                "Browser not started. Use async context manager or call start()."
            )
        return self._page

    @property
    def context(self) -> BrowserContext:
        """
        Get the browser context.

        Returns:
            Playwright browser context
        """
        if not self._context:
            raise RuntimeError("Browser context not initialized.")
        return self._context

    @property
    def browser(self) -> Browser:
        """
        Get the browser instance.

        Returns:
            Playwright browser
        """
        if not self._browser:
            raise RuntimeError("Browser not started.")
        return self._browser

    async def save_session(self, filepath: str) -> None:
        """
        Save browser session (cookies and storage) to file.

        Args:
            filepath: Path to save session file
        """
        if not self._context:
            raise RuntimeError("No browser context to save")

        storage_state = await self._context.storage_state()

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(storage_state, f, indent=2)

        logger.info(f"Session saved to {filepath}")

    async def load_session(self, filepath: str) -> None:
        """
        Load browser session from file.

        Args:
            filepath: Path to session file
        """
        if not Path(filepath).exists():
            raise FileNotFoundError(f"Session file not found: {filepath}")

        # Close existing context and create new one with stored state
        if self._context:
            await self._context.close()

        if not self._browser:
            raise RuntimeError("Browser not started")

        self._context = await self._browser.new_context(
            storage_state=filepath, viewport=self.viewport, user_agent=self.user_agent
        )

        # Create new page
        if self._page:
            await self._page.close()
        self._page = await self._context.new_page()

        self._is_authenticated = True

        logger.info(f"Session loaded from {filepath}")

    async def set_cookie(
        self, name: str, value: str, domain: str = ".linkedin.com"
    ) -> None:
        """
        Set a single cookie.

        Args:
            name: Cookie name
            value: Cookie value
            domain: Cookie domain
        """
        if not self._context:
            raise RuntimeError("No browser context")

        await self._context.add_cookies(
            [{"name": name, "value": value, "domain": domain, "path": "/"}]
        )

        logger.debug(f"Cookie set: {name}")

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self._is_authenticated

    @is_authenticated.setter
    def is_authenticated(self, value: bool) -> None:
        """Set authentication status."""
        self._is_authenticated = value


class PersistentBrowserManager:
    """
    Browser manager using Playwright's persistent context.

    Unlike BrowserManager, this uses launch_persistent_context() which
    automatically persists browser state (cookies, localStorage, etc) to
    a user data directory. No manual save/load needed.

    This approach:
    - Works like a real Chrome profile
    - Automatically saves cookies and session data
    - Is more resistant to anti-bot detection
    - Eliminates manual session.json management
    - Better suited for long-running services containers

    Usage:
        async with PersistentBrowserManager(user_data_dir="~/.linkedin/profile") as browser:
            await browser.page.goto("https://linkedin.com")
            # Cookies automatically saved on close

    Args:
        user_data_dir: Path to browser profile directory (created if doesn't exist)
        headless: Run browser in headless mode
        slow_mo: Slow down operations by specified milliseconds
        viewport: Browser viewport size (default: 1280x720)
        user_agent: Custom user agent string
        **launch_options: Additional Playwright context options
    """

    def __init__(
        self,
        user_data_dir: str | Path,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        **launch_options: Any,
    ):
        """Initialize persistent browser manager."""
        self.user_data_dir = Path(user_data_dir).expanduser()
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        self.launch_options = launch_options

        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_authenticated = False

    async def __aenter__(self) -> "PersistentBrowserManager":
        """Start browser and create persistent context."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close browser - state automatically persists to user_data_dir."""
        await self.close()

    async def start(self) -> None:
        """Launch persistent browser context."""
        try:
            # Ensure parent directory exists
            self.user_data_dir.parent.mkdir(parents=True, exist_ok=True)

            self._playwright = await async_playwright().start()

            # Build context options
            context_options: Dict[str, Any] = {
                "headless": self.headless,
                "slow_mo": self.slow_mo,
                "viewport": self.viewport,
                "locale": "en-US",
                "timezone_id": "America/New_York",
                **self.launch_options,
            }

            if self.user_agent:
                context_options["user_agent"] = self.user_agent

            # KEY DIFFERENCE: launch_persistent_context instead of launch + new_context
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(self.user_data_dir), **context_options
            )

            logger.info(
                f"Persistent browser context launched "
                f"(headless={self.headless}, profile={self.user_data_dir})"
            )

            # Reuse existing page or create new one
            if self._context.pages:
                self._page = self._context.pages[0]
                logger.info("Reusing existing page from persistent context")
            else:
                self._page = await self._context.new_page()
                logger.info("Created new page in persistent context")

        except Exception as e:
            await self.close()
            # Provide helpful error messages for common issues
            error_msg = str(e).lower()
            if "already in use" in error_msg or "already running" in error_msg:
                raise RuntimeError(
                    f"Profile directory '{self.user_data_dir}' is already in use "
                    "by another browser instance. Close other instances or use "
                    "a different profile directory."
                ) from e
            elif "cannot create" in error_msg or "permission denied" in error_msg:
                raise RuntimeError(
                    f"Cannot create or access profile directory '{self.user_data_dir}'. "
                    "Check file permissions."
                ) from e
            else:
                raise NetworkError(f"Failed to start persistent browser: {e}") from e

    async def close(self) -> None:
        """Close browser - state automatically persists to user_data_dir."""
        try:
            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            logger.info(
                f"Persistent browser closed "
                f"(profile saved to {self.user_data_dir})"
            )

        except Exception as e:
            logger.error(f"Error closing persistent browser: {e}")

    async def new_page(self) -> Page:
        """
        Create a new page in the current persistent context.

        Returns:
            New Playwright page
        """
        if not self._context:
            raise RuntimeError("Browser context not initialized. Call start() first.")

        page = await self._context.new_page()
        return page

    @property
    def page(self) -> Page:
        """
        Get the main page - compatible with existing scraper classes.

        Returns:
            Main Playwright page
        """
        if not self._page:
            raise RuntimeError(
                "Browser not started. Use async context manager or call start()."
            )
        return self._page

    @property
    def context(self) -> BrowserContext:
        """
        Get the browser context.

        Returns:
            Playwright browser context
        """
        if not self._context:
            raise RuntimeError("Browser context not initialized.")
        return self._context

    @property
    def browser(self) -> Browser:
        """
        Get the browser instance.

        Note: For persistent contexts, this returns None as Playwright doesn't
        expose a separate Browser object. Use context and page instead.

        Returns:
            None (persistent contexts don't have a separate browser object)
        """
        # Persistent contexts don't expose a browser object
        # This is fine - scrapers only need the page property
        return None  # type: ignore

    async def set_cookie(
        self, name: str, value: str, domain: str = ".linkedin.com"
    ) -> None:
        """
        Set a single cookie.

        Args:
            name: Cookie name
            value: Cookie value
            domain: Cookie domain
        """
        if not self._context:
            raise RuntimeError("No browser context")

        await self._context.add_cookies(
            [{"name": name, "value": value, "domain": domain, "path": "/"}]
        )

        logger.debug(f"Cookie set: {name}")

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self._is_authenticated

    @is_authenticated.setter
    def is_authenticated(self, value: bool) -> None:
        """Set authentication status."""
        self._is_authenticated = value

    def clear_profile(self) -> None:
        """
        Delete the persistent browser profile directory.

        WARNING: This will log you out and delete all saved session data.
        The browser must be closed before calling this method.

        Raises:
            RuntimeError: If browser is still running
        """
        if self._context is not None:
            raise RuntimeError(
                "Cannot clear profile while browser is running. "
                "Close the browser first with close() or exit the context manager."
            )

        if self.user_data_dir.exists():
            import shutil

            shutil.rmtree(self.user_data_dir)
            logger.info(f"Cleared profile directory: {self.user_data_dir}")
        else:
            logger.warning(f"Profile directory does not exist: {self.user_data_dir}")


async def migrate_session_to_profile(
    session_path: str | Path, user_data_dir: str | Path, headless: bool = True
) -> bool:
    """
    Migrate from session.json to persistent browser profile.

    Loads cookies from a session.json file created with BrowserManager
    and saves them to a persistent browser context. This allows you
    to migrate from manual session management to automatic persistence.

    Args:
        session_path: Path to existing session.json file
        user_data_dir: Path for new persistent browser profile
        headless: Run migration in headless mode

    Returns:
        True if migration successful and login verified, False otherwise

    Example:
        success = await migrate_session_to_profile(
            session_path="session.json",
            user_data_dir="~/.linkedin/profile"
        )
        if success:
            os.remove("session.json")  # Clean up old session file

    Raises:
        FileNotFoundError: If session_path doesn't exist
    """
    session_path = Path(session_path)
    if not session_path.exists():
        raise FileNotFoundError(f"Session file not found: {session_path}")

    logger.info(f"Migrating session from {session_path} to {user_data_dir}")

    # Load old session with BrowserManager
    old_browser = BrowserManager(headless=headless)
    await old_browser.start()

    try:
        await old_browser.load_session(str(session_path))
        logger.info("Loaded session from session.json")

        # Get storage state (cookies + localStorage)
        storage_state = await old_browser.context.storage_state()

        # Close old browser
        await old_browser.close()

        # Create persistent context
        new_browser = PersistentBrowserManager(
            user_data_dir=user_data_dir, headless=headless
        )
        await new_browser.start()

        try:
            # Import cookies into persistent profile
            if storage_state.get("cookies"):
                await new_browser.context.add_cookies(storage_state["cookies"])
                logger.info(f"Migrated {len(storage_state['cookies'])} cookies")

            # Verify by navigating to LinkedIn
            await new_browser.page.goto("https://www.linkedin.com/feed/")
            await asyncio.sleep(2)  # Wait for page to load

            # Check if we're logged in by looking for feed URL
            current_url = new_browser.page.url
            success = "/feed" in current_url or "linkedin.com/in/" in current_url

            if success:
                logger.info("Migration successful - login verified")
            else:
                logger.warning("Migration completed but login verification failed")

            await new_browser.close()
            return success

        except Exception as e:
            logger.error(f"Error during migration to persistent profile: {e}")
            await new_browser.close()
            return False

    except Exception as e:
        logger.error(f"Error loading session file: {e}")
        await old_browser.close()
        return False
