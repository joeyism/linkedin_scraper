"""Argparse specification with verbose, agent-discoverable --help text."""

import argparse
from textwrap import dedent

from .. import __version__

_ROOT_EPILOG = dedent(
    """
    WORKFLOW (recommended for agents & scripts):
      1. Check session health:  linkedin-scraper auth status
      2. If not logged in:      linkedin-scraper auth login --cookie "$LINKEDIN_LI_AT"
                                (or --env using LINKEDIN_EMAIL/LINKEDIN_PASSWORD; --manual needs a GUI)
      3. Inspect output schema: linkedin-scraper schema person
      4. Scrape pure JSON:      linkedin-scraper person https://www.linkedin.com/in/williamhgates/
      5. Time-windowed feed:    linkedin-scraper feed --search "software engineer @ Toronto" --since-hours 24

    AUTH PRECEDENCE (first match wins):
      1. --session PATH            Explicit Playwright storage_state JSON file
      2. $LINKEDIN_SESSION_PATH    Environment variable pointing to a session file
      3. --cookie LI_AT            Explicit LinkedIn li_at cookie value
      4. $LINKEDIN_LI_AT           Environment variable containing li_at cookie
      5. ./linkedin_session.json   Default session file in current directory
      6. ~/.config/linkedin-scraper/session.json

    OUTPUT CONTRACT:
      - stdout ALWAYS receives pure JSON (never logs or progress bars).
      - stderr receives errors, hints, and optional --verbose progress.
      - Pass --json-error for machine-parseable JSON error objects on stderr.

    EXIT CODES:
      0  Complete success (feed command: complete run, including zero matches)
      2  Invalid arguments, missing explicit session file, or malformed URL
      3  Authentication / challenge (missing or expired session, authwall, checkpoint)
      4  Rate limit (Too many requests / CAPTCHA; inspect suggested_wait_seconds)
      5  ProfileNotFoundError / ElementNotFoundError
      6  NetworkError or missing Playwright Chromium binary (`playwright install chromium`)
      7  Parse/scraping failure (DOM changed; retry with --headed)
      8  Partial feed run (stopped by --timeout, --max-results, or --max-pages;
         stderr carries {"partial":true,"reason":...,"count":N})
    """
).strip()


def _build_common_parent(
    suppress_defaults: bool, include_cookie: bool = True
) -> argparse.ArgumentParser:
    """Shared options accepted both before and after subcommands."""
    default_none = argparse.SUPPRESS if suppress_defaults else None
    default_false = argparse.SUPPRESS if suppress_defaults else False
    default_engine = argparse.SUPPRESS if suppress_defaults else "chromium"

    p = argparse.ArgumentParser(add_help=False)
    g_auth = p.add_argument_group("authentication & browser options")
    g_auth.add_argument(
        "--session",
        default=default_none,
        metavar="PATH",
        help="Path to Playwright session JSON (overrides $LINKEDIN_SESSION_PATH and defaults).",
    )
    if include_cookie:
        g_auth.add_argument(
            "--cookie",
            default=default_none,
            metavar="LI_AT",
            help="LinkedIn li_at cookie value (overrides $LINKEDIN_LI_AT).",
        )
    g_auth.add_argument(
        "--headed",
        action="store_true",
        default=default_false,
        help="Run a visible browser window (useful if LinkedIn challenges headless mode).",
    )
    g_auth.add_argument(
        "--engine",
        choices=["chromium", "firefox", "webkit"],
        default=default_engine,
        help="Playwright browser engine (default: chromium).",
    )
    g_auth.add_argument(
        "--no-stealth",
        action="store_true",
        default=default_false,
        help="Disable BrowserManager anti-detection launch args and init scripts.",
    )

    g_out = p.add_argument_group("output & diagnostics")
    g_out.add_argument(
        "-o",
        "--output",
        default=default_none,
        metavar="FILE",
        help="Write JSON output to FILE instead of stdout.",
    )
    g_out.add_argument(
        "--compact",
        action="store_true",
        default=default_false,
        help="Emit single-line compact JSON instead of pretty-printed JSON.",
    )
    g_out.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=default_false,
        help="Stream scraping progress to stderr (stdout remains pure JSON).",
    )
    g_out.add_argument(
        "--json-error",
        action="store_true",
        default=default_false,
        help="Emit errors on stderr as JSON objects {error_type, message, hint, ...}.",
    )
    return p


