"""Progress callback that writes exclusively to stderr so stdout stays pure JSON."""

import sys
from typing import Any, TextIO

from ..callbacks import ProgressCallback


class StderrProgressCallback(ProgressCallback):
    """Stream human-readable progress lines to stderr."""

    def __init__(self, stream: TextIO = None):
        self._stream = stream

    @property
    def stream(self) -> TextIO:
        return self._stream if self._stream is not None else sys.stderr

    async def on_start(self, scraper_type: str, url: str) -> None:
        print(f"[start] Starting {scraper_type}: {url}", file=self.stream, flush=True)

    async def on_progress(self, message: str, percent: int) -> None:
        print(f"[{percent}%] {message}", file=self.stream, flush=True)

    async def on_complete(self, scraper_type: str, result: Any) -> None:
        print(f"[done] Completed {scraper_type}", file=self.stream, flush=True)

    async def on_error(self, error: Exception) -> None:
        print(f"[error] {error}", file=self.stream, flush=True)
