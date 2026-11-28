"""Async command execution for the linkedin-scraper CLI."""

import json
import os
import sys
from datetime import datetime, timezone
from argparse import Namespace
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from ..callbacks import ProgressCallback, SilentCallback
from ..core.auth import (
    is_logged_in,
    login_with_cookie,
    login_with_credentials,
    wait_for_manual_login,
)
from ..core.browser import BrowserManager
from ..core.exceptions import AuthenticationError
from ..models import Company, Job, JobFeedItem, Person, Post
from ..scrapers import (
    CompanyPostsScraper,
    CompanyScraper,
    JobFeedScraper,
    JobScraper,
    JobSearchScraper,
    PersonScraper,
)
from ..scrapers.job_feed import (
    load_saved_searches,
    parse_search_spec,
    resolve_cutoff,
)
from .callbacks import StderrProgressCallback
from .errors import EXIT_AUTH, EXIT_OK, EXIT_PARTIAL, CliUsageError
from .session import (
    AuthSource,
    default_session_save_path,
    resolve_auth_source,
    validate_target_url,
)

_SCHEMA_MODELS = {
    "person": Person,
    "company": Company,
    "post": Post,
    "job": Job,
    "feed": JobFeedItem,
}

_SCRAPER_DEFAULTS = {
    "person": PersonScraper,
    "company": CompanyScraper,
    "posts": CompanyPostsScraper,
    "job": JobScraper,
    "job_search": JobSearchScraper,
    "job_feed": JobFeedScraper,
}


def write_json_output(data: Any, output_path: Optional[str], compact: bool) -> None:
    """Serialize data as JSON to stdout or to a file."""
    text = json.dumps(data, indent=None if compact else 2, ensure_ascii=False)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()


def _browser_kwargs(args: Namespace, force_headed: bool = False) -> dict:
    return {
        "headless": False if (force_headed or getattr(args, "headed", False)) else True,
        "engine": getattr(args, "engine", "chromium"),
        "stealth": not getattr(args, "no_stealth", False),
    }


async def _apply_auth(
    browser: Any,
    source: AuthSource,
    login_cookie_fn: Callable[..., Any],
) -> None:
    if source.kind == "session":
        await browser.load_session(source.value)
    elif source.kind == "cookie":
        await login_cookie_fn(browser.page, source.value)


async def _run_auth(
    args: Namespace,
    env: Mapping[str, str],
    cwd: Optional[Path],
    home: Optional[Path],
    browser_factory: Callable[..., Any],
    auth: Mapping[str, Callable[..., Any]],
) -> int:
    if args.auth_command == "status":
        source = resolve_auth_source(
            getattr(args, "session", None),
            getattr(args, "cookie", None),
            env,
            cwd=cwd,
            home=home,
        )
        if source is None:
            write_json_output(
                {"logged_in": False, "auth_source": None, "url": None},
                getattr(args, "output", None),
                getattr(args, "compact", False),
            )
            return EXIT_AUTH

        async with browser_factory(**_browser_kwargs(args)) as browser:
            if source.kind == "session":
                await browser.load_session(source.value)
                await browser.page.goto(
                    "https://www.linkedin.com/feed/", wait_until="domcontentloaded"
                )
                logged_in = await auth["is_logged_in"](browser.page, wait_timeout=5000)
            else:
                try:
                    await auth["login_with_cookie"](browser.page, source.value)
                    logged_in = True
                except AuthenticationError:
                    logged_in = False

            # Redact raw cookie values from the JSON payload.
            public_source = {
                "kind": source.kind,
                "value": source.value if source.kind == "session" else "<redacted>",
            }
            write_json_output(
                {
                    "logged_in": logged_in,
                    "auth_source": public_source,
                    "url": browser.page.url,
                },
                getattr(args, "output", None),
                getattr(args, "compact", False),
            )
            return EXIT_OK if logged_in else EXIT_AUTH

    if args.auth_command == "login":
        save_path = default_session_save_path(
            getattr(args, "session", None), env, cwd=cwd
        )
        force_headed = bool(getattr(args, "manual", False))

        async with browser_factory(
            **_browser_kwargs(args, force_headed=force_headed)
        ) as browser:
            if getattr(args, "login_cookie", None):
                await auth["login_with_cookie"](browser.page, args.login_cookie)
                mode = "cookie"
            elif getattr(args, "env", False):
                await auth["login_with_credentials"](browser.page)
                mode = "env"
            else:
                await browser.page.goto(
                    "https://www.linkedin.com/login", wait_until="domcontentloaded"
                )
                await auth["wait_for_manual_login"](
                    browser.page, timeout=args.timeout * 1000
                )
                mode = "manual"

            await browser.save_session(save_path)
            write_json_output(
                {"logged_in": True, "mode": mode, "saved_session": save_path},
                getattr(args, "output", None),
                getattr(args, "compact", False),
            )
            return EXIT_OK

    raise NotImplementedError(f"Unknown auth action: {args.auth_command}")



