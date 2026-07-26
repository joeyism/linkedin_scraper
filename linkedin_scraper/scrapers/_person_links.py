"""Internal URL and contact helpers for the person scraper."""

from typing import Dict, List, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlunparse

from ..models import Contact

SOCIAL_HOSTS = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "medium.com": "medium",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "scholar.google.com": "google_scholar",
    "behance.net": "behance",
    "dribbble.com": "dribbble",
    "stackoverflow.com": "stackoverflow",
    "leetcode.com": "leetcode",
    "kaggle.com": "kaggle",
    "linktr.ee": "linktree",
}


def profile_detail_url(profile_url: str, relative_path: str) -> str:
    """Build a detail URL without replacing a trailing profile slug."""
    parsed = urlparse(profile_url)
    clean = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", "", "")
    )
    return urljoin(clean, relative_path.lstrip("/"))


def unwrap_href(href: str) -> str:
    """Unwrap LinkedIn safety/redirect URLs to the real destination."""
    if "linkedin.com/safety/go" in href or "linkedin.com/redir/" in href:
        urls = parse_qs(urlparse(href).query).get("url")
        if urls:
            return unquote(urls[0])
    return href


def classify_link(href: str, label: Optional[str] = None) -> Contact:
    """Classify an outbound URL into a typed contact."""
    host = urlparse(href).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, contact_type in SOCIAL_HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return Contact(type=contact_type, value=href, label=label or None)
    return Contact(type="website", value=href, label=label or None)


def contact_type_from_heading(heading: str) -> Optional[str]:
    """Map a contact-info section heading to the public contact type."""
    heading = heading.lower()
    if "profile" in heading:
        return "linkedin"
    if "website" in heading:
        return "website"
    if "email" in heading:
        return "email"
    if "phone" in heading:
        return "phone"
    if "twitter" in heading or "x.com" in heading:
        return "twitter"
    if "birthday" in heading:
        return "birthday"
    if "address" in heading:
        return "address"
    return None


def merge_contacts(primary: List[Contact], extra: List[Contact]) -> List[Contact]:
    """Merge contacts, preferring typed entries and richer labels."""
    by_key: Dict[str, Contact] = {}
    for contact in primary + extra:
        key = "{}:{}".format(contact.type, contact.value.strip())
        existing = by_key.get(key)
        if existing is None or (contact.label and not existing.label):
            by_key[key] = contact
    return list(by_key.values())
