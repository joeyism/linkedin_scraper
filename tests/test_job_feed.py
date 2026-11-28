"""Unit tests for the time-windowed job feed scraper and CLI wiring."""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from linkedin_scraper.cli.errors import EXIT_PARTIAL, CliUsageError
from linkedin_scraper.cli.parser import build_parser
from linkedin_scraper.cli.runner import run_command
from linkedin_scraper.core.exceptions import AuthenticationError, RateLimitError, ScrapingError
from linkedin_scraper.scrapers.job_feed import (
    FeedResult,
    JobFeedScraper,
    SavedSearch,
    build_search_url,
    finalize_items,
    load_saved_searches,
    parse_search_fragment,
    parse_search_spec,
    resolve_cutoff,
)

NOW = datetime(2026, 11, 26, 12, 0, 0, tzinfo=timezone.utc)


def _card_html(job_id, title, company, location, iso_date, relative, extra=""):
    return f"""
    <li>
      <div data-entity-urn="urn:li:jobPosting:{job_id}">
        <a href="https://ca.linkedin.com/jobs/view/x-{job_id}"><span>{title}</span></a>
        <h3>{title}</h3>
        <h4><a href="https://www.linkedin.com/company/x">{company}</a></h4>
        <div>
          <span>{location}</span>
          <div><span>Be an early applicant</span></div>
          <time datetime="{iso_date}">{relative}</time>
        </div>
        {extra}
      </div>
    </li>
    """


def _fragment(*cards):
    return "<ul>" + "".join(cards) + "</ul>"


@pytest.mark.unit
def test_parse_search_spec_variants():
    assert parse_search_spec("software engineer") == SavedSearch("software engineer", None)
    assert parse_search_spec("ml engineer @ Toronto") == SavedSearch(
        "ml engineer", "Toronto"
    )
    with pytest.raises(ValueError):
        parse_search_spec("   ")
    with pytest.raises(ValueError):
        parse_search_spec("@ Toronto")


@pytest.mark.unit
def test_load_saved_searches_formats(tmp_path):
    p1 = tmp_path / "a.json"
    p1.write_text(json.dumps(["python @ Toronto", "data engineer"]))
    assert load_saved_searches(str(p1)) == [
        SavedSearch("python", "Toronto"),
        SavedSearch("data engineer", None),
    ]

    p2 = tmp_path / "b.json"
    p2.write_text(json.dumps({"searches": [{"keywords": "rust", "location": "Remote"}]}))
    assert load_saved_searches(str(p2)) == [SavedSearch("rust", "Remote")]

    p3 = tmp_path / "c.json"
    p3.write_text(json.dumps([{"location": "Remote"}]))
    with pytest.raises(ValueError):
        load_saved_searches(str(p3))

    p4 = tmp_path / "d.json"
    p4.write_text("{not json")
    with pytest.raises(ValueError):
        load_saved_searches(str(p4))

    with pytest.raises(ValueError):
        load_saved_searches(str(tmp_path / "missing.json"))


@pytest.mark.unit
def test_resolve_cutoff_variants():
    assert resolve_cutoff(NOW, since_hours=24) == NOW - timedelta(hours=24)
    assert resolve_cutoff(NOW, since_days=7) == NOW - timedelta(days=7)
    assert resolve_cutoff(NOW, since="2026-11-20") == datetime(
        2026, 11, 20, tzinfo=timezone.utc
    )
    assert resolve_cutoff(NOW, since="2026-11-20T06:00:00Z") == datetime(
        2026, 11, 20, 6, tzinfo=timezone.utc
    )
    assert resolve_cutoff(NOW) == NOW - timedelta(hours=24)
    with pytest.raises(ValueError):
        resolve_cutoff(NOW, since_hours=0)
    with pytest.raises(ValueError):
        resolve_cutoff(NOW, since="not-a-date")


