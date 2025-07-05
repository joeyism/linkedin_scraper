# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup and Installation

This is a Python package that scrapes LinkedIn profiles, companies, and job listings using Selenium WebDriver.

### Installation with uv (Recommended)
```bash
# Install dependencies
uv sync

# Install development dependencies (pre-commit hooks, ruff, etc.)
uv sync --dev
```

### Code Quality Tools
This project uses Ruff for linting and formatting, with pre-commit hooks for automation:

```bash
# Install pre-commit hooks (run once)
uv run pre-commit install

# Run pre-commit on all files
uv run pre-commit run --all-files

# Manual ruff commands
uv run ruff check          # Check for linting issues
uv run ruff check --fix    # Fix auto-fixable issues
uv run ruff format         # Format code
uv run ruff format --check # Check if code is properly formatted
```

Pre-commit will automatically run on every commit, ensuring code quality.

### Environment Setup
1. Copy environment template:
```bash
cp .env.example .env
```

2. Edit `.env` with your LinkedIn credentials:
```
LINKEDIN_EMAIL=your-email@example.com
LINKEDIN_PASSWORD=your-password
```

3. ChromeDriver is auto-detected from PATH, or set manually:
```bash
export CHROMEDRIVER=~/chromedriver
```

## Architecture Overview

This is a LinkedIn scraping library with the following core components:

### Core Classes
- **Person** (`linkedin_scraper/person.py`): Scrapes individual LinkedIn profiles including experiences, education, interests, and accomplishments
- **Company** (`linkedin_scraper/company.py`): Scrapes company profiles including about, employees, headquarters, and company details
- **Job** (`linkedin_scraper/jobs.py`): Scrapes individual job postings
- **JobSearch** (`linkedin_scraper/job_search.py`): Performs job searches and returns collections of jobs

### Supporting Modules
- **objects.py**: Contains data model classes (Experience, Education, Institution, Contact, etc.) and base Scraper class
- **selectors.py**: CSS/XPath selectors for different LinkedIn page elements
- **actions.py**: Utility functions including login automation
- **constants.py**: Configuration constants

### Project Structure
```
linkedin_scraper/
├── __init__.py          # Package exports
├── person.py            # Person profile scraping
├── company.py           # Company profile scraping
├── jobs.py              # Job posting scraping
├── job_search.py        # Job search functionality
├── objects.py           # Data models and base classes
├── selectors.py         # Web element selectors
├── actions.py           # Helper functions
└── constants.py         # Configuration constants
```

## Usage Patterns

### WebDriver Management
- Uses Chrome WebDriver by default
- Can accept custom driver instances via `driver` parameter
- Supports `close_on_complete` parameter to control browser cleanup
- WebDriver location configured via `CHROMEDRIVER` environment variable

### Authentication
- Login handled via `actions.login(driver, email, password)`
- Supports both prompted and programmatic credential entry
- Can scrape with or without authentication depending on profile visibility

### Scraping Modes
- **Automatic**: Set `scrape=True` (default) to scrape immediately on instantiation
- **Manual**: Set `scrape=False` to create object first, then call `.scrape()` method later
- **Batch**: Keep `close_on_complete=False` to reuse driver across multiple scrapes

## Development Notes

- This is a setuptools-based Python package (setup.py)
- Version defined in `linkedin_scraper/__init__.py`
- Uses Selenium for browser automation, requests for HTTP, lxml for HTML parsing
- No formal test framework detected - basic test scripts in `test/` directory
- Package distributed via pip as `linkedin_scraper`

## Sample Usage
```python
from linkedin_scraper import Person, Company, actions
from selenium import webdriver

# Setup driver and login
driver = webdriver.Chrome()
actions.login(driver, email, password)

# Scrape person profile
person = Person("https://www.linkedin.com/in/stickerdaniel", driver=driver)

# Scrape company
company = Company("https://www.linkedin.com/company/google", driver=driver)
```
