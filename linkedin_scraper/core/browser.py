"""Browser lifecycle management using Patchright with persistent context."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union
from patchright.async_api import async_playwright, BrowserContext, Page, Playwright

from .exceptions import NetworkError

logger = logging.getLogger(__name__)

_DEFAULT_USER_DATA_DIR = Path.home() / ".linkedin_scraper" / "browser_data"


class BrowserManager:
    """Async context manager for Patchright browser with persistent profile.

    Session persistence is handled automatically by the persistent browser
    context — all cookies, localStorage, and session state are retained in
    the ``user_data_dir`` between runs. No explicit save/load is needed.
    """

    def __init__(
        self,
        user_data_dir: Union[str, Path] = _DEFAULT_USER_DATA_DIR,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        **launch_options: Any
    ):
        """
        Initialize browser manager with persistent context.

        Args:
            user_data_dir: Path to Chromium user data directory (persistent profile).
                Defaults to ``~/.linkedin_scraper/browser_data``.
            headless: Run browser in headless mode
            slow_mo: Slow down operations by specified milliseconds
            viewport: Browser viewport size (default: 1280x720)
            user_agent: Custom user agent string
            **launch_options: Additional Patchright launch options
        """
        self.user_data_dir = str(Path(user_data_dir).expanduser())
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        self.launch_options = launch_options

        self._playwright: Optional[Playwright] = None
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
        """Start Patchright and launch persistent browser context."""
        try:
            self._playwright = await async_playwright().start()

            # Ensure user data dir exists
            Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)

            # Build context options
            context_options: Dict[str, Any] = {
                "headless": self.headless,
                "slow_mo": self.slow_mo,
                "viewport": self.viewport,
                **self.launch_options,
            }

            if self.user_agent:
                context_options["user_agent"] = self.user_agent

            # Launch persistent context (combines browser + context)
            self._context = await self._playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                **context_options,
            )

            logger.info(
                f"Persistent browser launched (headless={self.headless}, "
                f"user_data_dir={self.user_data_dir})"
            )

            # Use existing page or create one
            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = await self._context.new_page()

            logger.info("Browser context and page ready")

        except Exception as e:
            await self.close()
            raise NetworkError(f"Failed to start browser: {e}")

    async def close(self) -> None:
        """Close persistent context and cleanup resources."""
        try:
            if self._context:
                await self._context.close()
                self._context = None
                self._page = None

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
            New Patchright page
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
            Main Patchright page
        """
        if not self._page:
            raise RuntimeError("Browser not started. Use async context manager or call start().")
        return self._page

    @property
    def context(self) -> BrowserContext:
        """
        Get the browser context.

        Returns:
            Patchright browser context
        """
        if not self._context:
            raise RuntimeError("Browser context not initialized.")
        return self._context

    async def set_cookie(self, name: str, value: str, domain: str = ".linkedin.com") -> None:
        """
        Set a single cookie.

        Args:
            name: Cookie name
            value: Cookie value
            domain: Cookie domain
        """
        if not self._context:
            raise RuntimeError("No browser context")

        await self._context.add_cookies([{
            "name": name,
            "value": value,
            "domain": domain,
            "path": "/"
        }])

        logger.debug(f"Cookie set: {name}")

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated (tracked state, not a live check)."""
        return self._is_authenticated

    @is_authenticated.setter
    def is_authenticated(self, value: bool) -> None:
        """Set authentication status."""
        self._is_authenticated = value

    def _default_cookie_path(self) -> Path:
        """Get default cookie file path (parent of user_data_dir)."""
        return Path(self.user_data_dir).parent / "cookies.json"

    @staticmethod
    def _normalize_cookie_domain(cookie: dict) -> dict:
        """Normalize cookie domain for cross-platform compatibility.

        Playwright reports some LinkedIn cookies with ``.www.linkedin.com``
        domain, but Chromium's internal store uses ``.linkedin.com``. This
        mismatch causes cookies to not be sent on Linux after import.
        """
        domain = cookie.get("domain", "")
        if domain in (".www.linkedin.com", "www.linkedin.com"):
            cookie = {**cookie, "domain": ".linkedin.com"}
        return cookie

    async def export_cookies(self, cookie_path: Optional[Union[str, Path]] = None) -> bool:
        """
        Export cookies from browser context to a portable JSON file.

        Enables cross-platform profile portability — Chromium encrypts cookies
        with OS-specific keys, so the JSON file bridges macOS and Linux Docker.

        Only exports LinkedIn-domain cookies with normalized domains so they
        work correctly when imported on a different platform.

        Args:
            cookie_path: Path to cookie file. Defaults to ``{user_data_dir}/../cookies.json``.

        Returns:
            True if export succeeded
        """
        if not self._context:
            logger.warning("Cannot export cookies: no browser context")
            return False

        path = Path(cookie_path) if cookie_path else self._default_cookie_path()
        try:
            all_cookies = await self._context.cookies()
            # Filter to LinkedIn cookies and normalize domains
            cookies = [
                self._normalize_cookie_domain(c) for c in all_cookies
                if "linkedin.com" in c.get("domain", "")
            ]
            path.write_text(json.dumps(cookies, indent=2))
            logger.info("Exported %d LinkedIn cookies to %s", len(cookies), path)
            return True
        except Exception:
            logger.exception("Failed to export cookies")
            return False

    # Auth cookies to import — everything else is regenerated fresh by the
    # server, avoiding conflicts with anti-bot (PerimeterX, Cloudflare) and
    # datacenter routing cookies that are tied to the original session.
    _AUTH_COOKIE_NAMES = frozenset({"li_at", "li_rm"})

    async def import_cookies(self, cookie_path: Optional[Union[str, Path]] = None) -> bool:
        """
        Import auth cookies from a portable JSON file into the browser context.

        Only imports essential authentication cookies (``li_at``, ``li_rm``).
        All other cookies (anti-bot, routing, session IDs) are left for the
        server to regenerate fresh, preventing redirect loops caused by stale
        or platform-mismatched bot-detection state.

        Args:
            cookie_path: Path to cookie file. Defaults to ``{user_data_dir}/../cookies.json``.

        Returns:
            True if cookies were imported
        """
        if not self._context:
            logger.warning("Cannot import cookies: no browser context")
            return False

        path = Path(cookie_path) if cookie_path else self._default_cookie_path()
        if not path.exists():
            logger.debug("No portable cookie file at %s", path)
            return False

        try:
            all_cookies = json.loads(path.read_text())
            if not all_cookies:
                logger.debug("Cookie file is empty")
                return False

            # Only import auth cookies with normalized domains
            cookies = [
                self._normalize_cookie_domain(c) for c in all_cookies
                if c.get("name") in self._AUTH_COOKIE_NAMES
            ]
            if not cookies:
                logger.warning("No auth cookies (li_at/li_rm) found in %s", path)
                return False

            # Clear undecryptable cookies from the persistent store first.
            # On cross-platform (macOS profile on Linux), Chromium loads
            # encrypted cookie entries it can't decrypt — these shadow any
            # cookies we import via CDP and prevent them from being sent.
            await self._context.clear_cookies()
            await self._context.add_cookies(cookies)
            logger.info(
                "Imported %d auth cookies from %s: %s",
                len(cookies), path,
                ", ".join(c["name"] for c in cookies),
            )
            return True
        except Exception:
            logger.exception("Failed to import cookies from %s", path)
            return False

    def cookie_file_exists(self, cookie_path: Optional[Union[str, Path]] = None) -> bool:
        """Check if a portable cookie file exists."""
        path = Path(cookie_path) if cookie_path else self._default_cookie_path()
        return path.exists()
