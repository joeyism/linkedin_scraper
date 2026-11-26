---
name: linkedin-avatar
description: Download a LinkedIn profile's headshot (avatar) to an image file. Use when you need to save profile photos for a CRM, directory, or gallery and the usual routes (image URL, right-click save, canvas, profile PDF) are blocked.
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

The one thing that works: **element-screenshot the rendered `<img>`** with Playwright, which writes straight to a file. This skill packages that.

## How it works

1. Authenticate a Playwright context (bring your own — see below).
2. Navigate to the profile, pick the **largest square** `media.licdn.com` image
   (the main photo, not the cover banner or thumbnail), and screenshot it at 2x.

## Authentication (bring your own)

`AvatarScraper` works with any logged-in Playwright context. Pick whichever fits:

- **`li_at` cookie** (simplest): `await login_with_cookie(page, li_at)` — grab the
  `li_at` value from your browser's LinkedIn cookies (any OS).
- **Credentials**: `await login_with_credentials(page, email, password)`.
- **Manual**: `await wait_for_manual_login(page)` and log in in the opened window.

## Usage

```bash
pip install -e .            # this repo
playwright install chromium
export LI_AT=<your li_at cookie value>
python samples/download_avatar.py https://www.linkedin.com/in/some-person/ out.png
```

Programmatically:

```python
import os
from linkedin_scraper import BrowserManager, login_with_cookie, AvatarScraper

async with BrowserManager(headless=True, viewport={"width":1400,"height":900},
                          device_scale_factor=2) as page:
    await login_with_cookie(page, os.environ["LI_AT"])
    result = await AvatarScraper(page).download(url, "out.png")
    # {'saved': True, 'path': 'out.png', 'rendered': (152, 152)}
```

## Guardrails

- Reuse **one** authenticated context and **pace** requests (a couple of seconds
  between profiles). LinkedIn throttles bursts.
- `saved: False` means the profile has no photo (default ghost) — skip it.
- Respect LinkedIn's Terms and only collect data you're entitled to.