@pytest.mark.unit
def test_parse_search_fragment_fields():
    html = _fragment(
        _card_html("111", "Staff Engineer", "Acme", "Toronto, ON", "2026-11-26", "12 hours ago"),
        _card_html("222", "Data Engineer", "Beta", "Remote", "2026-11-25", "1 day ago"),
    )
    cards = parse_search_fragment(html, now=NOW)
    assert [c.job_id for c in cards] == ["111", "222"]
    first = cards[0]
    assert first.title == "Staff Engineer"
    assert first.company == "Acme"
    assert first.location == "Toronto, ON"
    assert first.posted_at == "2026-11-26"
    assert first.posted_ts == datetime(2026, 11, 26, 23, 59, 59, tzinfo=timezone.utc)
    assert first.url == "https://www.linkedin.com/jobs/view/111"


@pytest.mark.unit
def test_parse_search_fragment_dedupes_within_page():
    card = _card_html("111", "T", "C", "L", "2026-11-26", "1 hour ago")
    cards = parse_search_fragment(_fragment(card, card), now=NOW)
    assert len(cards) == 1


@pytest.mark.unit
def test_finalize_dedupes_sorts_and_omits_missing():
    from linkedin_scraper.scrapers.job_feed import FeedCard

    items = finalize_items(
        [
            FeedCard(
                job_id="1",
                title="Old",
                company="A",
                location="X",
                posted_at="2026-11-20",
                posted_ts=datetime(2026, 11, 20, tzinfo=timezone.utc),
                description="old",
            ),
            FeedCard(
                job_id="2",
                title="New",
                company="B",
                posted_at="2026-11-26",
                posted_ts=datetime(2026, 11, 26, tzinfo=timezone.utc),
                description="new",
            ),
            FeedCard(
                job_id="1",
                title="Old",
                location="Y",
                description="",
            ),
        ]
    )
    assert [i["title"] for i in items] == ["New", "Old"]
    assert items[1]["location"] == "X"  # mismatch: merged first-wins
    assert items[1]["description"] == "old"
    assert "location" not in items[0]
    assert set(items[0]) <= {"title", "url", "company", "location", "postedAt", "description"}
    assert items[0]["url"] == "https://www.linkedin.com/jobs/view/2"


@pytest.mark.unit
def test_build_search_url_has_paging_and_window():
    url = build_search_url(SavedSearch("python", "Toronto"), start=25, window_seconds=86400)
    assert url.startswith("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?")
    assert "start=25" in url
    assert "sortBy=DD" in url
    assert "f_TPR=r86400" in url
    assert "location=Toronto" in url


