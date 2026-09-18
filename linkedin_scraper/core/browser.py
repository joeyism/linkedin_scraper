"""Browser lifecycle management for Playwright."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import Browser, BrowserContext, Page

from .exceptions import NetworkError

try:
    from cloakbrowser import launch_async
    _cloak_import_error: Optional[ImportError] = None
except ImportError as e:
    launch_async = None  # type: ignore[assignment]
    _cloak_import_error = e

logger = logging.getLogger(__name__)


class BrowserManager:
    """Async context manager for Playwright browser lifecycle."""
    
    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        proxy: Optional[str] = None,
        geoip: bool = False,
        humanize: bool = False,
        fingerprint: Optional[str] = None,
        **launch_options: Any
    ):
        """
        Initialize browser manager.

        Args:
            headless: Run browser in headless mode
            slow_mo: Accepted for backwards compatibility but IGNORED by the
                CloakBrowser backend (CloakBrowser's launch API documents no
                slow_mo option). A debug log is emitted when non-zero.
            viewport: Browser viewport size (default: 1280x720)
            user_agent: Custom user agent string
            proxy: Proxy URL for CloakBrowser
                (e.g. "http://user:pass@residential-proxy:port",
                "socks5://..."). Passed as launch_async(proxy=...).
            geoip: Match timezone + locale to proxy IP
                (launch_async(geoip=...)).
            humanize: Human-like mouse, keyboard, scroll
                (launch_async(humanize=...)).
            fingerprint: Fixed fingerprint seed for a consistent identity
                (becomes args ["--fingerprint=<seed>"]). Default None means
                CloakBrowser auto-generates a fresh identity per launch.
            **launch_options: Additional CloakBrowser launch_async() options
                (e.g. args=[...]). Only options supported by cloakbrowser
                are guaranteed to work.
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        self.proxy = proxy
        self.geoip = geoip
        self.humanize = humanize
        self.fingerprint = fingerprint
        self.launch_options = launch_options

        # None under CloakBrowser backend (cloak manages Playwright internally).
        self._playwright: Optional[Any] = None
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
        """Start CloakBrowser and create context."""
        try:
            if launch_async is None:
                raise NetworkError(
                    "cloakbrowser is required but not installed: "
                    "pip install cloakbrowser && "
                    "python -m cloakbrowser install "
                    f"({_cloak_import_error})"
                )

            if self.slow_mo:
                logger.debug(
                    "slow_mo=%s is ignored by the CloakBrowser backend",
                    self.slow_mo,
                )

            launch_kwargs: Dict[str, Any] = {
                "headless": self.headless,
                "proxy": self.proxy,
                "geoip": self.geoip,
                "humanize": self.humanize,
            }
            launch_kwargs.update(self.launch_options)
            if self.fingerprint:
                launch_kwargs["args"] = [
                    *(launch_kwargs.get("args") or []),
                    f"--fingerprint={self.fingerprint}",
                ]
            # Drop None values so cloakbrowser defaults apply
            # (e.g. proxy=None must not override).
            launch_kwargs = {
                k: v for k, v in launch_kwargs.items() if v is not None
            }
            # headless/geoip/humanize are bools and never None;
            # they survive the filter above.

            self._browser = await launch_async(**launch_kwargs)

            logger.info(f"Browser launched (headless={self.headless})")

            # Create context — UNCHANGED from vanilla backend.
            context_options: Dict[str, Any] = {
                "viewport": self.viewport,
            }

            if self.user_agent:
                context_options["user_agent"] = self.user_agent

            self._context = await self._browser.new_context(**context_options)

            # Create initial page — UNCHANGED.
            self._page = await self._context.new_page()

            logger.info("Browser context and page created")

        except Exception as e:
            await self.close()
            if isinstance(e, NetworkError):
                raise
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
            
            if self._playwright is not None:
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
            raise RuntimeError("Browser not started. Use async context manager or call start().")
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
        
        with open(filepath, 'w') as f:
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
            storage_state=filepath,
            viewport=self.viewport,
            user_agent=self.user_agent
        )
        
        # Create new page
        if self._page:
            await self._page.close()
        self._page = await self._context.new_page()
        
        self._is_authenticated = True
        
        logger.info(f"Session loaded from {filepath}")
    
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
        """Check if user is authenticated."""
        return self._is_authenticated
    
    @is_authenticated.setter
    def is_authenticated(self, value: bool) -> None:
        """Set authentication status."""
        self._is_authenticated = value
