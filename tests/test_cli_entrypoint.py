"""Unit tests for top-level main(), --json-error formatting, and `python -m` execution."""
import json
import subprocess
import sys

import pytest

from linkedin_scraper.cli import main
from linkedin_scraper.cli.errors import EXIT_AUTH, EXIT_OK, EXIT_USAGE


@pytest.mark.unit
def test_main_schema_returns_zero(capsys):
    code = main(["schema", "post"])
    assert code == EXIT_OK
    assert json.loads(capsys.readouterr().out)["title"] == "Post"


@pytest.mark.unit
def test_main_formats_json_error_on_stderr(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LINKEDIN_SESSION_PATH", raising=False)
    monkeypatch.delenv("LINKEDIN_LI_AT", raising=False)
    code = main(
        ["person", "https://www.linkedin.com/in/williamhgates/", "--json-error"]
    )
    assert code == EXIT_AUTH
    captured = capsys.readouterr()
    assert captured.out == ""
    err = json.loads(captured.err)
    assert err["error_type"] == "AuthenticationError"
    assert "hint" in err


@pytest.mark.unit
def test_main_invalid_url_returns_exit_usage(capsys):
    code = main(["person", "https://example.com/not-linkedin"])
    assert code == EXIT_USAGE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "CliUsageError" in captured.err


@pytest.mark.unit
def test_python_m_linkedin_scraper_runs_schema():
    proc = subprocess.run(
        [sys.executable, "-m", "linkedin_scraper", "schema", "company"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["title"] == "Company"
