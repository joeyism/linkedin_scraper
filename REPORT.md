# LinkedIn Jobs Collector — Summary

## Problem

The existing `linkedin_scraper` library scrapers were broken for job pages. LinkedIn migrated to a new React SPA architecture with:

- **Randomized CSS class names** (e.g. `_3d4c77c2 e7046641 ...`) that change per deployment
- **No `<h1>` elements** — job titles only exist in `<title>` and raw text
- **Locale-dependent text** — the user's session is Arabic, so English text patterns (`"ago"`, `"applicant"`, `"About the job"`) failed to match
- **Restructured DOM** — old selectors like `.job-details-jobs-unified-top-card__primary-description-container` no longer exist

As a result, the `JobScraper` returned `null` for every field except company name.

---

## What was built

### 1. `collect_jobs.py` — New CLI tool

A standalone script to collect LinkedIn jobs at scale with:

| Feature | Details |
|---|---|
| **Multi-query search** | Comma-separated `--keywords`/`--locations` zipped together |
| **Automatic session reuse** | Loads `linkedin_session.json` |
| **Rate-limit prevention** | Random delay (3–6s default) between scrapes |
| **Incremental saving** | JSONL appends each job immediately (crash-safe) |
| **3 output formats** | `--format jsonl` (default), `json` (pretty array), `csv` (Excel) |
| **Error resilience** | Per-job try/except — skips failures, continues |

### 2. Fixed `linkedin_scraper/scrapers/job.py` — JobScraper rewrite

Every extraction method was rewritten to be resilient against CSS randomization and locale:

| Method | Old approach (broken) | New approach |
|---|---|---|
| `_get_job_title()` | `<h1>` selector | `document.title` split on `\|` (locales: any) |
| `_get_company()` | `a[href*="/company/"]` | Kept same (still works) |
| `_get_company_url()` | Same | Kept same |
| `_get_location()` | Static CSS class + English fallback | Parses `·`-delimited metadata line from `<main>` content block |
| `_get_posted_date()` | Same broken selector + `"ago"` text match | Metadata line parsing + Arabic digit normalization |
| `_get_applicant_count()` | Same broken selector + `"applicant"` text match | Metadata line parsing (locale-independent) |
| `_get_description()` | `h2:has-text("About the job")` + `<article>` | Multi-strategy: (1) find "About" `h2` in 6 languages, extract all text after it from `document.body.innerText` filtered for UI noise; (2) `[data-testid="expandable-text-box"]`; (3) `<main>` content fallback |

---

## Verification

- **3 search queries** tested (Python Developer, Data Scientist, Product Manager)
- **4/4 jobs** scraped successfully with all fields populated
- **0 failures** across all runs
- JSON, CSV, and JSONL formats all produce valid output
- Total runtime for 4 jobs: ~2.5 minutes (with 3–6s delays)

---

## Files changed

| File | Change |
|---|---|
| `collect_jobs.py` | **New** — CLI collector script |
| `linkedin_scraper/scrapers/job.py` | **Rewritten** — all extraction methods |
