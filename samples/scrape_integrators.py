#!/usr/bin/env python3
"""
Scrape LinkedIn company data and merge it into a system integrator JSON list.

Reads a JSON file where each object has a `linkedin_url` field, scrapes missing
LinkedIn data via CompanyScraper, and writes the enriched records to the output
file.  Idempotent: records that already have `company_size` populated are skipped.

Usage:
    python samples/scrape_integrators.py
    python samples/scrape_integrators.py --input data/system_integrator_list.json
    python samples/scrape_integrators.py --input in.json --output out.json
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from linkedin_scraper.core.browser import BrowserManager
from linkedin_scraper.scrapers.company import CompanyScraper

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_INPUT = DATA_DIR / "system_integrator_list.json"
SESSION_PATH = Path(__file__).parent.parent / "linkedin_session.json"

# Fields the scraper provides; all map 1-to-1 onto the record schema
SCRAPED_FIELDS = [
    "name", "about_us", "website", "phone", "headquarters",
    "founded", "industry", "company_type", "company_size", "specialties",
]


def is_scraped(record: dict) -> bool:
    """Return True if this record already has LinkedIn data."""
    return bool(record.get("company_size"))


def merge(record: dict, company) -> dict:
    """Overwrite record fields with non-null scraped values."""
    updated = {**record}
    for field in SCRAPED_FIELDS:
        value = getattr(company, field, None)
        if value not in (None, ""):
            updated[field] = value
    return updated


async def scrape_all(records: list[dict], skip_scraped: bool = True) -> list[dict]:
    pending = [r for r in records if not (skip_scraped and is_scraped(r))]
    logger.info("%d/%d records need scraping", len(pending), len(records))

    if not pending:
        return records

    results_by_url = {r["linkedin_url"]: r for r in records}

    async with BrowserManager(headless=False) as browser:
        if SESSION_PATH.exists():
            await browser.load_session(str(SESSION_PATH))
            logger.info("Session loaded from %s", SESSION_PATH)
        else:
            logger.warning("No session file at %s — you may need to log in manually", SESSION_PATH)

        scraper = CompanyScraper(browser.page)

        for i, record in enumerate(pending, 1):
            url = record.get("linkedin_url", "").strip()
            label = record.get("name") or url

            if not url or "linkedin.com/company/" not in url:
                logger.warning("[%d/%d] Skipping %r — not a valid company URL", i, len(pending), label)
                continue

            logger.info("[%d/%d] Scraping: %s", i, len(pending), url)
            try:
                company = await scraper.scrape(url)
                results_by_url[url] = merge(record, company)
                logger.info("  -> OK: %s", company.name)
            except Exception as e:
                logger.error("  -> FAILED %s: %s", url, e)

    return list(results_by_url.values())


def main():
    parser = argparse.ArgumentParser(description="Scrape LinkedIn data into integrator JSON list")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Input JSON file (default: data/system_integrator_list.json)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSON file (default: same as input)")
    parser.add_argument("--skip-scraped", default=True, action=argparse.BooleanOptionalAction,
                        help="Skip records that already have LinkedIn data (default: true)")
    args = parser.parse_args()

    output_path = args.output or args.input

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )

    if not args.input.exists():
        logger.error("Input file not found: %s", args.input)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        records = json.load(f)
    logger.info("Loaded %d records from %s", len(records), args.input)

    enriched = asyncio.run(scrape_all(records, skip_scraped=args.skip_scraped))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    logger.info("Wrote %d records to %s", len(enriched), output_path)


if __name__ == "__main__":
    main()