def build_parser() -> argparse.ArgumentParser:
    """Build the root CLI ArgumentParser."""
    fmt = argparse.RawDescriptionHelpFormatter
    root_common = _build_common_parent(suppress_defaults=False)
    sub_common = _build_common_parent(suppress_defaults=True)
    login_common = _build_common_parent(suppress_defaults=True, include_cookie=False)

    parser = argparse.ArgumentParser(
        prog="linkedin-scraper",
        description=(
            "Scrape LinkedIn profiles, companies, company posts, and jobs as structured JSON.\n"
            "Run `linkedin-scraper <command> --help` for examples, flags, and output contracts."
        ),
        epilog=_ROOT_EPILOG,
        formatter_class=fmt,
        parents=[root_common],
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- auth ---
    p_auth = subparsers.add_parser(
        "auth",
        help="Inspect session status or create/refresh a LinkedIn session.",
        description="Manage LinkedIn authentication sessions.",
        formatter_class=fmt,
        parents=[sub_common],
    )
    auth_sub = p_auth.add_subparsers(dest="auth_command", required=True)

    auth_sub.add_parser(
        "status",
        help="Verify whether the resolved session/cookie is currently logged in.",
        description="Preflight check: opens linkedin.com/feed/ and verifies authenticated status.",
        epilog=dedent(
            """
            OUTPUT:
              JSON object: {"logged_in": bool, "auth_source": {"kind": ..., "value": ...} | null, "url": str | null}
              Exits 0 if logged_in is true, 3 (EXIT_AUTH) if not logged in.

            EXAMPLES:
              linkedin-scraper auth status
              linkedin-scraper auth status --session ./linkedin_session.json
            """
        ).strip(),
        formatter_class=fmt,
        parents=[sub_common],
    )

    p_login = auth_sub.add_parser(
        "login",
        help="Authenticate and save a reusable Playwright session file.",
        description=(
            "Authenticate to LinkedIn and save cookies/storage to --session "
            "(default: $LINKEDIN_SESSION_PATH or ./linkedin_session.json)."
        ),
        epilog=dedent(
            """
            NON-INTERACTIVE MODES (safe for headless agents):
              --cookie LI_AT   Authenticate with a browser li_at cookie value
              --env            Use LINKEDIN_EMAIL (or LINKEDIN_USERNAME) + LINKEDIN_PASSWORD from env/.env

            INTERACTIVE MODE (requires human + display):
              --manual         Opens a visible browser window and waits up to --timeout seconds for login/2FA

            EXAMPLES:
              linkedin-scraper auth login --cookie "$LINKEDIN_LI_AT" --session ./linkedin_session.json
              linkedin-scraper auth login --env
              linkedin-scraper auth login --manual --timeout 300
            """
        ).strip(),
        formatter_class=fmt,
        parents=[login_common],
    )
    mode = p_login.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--cookie", dest="login_cookie", metavar="LI_AT", help="Login using an li_at cookie."
    )
    mode.add_argument(
        "--env", action="store_true", help="Login using credentials from env / .env."
    )
    mode.add_argument(
        "--manual", action="store_true", help="Open headed browser for manual login/2FA."
    )
    p_login.add_argument(
        "--timeout",
        type=int,
        default=300,
        metavar="SECONDS",
        help="Timeout in seconds for --manual login (default: 300).",
    )

    # --- person ---
    p_person = subparsers.add_parser(
        "person",
        help="Scrape a LinkedIn person profile as JSON.",
        description=(
            "Scrape name, location, about, experiences, educations, interests, "
            "accomplishments, and contacts.\n"
            "Note: visits multiple detail subpages (~12 navigations); space out batch runs "
            "to avoid rate limits."
        ),
        epilog=dedent(
            """
            OUTPUT:
              JSON object conforming to `linkedin-scraper schema person`.

            EXAMPLES:
              linkedin-scraper person https://www.linkedin.com/in/williamhgates/
              linkedin-scraper person https://www.linkedin.com/in/williamhgates/ -o gates.json --verbose
              linkedin-scraper person https://www.linkedin.com/in/williamhgates/ | jq '.experiences[].position_title'
            """
        ).strip(),
        formatter_class=fmt,
        parents=[sub_common],
    )
    p_person.add_argument(
        "url", help="LinkedIn profile URL (must contain linkedin.com/in/)."
    )

    # --- company ---
    p_company = subparsers.add_parser(
        "company",
        help="Scrape a LinkedIn company page as JSON.",
        description=(
            "Scrape company name, about_us, industry, company_size, headquarters, "
            "website, and overview fields."
        ),
        epilog=dedent(
            """
            OUTPUT:
              JSON object conforming to `linkedin-scraper schema company`.

            EXAMPLES:
              linkedin-scraper company https://www.linkedin.com/company/microsoft/
              linkedin-scraper company https://www.linkedin.com/company/microsoft/ --compact
            """
        ).strip(),
        formatter_class=fmt,
        parents=[sub_common],
    )
    p_company.add_argument(
        "url", help="LinkedIn company URL (must contain linkedin.com/company/)."
    )

    # --- posts ---
    p_posts = subparsers.add_parser(
        "posts",
        help="Scrape recent posts from a LinkedIn company page as a JSON array.",
        description="Scrape posts from a company's /posts/ feed.",
        epilog=dedent(
            """
            OUTPUT:
              JSON array of objects conforming to `linkedin-scraper schema post`.

            EXAMPLES:
              linkedin-scraper posts https://www.linkedin.com/company/microsoft/ --limit 5
              linkedin-scraper posts https://www.linkedin.com/company/microsoft/ --limit 10 -o posts.json
            """
        ).strip(),
        formatter_class=fmt,
        parents=[sub_common],
    )
    p_posts.add_argument(
        "url", help="LinkedIn company URL (must contain linkedin.com/company/)."
    )
    p_posts.add_argument(
        "--limit", type=int, default=10, help="Max posts to scrape (default: 10)."
    )

    # --- job ---
    p_job = subparsers.add_parser(
        "job",
        help="Scrape a single LinkedIn job posting as JSON.",
        description=(
            "Scrape job_title, company, location, posted_date, applicant_count, "
            "and job_description."
        ),
        epilog=dedent(
            """
            OUTPUT:
              JSON object conforming to `linkedin-scraper schema job`.

            EXAMPLES:
              linkedin-scraper job https://www.linkedin.com/jobs/view/4457057735/
            """
        ).strip(),
        formatter_class=fmt,
        parents=[sub_common],
    )
    p_job.add_argument(
        "url", help="LinkedIn job URL (must contain linkedin.com/jobs/view/)."
    )

    # --- jobs ---
    p_jobs = subparsers.add_parser(
        "jobs",
        help="Search LinkedIn jobs (returns URLs by default, or full Job objects with --details).",
        description="Search LinkedIn job postings by keywords and optional location.",
        epilog=dedent(
            """
            OUTPUT:
              Default:        JSON array of job URL strings.
              With --details: JSON array of objects conforming to `linkedin-scraper schema job`.

            EXAMPLES:
              linkedin-scraper jobs "software engineer" --location "Toronto" --limit 5
              linkedin-scraper jobs "ml engineer" --location "Seattle" --limit 3 --details
            """
        ).strip(),
        formatter_class=fmt,
        parents=[sub_common],
    )
    p_jobs.add_argument(
        "keywords", help="Search keywords (e.g. 'software engineer')."
    )
    p_jobs.add_argument(
        "--location", default=None, help="Optional location filter (e.g. 'Toronto')."
    )
    p_jobs.add_argument(
        "--limit", type=int, default=10, help="Max job postings to return (default: 10)."
    )
    p_jobs.add_argument(
        "--details",
        action="store_true",
        help="Scrape full Job details for each matched URL (slower; 1 navigation per job).",
    )

    # --- feed ---
    p_feed = subparsers.add_parser(
        "feed",
        help="Emit a deduped, time-windowed job feed across saved searches.",
        description=(
            "Run one or more saved job searches, page through all results, keep "
            "postings inside a time window, and print one flat JSON array.\n"
            "Uses date-descending order and canonical https://www.linkedin.com/jobs/view/<id> URLs."
        ),
        epilog=dedent(
            """
            SEARCHES (repeatable):
              --search KEYWORDS[@LOCATION]   Inline saved search (repeatable)
              --search-file FILE             JSON file: ["kw @ loc", ...] or
                                             [{"keywords": ..., "location": ...}] or {"searches": [...]}

            TIME WINDOW (choose at most one; default: last 24 hours):
              --since-hours N   --since-days N   --since 2026-11-25[THH:MM:SSZ]

            BEHAVIOUR:
              - Sorted by posting date descending; paged by offset until the
                window boundary is crossed or results are exhausted.
              - Deduplicated across searches by posting id.
              - Description is plain text scraped from each posting page.
              - postedAt is the ORIGINAL first-posted date (ISO 8601 date, day
                resolution) from the search card's <time datetime>. Reposts/re-lists
                do not change it; the posting is deduped by id and the "Reposted ..."
                label is ignored for the window. If <time datetime> is missing, the
                relative label is used (months=30d, years=365d); otherwise omitted.
              - On --timeout, returns partial results and prints a warning to stderr.

            OUTPUT:
              JSON array of {title, url, company, location, postedAt, description}
              (fields omitted when genuinely unavailable). Empty array = zero matches.

            EXIT CODES:
              0  Complete run (including zero matches -> [])
              8  Partial run: stopped by --timeout, --max-results, or --max-pages.
                 stdout still holds the flat array; stderr carries
                 {"partial":true,"reason":"timeout"|"max-results"|"max-pages","count":N}
              2  Invalid arguments / malformed search or window
              3  Authentication or security challenge
              4  Rate limit / CAPTCHA
              7  Parse failure (DOM changed)

            ERRORS:
              Failures emit a JSON object {error_type, message, hint, ...} on stderr.

            EXAMPLES:
              linkedin-scraper feed --search "software engineer @ Toronto" --since-hours 24
              linkedin-scraper feed --search-file saved_searches.json --since-days 7 --max-results 100
              linkedin-scraper feed --search "ml engineer" --since-hours 12 --timeout 300 --compact -o feed.json
            """
        ).strip(),
        formatter_class=fmt,
        parents=[sub_common],
    )
    p_feed.add_argument(
        "--search",
        action="append",
        metavar="KEYWORDS[@LOCATION]",
        help="Inline saved search; repeat for multiple searches.",
    )
    p_feed.add_argument(
        "--search-file",
        action="append",
        dest="search_file",
        metavar="FILE",
        help="JSON file with one or more saved searches (repeatable).",
    )
    window = p_feed.add_mutually_exclusive_group()
    window.add_argument(
        "--since-hours",
        type=float,
        default=None,
        metavar="N",
        help="Only include jobs posted within the last N hours (default: 24).",
    )
    window.add_argument(
        "--since-days",
        type=float,
        default=None,
        metavar="N",
        help="Only include jobs posted within the last N days.",
    )
    window.add_argument(
        "--since",
        default=None,
        metavar="ISO8601",
        help="Only include jobs posted at/after this ISO date or datetime.",
    )
    p_feed.add_argument(
        "--timeout",
        type=int,
        default=600,
        metavar="SECONDS",
        help="Overall runtime limit in seconds (default: 600); returns partial results.",
    )
    p_feed.add_argument(
        "--max-results",
        type=int,
        default=200,
        metavar="N",
        help="Stop after N postings (default: 200).",
    )
    p_feed.add_argument(
        "--max-pages",
        type=int,
        default=20,
        metavar="N",
        help="Maximum search-result pages per saved search (default: 20).",
    )
    p_feed.add_argument(
        "--page-delay",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Pause between search-result pages (default: 2.0).",
    )
    p_feed.add_argument(
        "--detail-delay",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="Pause between job-detail scrapes (default: 1.0).",
    )

    # --- schema ---
    p_schema = subparsers.add_parser(
        "schema",
        help="Print Pydantic JSON Schema for output models (no browser or auth needed).",
        description=(
            "Emit JSON Schema so agents can inspect exact output field names "
            "and types offline."
        ),
        epilog=dedent(
            """
            EXAMPLES:
              linkedin-scraper schema person
              linkedin-scraper schema company
              linkedin-scraper schema all
            """
        ).strip(),
        formatter_class=fmt,
        parents=[sub_common],
    )
    p_schema.add_argument(
        "model",
        choices=["person", "company", "post", "job", "feed", "all"],
        help="Model schema to print.",
    )

    return parser
