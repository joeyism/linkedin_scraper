"""Browser lifecycle management for Playwright."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from .exceptions import NetworkError

logger = logging.getLogger(__name__)


_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
    window.navigator.permissions.query = (parameters) =>
        parameters && parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
}
"""

_CHROMIUM_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
]


class BrowserManager:
    """Async context manager for Playwright browser lifecycle."""
    
    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        engine: str = "chromium",
        stealth: bool = True,
        **launch_options: Any
    ):
        """
        Initialize browser manager.
        
        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down operations by specified milliseconds
            viewport: Browser viewport size (default: 1280x720)
            user_agent: Custom user agent string
            engine: Browser engine to use ("chromium" or "firefox")
            stealth: Apply basic anti-bot-detection patches (default: True)
            **launch_options: Additional Playwright launch options
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        self.engine = engine
        self.stealth = stealth
        self.launch_options = launch_options
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_authenticated = False
        self._resolved_user_agent: Optional[str] = user_agent
    
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
            
            if self.engine not in ("chromium", "firefox", "webkit"):
                raise ValueError(
                    f"Unsupported engine '{self.engine}'. "
                    "Choose 'chromium', 'firefox' or 'webkit'."
                )
            
            browser_type = getattr(self._playwright, self.engine)
            
            launch_args: Dict[str, Any] = {
                "headless": self.headless,
                "slow_mo": self.slow_mo,
            }
            
            # Chromium exposes automation flags that anti-bot systems detect.
            if self.stealth and self.engine == "chromium":
                launch_args["args"] = list(_CHROMIUM_STEALTH_ARGS)
            
            launch_args.update(self.launch_options)
            
            self._browser = await browser_type.launch(**launch_args)
            
            logger.info(f"Browser launched (engine={self.engine}, headless={self.headless})")
            
            # Headless Chromium advertises "HeadlessChrome" in its UA, which is a
            # well-known bot signal. Present a normal Chrome UA unless the caller
            # supplied their own.
            if not self._resolved_user_agent and self.engine == "chromium":
                version = getattr(self._browser, "version", "") or ""
                self._resolved_user_agent = (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    f"(KHTML, like Gecko) Chrome/{version} Safari/537.36"
                )
            
            self._context = await self._create_context()
            
            # Create initial page
            self._page = await self._context.new_page()
            
            logger.info("Browser context and page created")
            
        except Exception as e:
            await self.close()
            raise NetworkError(f"Failed to start browser: {e}")
    
    async def _create_context(self, storage_state: Optional[str] = None) -> BrowserContext:
        """Create a browser context with consistent stealth settings."""
        if not self._browser:
            raise RuntimeError("Browser not started")
        
        context_options: Dict[str, Any] = {
            "viewport": self.viewport,
            "locale": "en-US",
        }
        
        if self._resolved_user_agent:
            context_options["user_agent"] = self._resolved_user_agent
        
        if storage_state:
            context_options["storage_state"] = storage_state
        
        context = await self._browser.new_context(**context_options)
        
        if self.stealth:
            await context.add_init_script(_STEALTH_INIT_SCRIPT)
        
        return context
    
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
        
        self._context = await self._create_context(storage_state=filepath)
        
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
