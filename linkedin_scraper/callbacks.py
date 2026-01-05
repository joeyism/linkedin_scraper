"""Progress callback system for scraping operations."""

from typing import Any, Optional
import json
from datetime import datetime


class ProgressCallback:
    """Base callback class for progress tracking."""
    
    async def on_start(self, scraper_type: str, url: str) -> None:
        """
        Called when scraping starts.
        
        Args:
            scraper_type: Type of scraper (person, company, job, etc.)
            url: URL being scraped
        """
        pass
    
    async def on_progress(self, message: str, percent: int) -> None:
        """
        Called during scraping to report progress.
        
        Args:
            message: Progress message
            percent: Progress percentage (0-100)
        """
        pass
    
    async def on_complete(self, scraper_type: str, result: Any) -> None:
        """
        Called when scraping completes successfully.
        
        Args:
            scraper_type: Type of scraper
            result: The scraped result object
        """
        pass
    
    async def on_error(self, error: Exception) -> None:
        """
        Called when an error occurs.
        
        Args:
            error: The exception that occurred
        """
        pass


class ConsoleCallback(ProgressCallback):
    """Print progress to console."""
    
    def __init__(self, verbose: bool = True):
        """
        Initialize console callback.
        
        Args:
            verbose: If True, print all messages. If False, only print major milestones.
        """
        self.verbose = verbose
    
    async def on_start(self, scraper_type: str, url: str) -> None:
        """Print start message."""
        print(f"🚀 Starting {scraper_type} scraping: {url}")
    
    async def on_progress(self, message: str, percent: int) -> None:
        """Print progress message."""
        if self.verbose or percent % 20 == 0:  # Print every 20% if not verbose
            bar_length = 30
            filled = int(bar_length * percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"[{bar}] {percent}% - {message}")
    
    async def on_complete(self, scraper_type: str, result: Any) -> None:
        """Print completion message."""
        print(f"✅ Completed {scraper_type} scraping successfully!")
    
    async def on_error(self, error: Exception) -> None:
        """Print error message."""
        print(f"❌ Error: {error}")


class SilentCallback(ProgressCallback):
    """Silent callback that does nothing (for when you don't want progress updates)."""
    pass


class JSONLogCallback(ProgressCallback):
    """Log progress as JSON to a file."""
    
    def __init__(self, log_file: str):
        """
        Initialize JSON log callback.
        
        Args:
            log_file: Path to log file
        """
        self.log_file = log_file
        self.logs = []
    
    def _log(self, event_type: str, data: dict) -> None:
        """Add a log entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **data
        }
        self.logs.append(entry)
        
        # Append to file
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    async def on_start(self, scraper_type: str, url: str) -> None:
        """Log start event."""
        self._log("start", {"scraper_type": scraper_type, "url": url})
    
    async def on_progress(self, message: str, percent: int) -> None:
        """Log progress event."""
        self._log("progress", {"message": message, "percent": percent})
    
    async def on_complete(self, scraper_type: str, result: Any) -> None:
        """Log completion event."""
        self._log("complete", {"scraper_type": scraper_type})
    
    async def on_error(self, error: Exception) -> None:
        """Log error event."""
        self._log("error", {"error": str(error), "error_type": type(error).__name__})


class MultiCallback(ProgressCallback):
    """Combine multiple callbacks."""
    
    def __init__(self, *callbacks: ProgressCallback):
        """
        Initialize multi-callback.
        
        Args:
            *callbacks: Variable number of callback instances
        """
        self.callbacks = callbacks
    
    async def on_start(self, scraper_type: str, url: str) -> None:
        """Call all callbacks."""
        for callback in self.callbacks:
            await callback.on_start(scraper_type, url)
    
    async def on_progress(self, message: str, percent: int) -> None:
        """Call all callbacks."""
        for callback in self.callbacks:
            await callback.on_progress(message, percent)
    
    async def on_complete(self, scraper_type: str, result: Any) -> None:
        """Call all callbacks."""
        for callback in self.callbacks:
            await callback.on_complete(scraper_type, result)
    
    async def on_error(self, error: Exception) -> None:
        """Call all callbacks."""
        for callback in self.callbacks:
            await callback.on_error(error)
