"""Auth source resolution and target URL validation for the CLI."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from .errors import CliUsageError


@dataclass(frozen=True)
class AuthSource:
    """Resolved authentication method (`session` file path or `cookie` value)."""

    kind: str  # "session" | "cookie"
    value: str


_URL_RULES = {
    "person": ("linkedin.com/in/", "https://www.linkedin.com/in/<username>/"),
    "company": ("linkedin.com/company/", "https://www.linkedin.com/company/<slug>/"),
    "posts": ("linkedin.com/company/", "https://www.linkedin.com/company/<slug>/"),
    "job": ("linkedin.com/jobs/", "https://www.linkedin.com/jobs/view/<id>/"),
}


def resolve_auth_source(
    session_arg: Optional[str],
    cookie_arg: Optional[str],
    env: Mapping[str, str],
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Optional[AuthSource]:
    """Resolve auth with precedence:

    1. ``--session`` flag (must exist)
    2. ``$LINKEDIN_SESSION_PATH`` (must exist if set)
    3. ``--cookie`` flag
    4. ``$LINKEDIN_LI_AT``
    5. ``./linkedin_session.json`` (if exists)
    6. ``~/.config/linkedin-scraper/session.json`` (if exists)
    """
    cwd = cwd or Path.cwd()
    home = home or Path.home()

    if session_arg:
        path = Path(session_arg).expanduser()
        if not path.exists():
            raise CliUsageError(f"Session file not found: {session_arg}")
        return AuthSource(kind="session", value=str(path))

    env_session = env.get("LINKEDIN_SESSION_PATH")
    if env_session:
        path = Path(env_session).expanduser()
        if not path.exists():
            raise CliUsageError(
                f"Session file from LINKEDIN_SESSION_PATH not found: {env_session}"
            )
        return AuthSource(kind="session", value=str(path))

    if cookie_arg:
        return AuthSource(kind="cookie", value=cookie_arg)

    env_cookie = env.get("LINKEDIN_LI_AT")
    if env_cookie:
        return AuthSource(kind="cookie", value=env_cookie)

    local_session = cwd / "linkedin_session.json"
    if local_session.exists():
        return AuthSource(kind="session", value=str(local_session))

    xdg_session = home / ".config" / "linkedin-scraper" / "session.json"
    if xdg_session.exists():
        return AuthSource(kind="session", value=str(xdg_session))

    return None


def default_session_save_path(
    session_arg: Optional[str],
    env: Mapping[str, str],
    cwd: Optional[Path] = None,
) -> str:
    """Target file path when ``auth login`` persists a session."""
    if session_arg:
        return session_arg
    if env.get("LINKEDIN_SESSION_PATH"):
        return env["LINKEDIN_SESSION_PATH"]
    return str((cwd or Path.cwd()) / "linkedin_session.json")


def validate_target_url(kind: str, url: str) -> str:
    """Fail fast with CliUsageError before starting Playwright on bad URLs."""
    needle, example = _URL_RULES[kind]
    if needle not in url:
        raise CliUsageError(
            f"Invalid {kind} URL '{url}'. Expected a URL containing '{needle}' "
            f"(e.g. {example})."
        )
    return url
