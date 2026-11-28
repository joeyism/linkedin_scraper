"""Unit tests verifying CLI progress never touches stdout."""
import pytest

from linkedin_scraper.cli.callbacks import StderrProgressCallback


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stderr_callback_writes_only_to_stderr(capsys):
    cb = StderrProgressCallback()
    await cb.on_start("person", "https://www.linkedin.com/in/williamhgates/")
    await cb.on_progress("Got name: Bill Gates", 20)
    await cb.on_complete("person", object())
    await cb.on_error(RuntimeError("boom"))

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Starting person" in captured.err
    assert "[20%]" in captured.err
    assert "Completed person" in captured.err
    assert "boom" in captured.err
