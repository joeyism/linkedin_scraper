"""Browser lifecycle management for Playwright."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

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
        proxy: Optional[Dict[str, str]] = None,
        block_resources: Optional[list] = None,
        **launch_options: Any
    ):
        """
        Initialize browser manager.
        
        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down operations by specified milliseconds
            viewport: Browser viewport size (default: 1280x720)
            user_agent: Custom user agent string
            proxy: Proxy configuration dict with 'server', 'username', 'password'
                   Example: {"server": "http://proxy.example.com:8080",
                            "username": "user", "password": "pass"}
            block_resources: List of resource types to block
                   Options: 'image', 'stylesheet', 'font', 'media', 'websocket', 'manifest', 'other'
                   Example: ['image', 'stylesheet'] to block images and CSS
                   For JavaScript only: ['image', 'stylesheet', 'font', 'media', 'websocket', 'manifest', 'other']
            **launch_options: Additional Playwright launch options
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        self.proxy = proxy
        self.block_resources = block_resources or []
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
                headless=self.headless,
                slow_mo=self.slow_mo,
                **self.launch_options
            )
            
            logger.info(f"Browser launched (headless={self.headless})")
            
            # Create context
            context_options: Dict[str, Any] = {
                "viewport": self.viewport,
            }
            
            if self.user_agent:
                context_options["user_agent"] = self.user_agent
            
            if self.proxy:
                context_options["proxy"] = self.proxy

            self._context = await self._browser.new_context(**context_options)
            
            # Create initial page
            self._page = await self._context.new_page()
            
            # Set up resource blocking if configured
            if self.block_resources:
                await self._setup_resource_blocking(self._page)

            logger.info("Browser context and page created")
            
        except Exception as e:
            await self.close()
            raise NetworkError(f"Failed to start browser: {e}")
    
    async def _setup_resource_blocking(self, page: Page) -> None:
        """Set up resource blocking for a page."""
        async def handle_route(route):
            if route.request.resource_type in self.block_resources:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", handle_route)
        logger.info(f"Resource blocking enabled for: {', '.join(self.block_resources)}")

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

        if self.block_resources:
            await self._setup_resource_blocking(page)

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
            user_agent=self.user_agent,
            proxy=self.proxy
        )
        
        # Create new page
        if self._page:
            await self._page.close()
        self._page = await self._context.new_page()

        # Apply resource blocking
        if self.block_resources:
            await self._setup_resource_blocking(self._page)

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
