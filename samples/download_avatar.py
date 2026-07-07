"""Download a LinkedIn profile avatar to an image file.

    export LI_AT=<your li_at cookie value>
    python samples/download_avatar.py https://www.linkedin.com/in/some-person/ out.png

Authentication is "bring your own" — any logged-in Playwright context works. This
sample uses the library's ``login_with_cookie`` with the ``li_at`` cookie from the
``LI_AT`` environment variable. (Grab ``li_at`` from your browser's LinkedIn cookies,
or use ``login_with_credentials`` / ``wait_for_manual_login`` instead.)
"""
import asyncio
import os
import sys

from linkedin_scraper import (
    BrowserManager,
    login_with_cookie,
    AvatarScraper,
)


async def main(url: str, out: str) -> None:
    li_at = os.environ.get("LI_AT")
    if not li_at:
        print("Set the LI_AT environment variable to your li_at cookie value.")
        sys.exit(1)
    async with BrowserManager(
        headless=True,
        viewport={"width": 1400, "height": 900},
        device_scale_factor=2,  # 2x for a crisp headshot
    ) as page:
        await login_with_cookie(page, li_at)
        result = await AvatarScraper(page).download(url, out)
        print(result)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
