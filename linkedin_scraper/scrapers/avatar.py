"""Download a LinkedIn profile's avatar (headshot).

Getting a usable image file of a profile photo is awkward: the CDN URL is
token-signed and CORS-locked, ``fetch()``/``canvas`` are blocked, and the
"Save to PDF" export contains no image. The reliable path is to **element-
screenshot the rendered <img>** — Playwright writes it straight to a file.

This scraper finds the largest *square* ``media.licdn.com`` image on the profile
(the main photo, not the cover banner or tiny mutual-connection thumbnails) and
screenshots it.

Example::

    from linkedin_scraper import BrowserManager, get_chrome_linkedin_cookies, AvatarScraper

    cookies = get_chrome_linkedin_cookies()
    async with BrowserManager(headless=True, viewport={"width": 1400, "height": 900},
                              device_scale_factor=2) as page:
        await page.context.add_cookies(cookies)
        result = await AvatarScraper(page).download(
            "https://www.linkedin.com/in/some-person/", "some-person.png")
        print(result)  # {'saved': True, 'path': 'some-person.png', 'rendered': (152, 152)}
"""

import logging
from typing import Optional, Dict, Any

from .base import BaseScraper

logger = logging.getLogger(__name__)

# In-page: tag the largest square licdn image so we can screenshot it by selector.
_PICK_AVATAR_JS = """
(minSize) => {
  const imgs = [...document.querySelectorAll('img')]
    .filter(i => /media\\.licdn\\.com\\/dms\\/image/.test(i.currentSrc || i.src));
  let pick = null, area = 0;
  for (const im of imgs) {
    const r = im.getBoundingClientRect();
    const w = r.width, h = r.height;
    if (w < minSize || h < minSize) continue;      // skip tiny thumbnails
    if (Math.abs(w / h - 1) > 0.15) continue;      // square only (skip cover banner)
    if (w * h > area) { area = w * h; pick = im; }
  }
  if (!pick) return null;
  pick.setAttribute('data-li-avatar', '1');
  const r = pick.getBoundingClientRect();
  return { w: Math.round(r.width), h: Math.round(r.height) };
}
"""


class AvatarScraper(BaseScraper):
    """Download the main profile photo of a LinkedIn profile as an image file."""

    async def download(
        self,
        url: str,
        output_path: str,
        min_size: int = 80,
        settle_ms: int = 3500,
    ) -> Dict[str, Any]:
        """Navigate to ``url`` and save the profile avatar to ``output_path``.

        Args:
            url: LinkedIn profile URL.
            output_path: Where to write the PNG (screenshot of the rendered photo).
            min_size: Minimum rendered edge (px) to accept as the main photo.
            settle_ms: How long to wait after load for the photo to render.

        Returns:
            ``{"saved": bool, "path": str|None, "rendered": (w, h)|None}``.
            ``saved`` is False when the profile has no photo (default ghost avatar).
        """
        self.callback.on_progress(f"avatar: {url}")
        await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await self.page.wait_for_timeout(settle_ms)
        await self.ensure_logged_in()

        dims = await self.page.evaluate(_PICK_AVATAR_JS, min_size)
        if not dims:
            logger.info("No avatar image found for %s", url)
            return {"saved": False, "path": None, "rendered": None}

        try:
            await self.page.locator('img[data-li-avatar="1"]').screenshot(path=output_path)
        except Exception as exc:  # pragma: no cover
            logger.warning("Avatar screenshot failed for %s: %s", url, exc)
            return {"saved": False, "path": None, "rendered": (dims["w"], dims["h"])}

        return {"saved": True, "path": output_path, "rendered": (dims["w"], dims["h"])}