class _FakeDetail:
    def __init__(self):
        self.calls = []

    async def scrape(self, url):
        self.calls.append(url)
        return SimpleNamespace(
            job_description=f"description for {url}",
            job_title=None,
            company=None,
            location=None,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_pages_stops_at_window_and_dedupes():
    pages = {
        0: _fragment(
            _card_html("1", "A", "Co", "Toronto", "2026-11-26", "2 hours ago"),
            _card_html("2", "B", "Co", "Toronto", "2026-11-25", "1 day ago"),
        ),
        2: _fragment(
            _card_html("3", "Old", "Co", "Toronto", "2026-11-20", "6 days ago"),
        ),
    }
    urls = []

    async def fetch(url, timeout_ms):
        urls.append(url)
        from urllib.parse import parse_qs, urlparse

        start = int(parse_qs(urlparse(url).query).get("start", ["0"])[0])
        return pages.get(start, "")

    detail = _FakeDetail()
    scraper = JobFeedScraper(page=None, detail_scraper=detail, fetch_page=fetch)
    cutoff = NOW - timedelta(hours=24)
    result = await scraper.collect(
        [SavedSearch("python", "Toronto")],
        cutoff,
        timeout=60,
        max_results=10,
        max_pages=5,
        page_delay=0,
        detail_delay=0,
        now=NOW,
    )

    assert result.timed_out is False
    assert result.reason is None
    assert result.partial is False
    assert [i["title"] for i in result.items] == ["A", "B"]
    assert result.items[0]["url"] == "https://www.linkedin.com/jobs/view/1"
    assert result.items[0]["postedAt"] == "2026-11-26"
    assert result.items[0]["description"].startswith("description for")
    assert detail.calls == [
        "https://www.linkedin.com/jobs/view/1",
        "https://www.linkedin.com/jobs/view/2",
    ]
    assert len(urls) == 2
    assert "start=0" in urls[0]
    assert "start=2" in urls[1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_dedupes_across_searches():
    page = _fragment(_card_html("9", "Same", "Co", "L", "2026-11-26", "1 hour ago"))
    detail = _FakeDetail()

    async def fetch(url, timeout_ms):
        return page

    scraper = JobFeedScraper(page=None, detail_scraper=detail, fetch_page=fetch)
    result = await scraper.collect(
        [SavedSearch("a"), SavedSearch("b")],
        NOW - timedelta(hours=24),
        timeout=60,
        max_results=10,
        max_pages=1,
        page_delay=0,
        detail_delay=0,
        now=NOW,
    )
    assert len(result.items) == 1
    assert len(detail.calls) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_zero_results_is_empty_success():
    async def fetch(url, timeout_ms):
        return "<ul></ul><p>No matching jobs found.</p>"

    scraper = JobFeedScraper(page=None, detail_scraper=_FakeDetail(), fetch_page=fetch)
    result = await scraper.collect(
        [SavedSearch("none")],
        NOW - timedelta(hours=24),
        timeout=30,
        page_delay=0,
        detail_delay=0,
        now=NOW,
    )
    assert result.items == []
    assert result.reason is None
    assert result.partial is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_raises_on_rate_limit_text():
    async def fetch(url, timeout_ms):
        return "<p>Too many requests. Please slow down.</p>"

    scraper = JobFeedScraper(page=None, detail_scraper=_FakeDetail(), fetch_page=fetch)
    with pytest.raises(RateLimitError):
        await scraper.collect(
            [SavedSearch("x")],
            NOW - timedelta(hours=24),
            timeout=30,
            page_delay=0,
            detail_delay=0,
            now=NOW,
        )


@pytest.mark.unit
def test_posted_at_is_original_date_for_reposts():
    # Real-world case: <time datetime> holds the ORIGINAL posted date (Nov 5),
    # while the displayed label is a later REPOST date ("2 weeks ago" -> Nov 12).
    card = _card_html("333", "X", "C", "L", "2026-11-05", "Reposted 2 weeks ago")
    parsed = parse_search_fragment(_fragment(card), now=NOW)[0]
    assert parsed.posted_at == "2026-11-05"  # original first-posted date
    assert parsed.posted_ts == datetime(2026, 11, 5, 23, 59, 59, tzinfo=timezone.utc)


@pytest.mark.unit
def test_posted_at_falls_back_to_relative_without_datetime():
    html = "<ul><li><div data-entity-urn=\"urn:li:jobPosting:555\">"
    html += "<h3>X</h3><h4><a>C</a></h4><div><span>L</span><time>3 days ago</time></div>"
    html += "</div></li></ul>"
    parsed = parse_search_fragment(html, now=NOW)[0]
    assert parsed.posted_at == (NOW - timedelta(days=3)).date().isoformat()
    assert parsed.posted_ts == NOW - timedelta(days=3)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_reason_max_results():
    page = _fragment(
        _card_html("1", "A", "Co", "L", "2026-11-26", "1 hour ago"),
        _card_html("2", "B", "Co", "L", "2026-11-26", "2 hours ago"),
        _card_html("3", "C", "Co", "L", "2026-11-26", "3 hours ago"),
    )

    async def fetch(url, timeout_ms):
        return page

    scraper = JobFeedScraper(page=None, detail_scraper=_FakeDetail(), fetch_page=fetch)
    result = await scraper.collect(
        [SavedSearch("x")],
        NOW - timedelta(hours=24),
        timeout=60,
        max_results=2,
        max_pages=5,
        page_delay=0,
        detail_delay=0,
        now=NOW,
    )
    assert result.reason == "max-results"
    assert result.partial is True
    assert len(result.items) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_reason_max_pages():
    page = _fragment(
        _card_html("1", "A", "Co", "L", "2026-11-26", "1 hour ago"),
        _card_html("2", "B", "Co", "L", "2026-11-26", "2 hours ago"),
    )

    async def fetch(url, timeout_ms):
        return page

    scraper = JobFeedScraper(page=None, detail_scraper=_FakeDetail(), fetch_page=fetch)
    result = await scraper.collect(
        [SavedSearch("x")],
        NOW - timedelta(hours=24),
        timeout=60,
        max_results=10,
        max_pages=1,
        page_delay=0,
        detail_delay=0,
        now=NOW,
    )
    assert result.reason == "max-pages"
    assert result.partial is True
    assert len(result.items) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_reason_timeout(monkeypatch):
    import linkedin_scraper.scrapers.job_feed as jf

    page = _fragment(_card_html("1", "A", "Co", "L", "2026-11-26", "1 hour ago"))

    async def fetch(url, timeout_ms):
        return page

    ticks = [0.0, 0.0, 0.0, 1000.0]

    def fake_monotonic():
        return ticks.pop(0) if ticks else 1000.0

    monkeypatch.setattr(jf._time, "monotonic", fake_monotonic)

    scraper = JobFeedScraper(page=None, detail_scraper=_FakeDetail(), fetch_page=fetch)
    result = await scraper.collect(
        [SavedSearch("x")],
        NOW - timedelta(hours=24),
        timeout=5,
        max_results=10,
        max_pages=5,
        page_delay=0,
        detail_delay=0,
        now=NOW,
    )
    assert result.reason == "timeout"
    assert result.partial is True
    assert result.timed_out is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_raises_on_unparseable_large_response():
    async def fetch(url, timeout_ms):
        return "<html><body>" + ("<div>unexpected markup</div>" * 500) + "</body></html>"

    scraper = JobFeedScraper(page=None, detail_scraper=_FakeDetail(), fetch_page=fetch)
    with pytest.raises(ScrapingError):
        await scraper.collect(
            [SavedSearch("x")],
            NOW - timedelta(hours=24),
            timeout=30,
            page_delay=0,
            detail_delay=0,
            now=NOW,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_raises_on_security_challenge_text():
    async def fetch(url, timeout_ms):
        return "<p>Security verification required. Verify your identity.</p>"

    scraper = JobFeedScraper(page=None, detail_scraper=_FakeDetail(), fetch_page=fetch)
    with pytest.raises(AuthenticationError):
        await scraper.collect(
            [SavedSearch("x")],
            NOW - timedelta(hours=24),
            timeout=30,
            page_delay=0,
            detail_delay=0,
            now=NOW,
        )


@pytest.mark.unit
def test_feed_parser_flags_and_help(capsys):
    parser = build_parser()
    args = parser.parse_args(
        [
            "feed",
            "--search",
            "a",
            "--search",
            "b @ Toronto",
            "--search-file",
            "s.json",
            "--since-hours",
            "12",
            "--timeout",
            "60",
            "--max-results",
            "5",
            "--page-delay",
            "0.1",
            "--detail-delay",
            "0.2",
        ]
    )
    assert args.command == "feed"
    assert args.search == ["a", "b @ Toronto"]
    assert args.search_file == ["s.json"]
    assert args.since_hours == 12
    assert args.timeout == 60
    assert args.max_results == 5
    assert args.page_delay == 0.1
    assert args.detail_delay == 0.2

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["feed", "--search", "a", "--since-hours", "1", "--since-days", "2"])
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["feed", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for snippet in ("SEARCHES", "TIME WINDOW", "postedAt", "--search-file", "EXAMPLES"):
        assert snippet in out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_feed_command_with_fake_feed(tmp_path, capsys):
    (tmp_path / "linkedin_session.json").write_text("{}")

    class _FakeJob:
        def __init__(self, page, callback=None):
            pass

        async def scrape(self, url):
            raise AssertionError("should not be used")

    class _FakeFeed:
        def __init__(self, page, callback=None, detail_scraper=None):
            self.detail = detail_scraper

        async def collect(self, searches, cutoff, **kwargs):
            assert [s.describe() for s in searches] == ["a", "b @ Toronto"]
            assert cutoff.tzinfo is not None
            return FeedResult(
                items=[
                    {
                        "title": "T",
                        "url": "https://www.linkedin.com/jobs/view/1",
                        "postedAt": "2026-11-26",
                        "description": "d",
                    }
                ],
                warnings=["one warning"],
            )

    class _FakeBrowser:
        def __init__(self, **kwargs):
            self.page = object()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def load_session(self, path):
            pass

    args = build_parser().parse_args(
        ["feed", "--search", "a", "--search", "b @ Toronto", "--since-hours", "24"]
    )
    code = await run_command(
        args,
        env={},
        cwd=tmp_path,
        home=tmp_path,
        browser_factory=_FakeBrowser,
        scraper_factories={"job": _FakeJob, "job_feed": _FakeFeed},
    )
    assert code == 0
    captured = capsys.readouterr()
    warning_lines = [ln for ln in captured.err.splitlines() if ln.startswith("{")]
    assert any(json.loads(ln).get("warning") == "one warning" for ln in warning_lines)
    data = json.loads(captured.out)
    assert data[0]["title"] == "T"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_feed_partial_returns_exit_8_and_json_marker(tmp_path, capsys):
    (tmp_path / "linkedin_session.json").write_text("{}")

    class _FakeJob:
        def __init__(self, page, callback=None):
            pass

    class _FakeFeed:
        def __init__(self, page, callback=None, detail_scraper=None):
            pass

        async def collect(self, searches, cutoff, **kwargs):
            return FeedResult(
                items=[
                    {
                        "title": "T",
                        "url": "https://www.linkedin.com/jobs/view/1",
                    }
                ],
                reason="max-results",
            )

    class _FakeBrowser:
        def __init__(self, **kwargs):
            self.page = object()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def load_session(self, path):
            pass

    args = build_parser().parse_args(["feed", "--search", "a"])
    code = await run_command(
        args,
        env={},
        cwd=tmp_path,
        home=tmp_path,
        browser_factory=_FakeBrowser,
        scraper_factories={"job": _FakeJob, "job_feed": _FakeFeed},
    )
    assert code == EXIT_PARTIAL
    captured = capsys.readouterr()
    assert json.loads(captured.out)[0]["title"] == "T"
    markers = [json.loads(ln) for ln in captured.err.splitlines() if ln.startswith("{")]
    assert markers == [{"partial": True, "reason": "max-results", "count": 1}]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_feed_requires_searches_and_auth(tmp_path):
    (tmp_path / "linkedin_session.json").write_text("{}")

    class _Dummy:
        def __init__(self, page, callback=None, detail_scraper=None):
            pass

    class _FakeBrowser:
        def __init__(self, **kwargs):
            self.page = object()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def load_session(self, path):
            pass

    parser = build_parser()

    with pytest.raises(CliUsageError):
        await run_command(
            parser.parse_args(["feed"]),
            env={},
            cwd=tmp_path,
            home=tmp_path,
            browser_factory=_FakeBrowser,
            scraper_factories={"job": _Dummy, "job_feed": _Dummy},
        )

    with pytest.raises(CliUsageError):
        await run_command(
            parser.parse_args(["feed", "--search", "a", "--search-file", str(tmp_path / "nope.json")]),
            env={},
            cwd=tmp_path,
            home=tmp_path,
            browser_factory=_FakeBrowser,
            scraper_factories={"job": _Dummy, "job_feed": _Dummy},
        )

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AuthenticationError):
        await run_command(
            parser.parse_args(["feed", "--search", "a"]),
            env={},
            cwd=empty,
            home=empty,
            browser_factory=_FakeBrowser,
            scraper_factories={"job": _Dummy, "job_feed": _Dummy},
        )


@pytest.mark.unit
def test_main_feed_errors_are_json_by_default(tmp_path, monkeypatch, capsys):
    from linkedin_scraper.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LINKEDIN_SESSION_PATH", raising=False)
    monkeypatch.delenv("LINKEDIN_LI_AT", raising=False)

    code = main(["feed", "--search", "python"])
    assert code == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err)
    assert payload["error_type"] == "AuthenticationError"
