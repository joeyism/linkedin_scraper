"""Download a LinkedIn profile avatar using your existing Chrome login (macOS).

    python samples/download_avatar.py https://www.linkedin.com/in/some-person/ out.png

No LinkedIn password needed — it reuses the cookies from your logged-in Chrome.
"""
import asyncio
import sys

from linkedin_scraper import (
    BrowserManager,
    get_chrome_linkedin_cookies,
    AvatarScraper,
)


async def main(url: str, out: str) -> None:
    cookies = get_chrome_linkedin_cookies()  # from Chrome "Default" profile
    async with BrowserManager(
        headless=True,
        viewport={"width": 1400, "height": 900},
        device_scale_factor=2,  # 2x for a crisp headshot
    ) as page:
        await page.context.add_cookies(cookies)
        result = await AvatarScraper(page).download(url, out)
        print(result)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
