"""Unit tests for `auth status` and `auth login` commands using fake browser/auth."""
import json

import pytest

from linkedin_scraper.cli.errors import EXIT_AUTH, EXIT_OK
from linkedin_scraper.cli.parser import build_parser
from linkedin_scraper.cli.runner import run_command


class _FakePage:
    def __init__(self, url="https://www.linkedin.com/feed/"):
        self.url = url
        self.visited = []

    async def goto(self, url, **kwargs):
        self.visited.append(url)
        self.url = url


class _FakeBrowser:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.page = _FakePage()
        self.loaded_session = None
        self.saved_session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def load_session(self, path):
        self.loaded_session = path

    async def save_session(self, path):
        self.saved_session = path


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_status_without_any_session_returns_exit_auth(tmp_path, capsys):
    args = build_parser().parse_args(["auth", "status"])
    code = await run_command(
        args, env={}, cwd=tmp_path, home=tmp_path, browser_factory=_FakeBrowser
    )
    assert code == EXIT_AUTH
    data = json.loads(capsys.readouterr().out)
    assert data["logged_in"] is False
    assert data["auth_source"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_status_with_valid_session_returns_ok(tmp_path, capsys):
    s = tmp_path / "linkedin_session.json"
    s.write_text("{}")

    async def fake_is_logged_in(page, wait_timeout=0):
        return True

    args = build_parser().parse_args(["auth", "status"])
    code = await run_command(
        args,
        env={},
        cwd=tmp_path,
        home=tmp_path,
        browser_factory=_FakeBrowser,
        auth_funcs={"is_logged_in": fake_is_logged_in},
    )
    assert code == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["logged_in"] is True
    assert data["auth_source"] == {"kind": "session", "value": str(s)}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_login_cookie_saves_session(tmp_path, capsys):
    out_session = tmp_path / "saved.json"
    created = []
    cookie_seen = []

    def factory(**kwargs):
        b = _FakeBrowser(**kwargs)
        created.append(b)
        return b

    async def fake_login_cookie(page, val):
        cookie_seen.append(val)

    args = build_parser().parse_args(
        ["auth", "login", "--cookie", "secret-li-at", "--session", str(out_session)]
    )
    code = await run_command(
        args,
        env={},
        cwd=tmp_path,
        home=tmp_path,
        browser_factory=factory,
        auth_funcs={"login_with_cookie": fake_login_cookie},
    )
    assert code == EXIT_OK
    assert cookie_seen == ["secret-li-at"]
    assert created[0].saved_session == str(out_session)
    data = json.loads(capsys.readouterr().out)
    assert data["saved_session"] == str(out_session)
    assert data["mode"] == "cookie"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auth_login_manual_forces_headed_browser(tmp_path, capsys):
    created = []

    def factory(**kwargs):
        b = _FakeBrowser(**kwargs)
        created.append(b)
        return b

    async def fake_wait_manual(page, timeout=300000):
        assert timeout == 120000

    args = build_parser().parse_args(["auth", "login", "--manual", "--timeout", "120"])
    code = await run_command(
        args,
        env={},
        cwd=tmp_path,
        home=tmp_path,
        browser_factory=factory,
        auth_funcs={"wait_for_manual_login": fake_wait_manual},
    )
    assert code == EXIT_OK
    assert created[0].kwargs["headless"] is False
    assert created[0].page.visited == ["https://www.linkedin.com/login"]
