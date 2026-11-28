"""Unit tests for all 5 scraper CLI commands using injected fakes."""
import json

import pytest

from linkedin_scraper.cli.errors import CliUsageError, EXIT_OK
from linkedin_scraper.cli.parser import build_parser
from linkedin_scraper.cli.runner import run_command
from linkedin_scraper.core.exceptions import AuthenticationError
from linkedin_scraper.models import Company, Job, Person, Post


class _FakeBrowser:
    def __init__(self, **kwargs):
        self.page = object()
        self.loaded_session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def load_session(self, path):
        self.loaded_session = path


def _make_session(tmp_path):
    s = tmp_path / "linkedin_session.json"
    s.write_text("{}")
    return s


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_bad_url_fails_before_launching_browser(tmp_path):
    _make_session(tmp_path)

    def exploding_browser(**kwargs):
        raise AssertionError("Browser should not start on invalid URL")

    args = build_parser().parse_args(
        ["person", "https://www.linkedin.com/company/microsoft/"]
    )
    with pytest.raises(CliUsageError):
        await run_command(
            args, env={}, cwd=tmp_path, home=tmp_path, browser_factory=exploding_browser
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scraper_without_auth_raises_authentication_error(tmp_path):
    args = build_parser().parse_args(
        ["person", "https://www.linkedin.com/in/williamhgates/"]
    )
    with pytest.raises(AuthenticationError):
        await run_command(
            args, env={}, cwd=tmp_path, home=tmp_path, browser_factory=_FakeBrowser
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_command_emits_pure_json_and_verbose_stderr(tmp_path, capsys):
    _make_session(tmp_path)

    class _FakePersonScraper:
        def __init__(self, page, callback=None):
            self.callback = callback

        async def scrape(self, url):
            await self.callback.on_progress("parsed", 50)
            return Person(linkedin_url=url, name="Bill Gates")

    args = build_parser().parse_args(
        ["person", "https://www.linkedin.com/in/williamhgates/", "--verbose"]
    )
    code = await run_command(
        args,
        env={},
        cwd=tmp_path,
        home=tmp_path,
        browser_factory=_FakeBrowser,
        scraper_factories={"person": _FakePersonScraper},
    )
    assert code == EXIT_OK
    captured = capsys.readouterr()
    assert "[50%] parsed" in captured.err
    data = json.loads(captured.out)
    assert data["name"] == "Bill Gates"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_posts_job_and_jobs_commands(tmp_path, capsys):
    _make_session(tmp_path)

    class _FakeCompany:
        def __init__(self, page, callback=None):
            pass

        async def scrape(self, url):
            return Company(linkedin_url=url, name="Microsoft")

    class _FakePosts:
        def __init__(self, page, callback=None):
            pass

        async def scrape(self, url, limit=10):
            return [Post(text=f"post {i}") for i in range(limit)]

    class _FakeJob:
        def __init__(self, page, callback=None):
            pass

        async def scrape(self, url):
            return Job(linkedin_url=url, job_title="Staff Eng", company="Acme")

    class _FakeJobSearch:
        def __init__(self, page, callback=None):
            pass

        async def search(self, keywords=None, location=None, limit=25):
            return [
                f"https://www.linkedin.com/jobs/view/{i}/" for i in range(limit)
            ]

    factories = {
        "company": _FakeCompany,
        "posts": _FakePosts,
        "job": _FakeJob,
        "job_search": _FakeJobSearch,
    }

    # company
    assert (
        await run_command(
            build_parser().parse_args(
                ["company", "https://www.linkedin.com/company/microsoft/"]
            ),
            env={},
            cwd=tmp_path,
            home=tmp_path,
            browser_factory=_FakeBrowser,
            scraper_factories=factories,
        )
        == EXIT_OK
    )
    assert json.loads(capsys.readouterr().out)["name"] == "Microsoft"

    # posts
    assert (
        await run_command(
            build_parser().parse_args(
                ["posts", "https://www.linkedin.com/company/microsoft/", "--limit", "2"]
            ),
            env={},
            cwd=tmp_path,
            home=tmp_path,
            browser_factory=_FakeBrowser,
            scraper_factories=factories,
        )
        == EXIT_OK
    )
    assert len(json.loads(capsys.readouterr().out)) == 2

    # job
    assert (
        await run_command(
            build_parser().parse_args(["job", "https://www.linkedin.com/jobs/view/1/"]),
            env={},
            cwd=tmp_path,
            home=tmp_path,
            browser_factory=_FakeBrowser,
            scraper_factories=factories,
        )
        == EXIT_OK
    )
    assert json.loads(capsys.readouterr().out)["job_title"] == "Staff Eng"

    # jobs (URLs only)
    assert (
        await run_command(
            build_parser().parse_args(["jobs", "python", "--limit", "2"]),
            env={},
            cwd=tmp_path,
            home=tmp_path,
            browser_factory=_FakeBrowser,
            scraper_factories=factories,
        )
        == EXIT_OK
    )
    urls = json.loads(capsys.readouterr().out)
    assert urls == [
        "https://www.linkedin.com/jobs/view/0/",
        "https://www.linkedin.com/jobs/view/1/",
    ]

    # jobs --details
    assert (
        await run_command(
            build_parser().parse_args(["jobs", "python", "--limit", "2", "--details"]),
            env={},
            cwd=tmp_path,
            home=tmp_path,
            browser_factory=_FakeBrowser,
            scraper_factories=factories,
        )
        == EXIT_OK
    )
    jobs = json.loads(capsys.readouterr().out)
    assert len(jobs) == 2 and jobs[0]["job_title"] == "Staff Eng"