def _parse_feed_searches(args: Namespace):
    """Merge --search specs and --search-file entries (deduped, order-preserving)."""
    searches = []
    for spec in getattr(args, "search", None) or []:
        try:
            searches.append(parse_search_spec(spec))
        except ValueError as exc:
            raise CliUsageError(str(exc)) from exc

    for path in getattr(args, "search_file", None) or []:
        try:
            searches.extend(load_saved_searches(path))
        except (ValueError, OSError) as exc:
            raise CliUsageError(str(exc)) from exc

    unique = []
    seen = set()
    for search in searches:
        key = (search.keywords, search.location)
        if key in seen:
            continue
        seen.add(key)
        unique.append(search)

    if not unique:
        raise CliUsageError(
            "No searches provided. Use --search 'KEYWORDS[@LOCATION]' and/or "
            "--search-file FILE."
        )
    return unique


async def _run_feed(
    args: Namespace,
    env: Mapping[str, str],
    cwd: Optional[Path],
    home: Optional[Path],
    browser_factory: Callable[..., Any],
    scrapers: Mapping[str, Callable[..., Any]],
    auth: Mapping[str, Callable[..., Any]],
) -> int:
    searches = _parse_feed_searches(args)

    now = datetime.now(timezone.utc)
    try:
        cutoff = resolve_cutoff(
            now,
            since=getattr(args, "since", None),
            since_hours=getattr(args, "since_hours", None),
            since_days=getattr(args, "since_days", None),
        )
    except ValueError as exc:
        raise CliUsageError(str(exc)) from exc

    source = resolve_auth_source(
        getattr(args, "session", None),
        getattr(args, "cookie", None),
        env,
        cwd=cwd,
        home=home,
    )
    if source is None:
        raise AuthenticationError(
            "No LinkedIn session or li_at cookie found. "
            "Run `linkedin-scraper auth status` or `linkedin-scraper auth login --help`."
        )

    callback: ProgressCallback = (
        StderrProgressCallback()
        if getattr(args, "verbose", False)
        else SilentCallback()
    )

    async with browser_factory(**_browser_kwargs(args)) as browser:
        await _apply_auth(browser, source, auth["login_with_cookie"])

        detail_scraper = scrapers["job"](browser.page, callback=callback)
        feed_factory = scrapers.get("job_feed", JobFeedScraper)
        feed = feed_factory(
            browser.page, callback=callback, detail_scraper=detail_scraper
        )

        result = await feed.collect(
            searches,
            cutoff,
            timeout=getattr(args, "timeout", 600),
            max_results=getattr(args, "max_results", 200),
            max_pages=getattr(args, "max_pages", 20),
            page_delay=getattr(args, "page_delay", 2.0),
            detail_delay=getattr(args, "detail_delay", 1.0),
            now=now,
        )

    for warning in result.warnings:
        print(json.dumps({"warning": warning}), file=sys.stderr)

    write_json_output(
        result.items,
        getattr(args, "output", None),
        getattr(args, "compact", False),
    )

    if result.reason:
        print(
            json.dumps(
                {
                    "partial": True,
                    "reason": result.reason,
                    "count": len(result.items),
                }
            ),
            file=sys.stderr,
        )
        return EXIT_PARTIAL
    return EXIT_OK


