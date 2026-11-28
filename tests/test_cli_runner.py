"""Unit tests for schema command and JSON output writing."""
import json

import pytest

from linkedin_scraper.cli.parser import build_parser
from linkedin_scraper.cli.runner import run_command


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schema_person_outputs_valid_json_schema(capsys):
    args = build_parser().parse_args(["schema", "person"])
    code = await run_command(args)
    assert code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    data = json.loads(captured.out)
    assert data["title"] == "Person"
    assert "experiences" in data["properties"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schema_all_includes_every_model(capsys):
    args = build_parser().parse_args(["schema", "all", "--compact"])
    code = await run_command(args)
    assert code == 0
    out = capsys.readouterr().out.strip()
    assert "\n" not in out  # compact single-line JSON
    data = json.loads(out)
    assert set(data.keys()) == {"person", "company", "post", "job", "feed"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_output_flag_writes_file_and_keeps_stdout_empty(tmp_path, capsys):
    out_file = tmp_path / "job_schema.json"
    args = build_parser().parse_args(["schema", "job", "-o", str(out_file)])
    code = await run_command(args)
    assert code == 0
    assert capsys.readouterr().out == ""
    data = json.loads(out_file.read_text())
    assert data["title"] == "Job"
