"""Unit tests for CLI session/auth precedence and URL validation."""
import pytest

from linkedin_scraper.cli.errors import CliUsageError
from linkedin_scraper.cli.session import (
    AuthSource,
    default_session_save_path,
    resolve_auth_source,
    validate_target_url,
)


@pytest.mark.unit
def test_explicit_session_flag_beats_everything(tmp_path):
    s = tmp_path / "custom.json"
    s.write_text("{}")
    src = resolve_auth_source(
        session_arg=str(s),
        cookie_arg="cookie-val",
        env={"LINKEDIN_SESSION_PATH": "/other.json", "LINKEDIN_LI_AT": "env-cookie"},
        cwd=tmp_path,
        home=tmp_path,
    )
    assert src == AuthSource(kind="session", value=str(s))


@pytest.mark.unit
def test_missing_explicit_session_raises_usage_error(tmp_path):
    with pytest.raises(CliUsageError, match="Session file not found"):
        resolve_auth_source(
            session_arg=str(tmp_path / "nope.json"),
            cookie_arg=None,
            env={},
            cwd=tmp_path,
            home=tmp_path,
        )


@pytest.mark.unit
def test_precedence_env_session_then_cookie_then_cwd_then_xdg(tmp_path):
    cwd = tmp_path / "cwd"
    home = tmp_path / "home"
    cwd.mkdir()
    xdg = home / ".config" / "linkedin-scraper"
    xdg.mkdir(parents=True)

    xdg_file = xdg / "session.json"
    xdg_file.write_text("{}")
    assert resolve_auth_source(None, None, {}, cwd=cwd, home=home) == AuthSource(
        kind="session", value=str(xdg_file)
    )

    cwd_file = cwd / "linkedin_session.json"
    cwd_file.write_text("{}")
    assert resolve_auth_source(None, None, {}, cwd=cwd, home=home) == AuthSource(
        kind="session", value=str(cwd_file)
    )

    assert resolve_auth_source(
        None, None, {"LINKEDIN_LI_AT": "abc"}, cwd=cwd, home=home
    ) == AuthSource(kind="cookie", value="abc")

    assert resolve_auth_source(
        None, "cli-cookie", {"LINKEDIN_LI_AT": "abc"}, cwd=cwd, home=home
    ) == AuthSource(kind="cookie", value="cli-cookie")

    env_file = tmp_path / "env.json"
    env_file.write_text("{}")
    assert resolve_auth_source(
        None, "cli-cookie", {"LINKEDIN_SESSION_PATH": str(env_file)}, cwd=cwd, home=home
    ) == AuthSource(kind="session", value=str(env_file))


@pytest.mark.unit
def test_no_auth_source_returns_none(tmp_path):
    assert resolve_auth_source(None, None, {}, cwd=tmp_path, home=tmp_path) is None


@pytest.mark.unit
def test_default_session_save_path_prefers_arg_then_env_then_cwd(tmp_path):
    assert default_session_save_path("a.json", {}, cwd=tmp_path) == "a.json"
    assert (
        default_session_save_path(None, {"LINKEDIN_SESSION_PATH": "/x/s.json"}, cwd=tmp_path)
        == "/x/s.json"
    )
    assert default_session_save_path(None, {}, cwd=tmp_path) == str(
        tmp_path / "linkedin_session.json"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "kind,url",
    [
        ("person", "https://www.linkedin.com/in/williamhgates/"),
        ("company", "https://www.linkedin.com/company/microsoft/"),
        ("posts", "https://www.linkedin.com/company/microsoft/"),
        ("job", "https://www.linkedin.com/jobs/view/123456/"),
    ],
)
def test_validate_target_url_accepts_valid(kind, url):
    assert validate_target_url(kind, url) == url


@pytest.mark.unit
@pytest.mark.parametrize(
    "kind,bad_url",
    [
        ("person", "https://www.linkedin.com/company/microsoft/"),
        ("company", "https://www.linkedin.com/in/williamhgates/"),
        ("posts", "https://example.com/company/foo"),
        ("job", "https://www.linkedin.com/in/williamhgates/"),
    ],
)
def test_validate_target_url_rejects_mismatched_urls(kind, bad_url):
    with pytest.raises(CliUsageError):
        validate_target_url(kind, bad_url)