async def run_command(
    args: Namespace,
    *,
    env: Optional[Mapping[str, str]] = None,
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
    browser_factory: Callable[..., Any] = BrowserManager,
    scraper_factories: Optional[Mapping[str, Callable[..., Any]]] = None,
    auth_funcs: Optional[Mapping[str, Callable[..., Any]]] = None,
) -> int:
    """Dispatch a parsed CLI Namespace and return a semantic exit code."""
    resolved_env = os.environ if env is None else env

    if args.command == "schema":
        if args.model == "all":
            payload = {
                name: cls.model_json_schema() for name, cls in _SCHEMA_MODELS.items()
            }
        else:
            payload = _SCHEMA_MODELS[args.model].model_json_schema()
        write_json_output(
            payload,
            getattr(args, "output", None),
            getattr(args, "compact", False),
        )
        return EXIT_OK

    auth = {
        "is_logged_in": is_logged_in,
        "login_with_cookie": login_with_cookie,
        "login_with_credentials": login_with_credentials,
        "wait_for_manual_login": wait_for_manual_login,
        **(auth_funcs or {}),
    }

    if args.command == "auth":
        return await _run_auth(args, resolved_env, cwd, home, browser_factory, auth)

    scrapers = {**_SCRAPER_DEFAULTS, **(scraper_factories or {})}

    if args.command == "feed":
        return await _run_feed(
            args, resolved_env, cwd, home, browser_factory, scrapers, auth
        )

    # Fail fast on URL shape before touching auth or Playwright.
    if args.command in ("person", "company", "posts", "job"):
        validate_target_url(args.command, args.url)

    source = resolve_auth_source(
        getattr(args, "session", None),
        getattr(args, "cookie", None),
        resolved_env,
        cwd=cwd,
        home=home,
    )
    if source is None:
        raise AuthenticationError(
            "No LinkedIn session or li_at cookie found. "
            "Run `linkedin-scraper auth status` or `linkedin-scraper auth login --help`."
        )

    callback: ProgressCallback = (
        StderrProgressCallback() if getattr(args, "verbose", False) else SilentCallback()
    )

    async with browser_factory(**_browser_kwargs(args)) as browser:
        await _apply_auth(browser, source, auth["login_with_cookie"])

        if args.command == "person":
            result = (
                await scrapers["person"](browser.page, callback=callback).scrape(
                    args.url
                )
            ).to_dict()
        elif args.command == "company":
            result = (
                await scrapers["company"](browser.page, callback=callback).scrape(
                    args.url
                )
            ).to_dict()
        elif args.command == "posts":
            posts = await scrapers["posts"](browser.page, callback=callback).scrape(
                args.url, limit=args.limit
            )
            result = [post.to_dict() for post in posts]
        elif args.command == "job":
            result = (
                await scrapers["job"](browser.page, callback=callback).scrape(args.url)
            ).to_dict()
        elif args.command == "jobs":
            urls = await scrapers["job_search"](
                browser.page, callback=callback
            ).search(
                keywords=args.keywords,
                location=args.location,
                limit=args.limit,
            )
            if args.details:
                job_scraper = scrapers["job"](browser.page, callback=callback)
                result = [(await job_scraper.scrape(url)).to_dict() for url in urls]
            else:
                result = urls
        else:
            raise NotImplementedError(f"Unknown command: {args.command}")

    write_json_output(
        result, getattr(args, "output", None), getattr(args, "compact", False)
    )
    return EXIT_OK
