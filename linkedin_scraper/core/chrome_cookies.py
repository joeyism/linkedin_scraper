"""Authenticate from your existing local Chrome LinkedIn session (macOS).

Instead of storing your LinkedIn email/password, this reads the cookies from a
locally installed Google Chrome profile that is already logged in to LinkedIn,
decrypts them with the ``Chrome Safe Storage`` key from the macOS Keychain, and
returns them in the shape Playwright's ``context.add_cookies()`` expects.

Typical use::

    from linkedin_scraper import BrowserManager, get_chrome_linkedin_cookies

    cookies = get_chrome_linkedin_cookies()          # from Chrome "Default" profile
    async with BrowserManager(headless=True) as page:
        await page.context.add_cookies(cookies)
        # ...now scrape as the logged-in user

Notes
-----
* **macOS only.** Chrome on Linux/Windows uses a different key store; this module
  raises ``NotImplementedError`` off macOS.
* It copies the cookie DB (including the ``-wal`` write-ahead log) to a temp file
  so it works even while Chrome is running, then checkpoints the WAL.
* Nothing is written back; your Chrome profile is never modified.
"""

import base64
import glob
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "chrome_cookies requires the 'cryptography' package. `pip install cryptography`."
    ) from exc

# httpOnly cookies per LinkedIn; the rest are safe to send as non-httpOnly.
_HTTPONLY = {"li_at", "JSESSIONID", "li_rm", "lidc", "bcookie", "liap"}


def _chrome_base() -> Path:
    if sys.platform != "darwin":
        raise NotImplementedError(
            "get_chrome_linkedin_cookies currently supports macOS only."
        )
    return Path.home() / "Library/Application Support/Google/Chrome"


def _safe_storage_key() -> bytes:
    """Fetch the 'Chrome Safe Storage' password from the macOS Keychain."""
    pw = subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"]
    ).strip()
    return PBKDF2HMAC(
        algorithm=hashes.SHA1(), length=16, salt=b"saltysalt",
        iterations=1003, backend=default_backend(),
    ).derive(pw)


def _decrypt(encrypted: bytes, key: bytes) -> Optional[str]:
    if not encrypted or encrypted[:3] != b"v10":
        return None
    dec = Cipher(
        algorithms.AES(key), modes.CBC(b" " * 16), backend=default_backend()
    ).decryptor()
    plain = dec.update(encrypted[3:]) + dec.finalize()
    plain = plain[: -plain[-1]]  # strip PKCS7 padding
    try:
        return plain.decode("utf-8")
    except UnicodeDecodeError:
        # Recent Chrome prepends a 32-byte SHA-256 domain hash to the plaintext.
        return plain[32:].decode("utf-8", "replace")


def _cookie_db(profile: str) -> Path:
    base = _chrome_base() / profile
    for candidate in (base / "Network" / "Cookies", base / "Cookies"):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No Chrome cookie DB found for profile {profile!r}.")


def get_chrome_linkedin_cookies(
    profile: str = "Default",
    domain_filter: str = "linkedin.com",
) -> List[Dict]:
    """Return decrypted LinkedIn cookies from a local Chrome profile.

    Args:
        profile: Chrome profile directory name (e.g. ``"Default"``, ``"Profile 1"``).
        domain_filter: Only return cookies whose host matches this substring.

    Returns:
        A list of dicts ready for Playwright ``context.add_cookies()``.

    Raises:
        NotImplementedError: On non-macOS platforms.
        FileNotFoundError: If the profile's cookie DB can't be located.
        RuntimeError: If no matching cookies could be decrypted (not logged in?).
    """
    key = _safe_storage_key()
    src = _cookie_db(profile)

    tmp = Path(tempfile.mkdtemp(prefix="li_cookies_"))
    try:
        shutil.copy(src, tmp / "Cookies")
        for ext in ("-wal", "-shm"):
            if (p := Path(str(src) + ext)).exists():
                shutil.copy(p, tmp / f"Cookies{ext}")
        con = sqlite3.connect(tmp / "Cookies")
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except sqlite3.Error:
            pass
        rows = con.execute(
            "SELECT name, encrypted_value, host_key, path, is_secure "
            "FROM cookies WHERE host_key LIKE ?",
            (f"%{domain_filter}%",),
        ).fetchall()
        con.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    cookies: List[Dict] = []
    for name, enc, host, path, is_secure in rows:
        value = _decrypt(enc, key)
        if value is None:
            continue
        cookies.append({
            "name": name,
            "value": value,
            "domain": host if host.startswith(".") else "." + domain_filter,
            "path": path or "/",
            "secure": bool(is_secure) or name in _HTTPONLY,
            "httpOnly": name in _HTTPONLY,
            "sameSite": "None",
        })

    if not any(c["name"] == "li_at" for c in cookies):
        raise RuntimeError(
            f"No 'li_at' cookie found in Chrome profile {profile!r}. "
            "Open Chrome and log in to LinkedIn first."
        )
    return cookies
