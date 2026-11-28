"""Unit tests for CLI argument parsing and agent-discoverable --help text."""
import pytest

from linkedin_scraper.cli.parser import build_parser


@pytest.mark.unit
def test_root_help_documents_workflow_auth_and_exit_codes():
    help_text = build_parser().format_help()
    for required in (
        "WORKFLOW",
        "AUTH PRECEDENCE",
        "EXIT CODES",
        "LINKEDIN_SESSION_PATH",
        "LINKEDIN_LI_AT",
        "auth",
        "person",
        "company",
        "posts",
        "job",
        "jobs",
        "schema",
    ):
        assert required in help_text, f"Missing {required!r} in root --help"


@pytest.mark.unit
@pytest.mark.parametrize(
    "cmd_path,expected_snippets",
    [
        (["person"], ["EXAMPLES", "OUTPUT", "schema person", "linkedin.com/in/"]),
        (["company"], ["EXAMPLES", "OUTPUT", "schema company", "linkedin.com/company/"]),
        (["posts"], ["EXAMPLES", "OUTPUT", "schema post", "--limit"]),
        (["job"], ["EXAMPLES", "OUTPUT", "schema job", "linkedin.com/jobs/view/"]),
        (["jobs"], ["EXAMPLES", "OUTPUT", "--details", "--location", "--limit"]),
        (["schema"], ["person", "company", "post", "job"]),
        (["auth"], ["status", "login"]),
        (["auth", "status"], ["EXAMPLES", "logged_in"]),
        (["auth", "login"], ["--cookie", "--env", "--manual", "NON-INTERACTIVE"]),
    ],
)
def test_every_subcommand_help_has_examples_and_contract(cmd_path, expected_snippets, capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(cmd_path + ["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for snippet in expected_snippets:
        assert snippet in out, f"Missing {snippet!r} in `{' '.join(cmd_path)} --help`"


@pytest.mark.unit
def test_global_flags_work_both_before_and_after_subcommand():
    parser = build_parser()
    url = "https://www.linkedin.com/in/williamhgates/"

    before = parser.parse_args(["--session", "s.json", "--headed", "--compact", "person", url])
    after = parser.parse_args(["person", url, "--session", "s.json", "--headed", "--compact"])

    assert before.command == after.command == "person"
    assert before.url == after.url == url
    assert before.session == after.session == "s.json"
    assert before.headed is after.headed is True
    assert before.compact is after.compact is True


@pytest.mark.unit
def test_jobs_search_flags_and_defaults():
    parser = build_parser()
    args = parser.parse_args(
        ["jobs", "staff engineer", "--location", "Toronto", "--limit", "5", "--details"]
    )
    assert args.command == "jobs"
    assert args.keywords == "staff engineer"
    assert args.location == "Toronto"
    assert args.limit == 5
    assert args.details is True


@pytest.mark.unit
def test_auth_login_requires_exactly_one_mode():
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["auth", "login"])
    assert exc.value.code == 2

    args = parser.parse_args(["auth", "login", "--env", "--session", "out.json"])
    assert args.command == "auth"
    assert args.auth_command == "login"
    assert args.env is True
    assert args.session == "out.json"
