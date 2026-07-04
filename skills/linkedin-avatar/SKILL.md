---
name: linkedin-avatar
description: Download a LinkedIn profile's headshot (avatar) to an image file, authenticating from your existing logged-in Chrome session (no password). Use when you need to save profile photos for a CRM, directory, or gallery and the usual routes (image URL, right-click save, canvas, profile PDF) are blocked.
---

# linkedin-avatar

Save a LinkedIn profile photo as a real image file.

## Why this exists

Every "easy" way to grab a LinkedIn avatar is blocked:

| Method | Result |
|---|---|
| Read the `<img>` src and download it | CDN URL is token-signed / filtered |
| `fetch()` the bytes in-page | CORS blocked (`Failed to fetch`) |
| Draw to `<canvas>` → `toDataURL()` | `SecurityError: tainted canvas` |
| Right-click → Save image as | Native OS dialog, not scriptable |
| Profile "Save to PDF" | Text-only résumé, no embedded image |

The one thing that works: **element-screenshot the rendered `<img>`** with Playwright, which writes straight to a file. This skill packages that plus password-free auth.

## How it works

1. `get_chrome_linkedin_cookies()` reads your local Chrome profile's cookie DB
   (copying the WAL so it works while Chrome is open) and decrypts `li_at` et al.
   with the `Chrome Safe Storage` key from the macOS Keychain. **macOS only.**
2. Inject those cookies into a headless Playwright context (`channel="chrome"`).
3. Navigate to the profile, pick the **largest square** `media.licdn.com` image
   (the main photo, not the cover banner or thumbnail), and screenshot it at 2x.

## Usage

```bash
pip install -e .            # this repo
playwright install chrome   # or use system Chrome via channel="chrome"
python samples/download_avatar.py https://www.linkedin.com/in/some-person/ out.png
```

Programmatically:

```python
from linkedin_scraper import BrowserManager, get_chrome_linkedin_cookies, AvatarScraper

cookies = get_chrome_linkedin_cookies()
async with BrowserManager(headless=True, viewport={"width":1400,"height":900},
                          device_scale_factor=2) as page:
    await page.context.add_cookies(cookies)
    result = await AvatarScraper(page).download(url, "out.png")
    # {'saved': True, 'path': 'out.png', 'rendered': (152, 152)}
```

## Guardrails

- Reuse **one** authenticated context and **pace** requests (a couple of seconds
  between profiles). LinkedIn throttles bursts.
- `saved: False` means the profile has no photo (default ghost) — skip it.
- Cookies are read-only; your Chrome profile is never modified.
- Respect LinkedIn's Terms and only collect data you're entitled to.
