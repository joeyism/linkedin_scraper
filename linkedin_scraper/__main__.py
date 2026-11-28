"""Allow `python -m linkedin_scraper ...` invocation."""

from .cli import cli_entry

if __name__ == "__main__":
    cli_entry()
