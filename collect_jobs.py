#!/usr/bin/env python3
"""
Collect LinkedIn job postings at scale.

Usage:
    python3 collect_jobs.py --keywords "Python Developer" --locations "San Francisco" --limit 50
    python3 collect_jobs.py --keywords "Python Developer,Data Scientist" --locations "San Francisco,New York" --limit 30 --format json
    python3 collect_jobs.py --keywords "Software Engineer" --locations "Remote" --limit 100 --session my_session.json --format csv
"""
import asyncio
import argparse
import csv
import json
import random
import logging
import sys
from pathlib import Path
from typing import List, Optional

from linkedin_scraper import BrowserManager, JobSearchScraper, JobScraper
from linkedin_scraper.core.exceptions import LinkedInScraperException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("collect_jobs")

FORMATS = {"jsonl", "json", "csv"}
FIELD_NAMES = [
    "linkedin_url",
    "job_title",
    "company",
    "company_linkedin_url",
    "location",
    "posted_date",
    "applicant_count",
    "job_description",
    "benefits",
]
FORMAT_EXTENSIONS = {"jsonl": ".jsonl", "json": ".json", "csv": ".csv"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect LinkedIn job postings")
    parser.add_argument(
        "--keywords",
        required=True,
        help="Comma-separated job search keywords (e.g. 'Python Developer,Data Scientist')",
    )
    parser.add_argument(
        "--locations",
        required=True,
        help="Comma-separated locations, one per keywords entry (e.g. 'San Francisco,New York')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max jobs to collect per search query (default: 25)",
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: jobs.<format>)",
    )
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=sorted(FORMATS),
        default="jsonl",
        help="Output format: jsonl (line-delimited JSON), json (pretty array), csv (default: jsonl)",
    )
    parser.add_argument(
        "--session",
        default="linkedin_session.json",
        help="Session file path (default: linkedin_session.json)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser headless (default: True)",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Show browser window",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=3.0,
        help="Min seconds between job scrapes (default: 3.0)",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=6.0,
        help="Max seconds between job scrapes (default: 6.0)",
    )
    return parser.parse_args()


def build_search_queries(
    keywords_str: str, locations_str: str
) -> List[tuple[str, Optional[str]]]:
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    locations = [l.strip() for l in locations_str.split(",") if l.strip()]

    if not keywords:
        logger.error("No keywords provided")
        sys.exit(1)

    if len(locations) == 1 and len(keywords) > 1:
        locations = locations * len(keywords)
    elif len(locations) != len(keywords):
        logger.error(
            f"Number of locations ({len(locations)}) must be 1 or match "
            f"number of keywords ({len(keywords)})"
        )
        sys.exit(1)

    return list(zip(keywords, locations))


async def main() -> None:
    args = parse_args()

    session_path = Path(args.session)
    if not session_path.exists():
        logger.error(f"Session file not found: {args.session}")
        logger.error("Run 'python3 samples/create_session.py' first to create one.")
        sys.exit(1)

    queries = build_search_queries(args.keywords, args.locations)
    total_expected = len(queries) * args.limit
    logger.info(
        f"Will run {len(queries)} search queries, "
        f"targeting up to {args.limit} jobs each (~{total_expected} total)"
    )
    for kw, loc in queries:
        logger.info(f"  Query: keywords='{kw}', location='{loc}'")

    if args.output:
        output_path = Path(args.output)
    else:
        ext = FORMAT_EXTENSIONS[args.fmt]
        output_path = Path(f"jobs{ext}")

    async with BrowserManager(headless=args.headless) as browser:
        await browser.load_session(str(session_path))
        logger.info("Session loaded")

        search_scraper = JobSearchScraper(browser.page)
        job_scraper = JobScraper(browser.page)

        all_urls: set[str] = set()

        for kw, loc in queries:
            logger.info(f"Searching: keywords='{kw}', location='{loc}'")
            try:
                urls = await search_scraper.search(
                    keywords=kw, location=loc, limit=args.limit
                )
            except LinkedInScraperException as e:
                logger.error(f"Search failed for '{kw}' / '{loc}': {e}")
                continue

            new_urls = [u for u in urls if u not in all_urls]
            all_urls.update(new_urls)
            logger.info(
                f"  Found {len(urls)} jobs ({len(new_urls)} new, "
                f"{len(all_urls)} unique total)"
            )

        if not all_urls:
            logger.error("No job URLs found. Exiting.")
            sys.exit(1)

        logger.info(f"Scraping {len(all_urls)} unique job postings...")

        jobs: list[dict] = []
        success = 0
        fail = 0

        csv_fh = None
        csv_writer = None
        if args.fmt == "csv":
            csv_fh = open(output_path, "w", newline="")
            csv_writer = csv.DictWriter(csv_fh, fieldnames=FIELD_NAMES, extrasaction="ignore")
            csv_writer.writeheader()

        for i, url in enumerate(all_urls, 1):
            delay = random.uniform(args.min_delay, args.max_delay)
            logger.info(f"[{i}/{len(all_urls)}] Scraping (waiting {delay:.1f}s)...")

            await asyncio.sleep(delay)

            try:
                job = await job_scraper.scrape(url)
            except LinkedInScraperException as e:
                logger.warning(f"  FAIL [{i}/{len(all_urls)}] {url}: {e}")
                fail += 1
                continue
            except Exception as e:
                logger.warning(f"  ERROR [{i}/{len(all_urls)}] {url}: {e}")
                fail += 1
                continue

            row = job.model_dump()

            if args.fmt == "jsonl":
                with open(output_path, "a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            elif args.fmt == "csv":
                csv_writer.writerow(row)
            else:
                jobs.append(row)

            title = job.job_title or "N/A"
            company = job.company or "N/A"
            logger.info(f"  OK   [{i}/{len(all_urls)}] {title} @ {company}")
            success += 1

        if csv_fh:
            csv_fh.close()

        if args.fmt == "json":
            with open(output_path, "w") as f:
                json.dump(jobs, f, ensure_ascii=False, indent=2)

    logger.info(f"Done. {success} succeeded, {fail} failed, saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
