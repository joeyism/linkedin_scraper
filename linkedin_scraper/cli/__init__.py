"""Executable CLI package for linkedin_scraper."""

import asyncio
import json
import sys
from typing import Optional, Sequence

from .errors import EXIT_OK, classify_error, format_error_text
from .parser import build_parser
from .runner import run_command


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point returning an OS exit code."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    # The feed command promises structured, machine-readable failures on stderr.
    if getattr(args, "command", None) == "feed":
        args.json_error = True
    try:
        return asyncio.run(run_command(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        code, payload = classify_error(exc)
        if getattr(args, "json_error", False):
            print(json.dumps(payload), file=sys.stderr)
        else:
            print(format_error_text(payload), file=sys.stderr)
        return code


def cli_entry() -> None:
    """Console script hook for `[project.scripts]`."""
    raise SystemExit(main())


__all__ = ["main", "cli_entry", "build_parser", "EXIT_OK"]
