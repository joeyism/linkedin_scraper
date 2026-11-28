"""Unit tests for pure parsing helpers (no network)."""
import pytest

from linkedin_scraper.scrapers.company import CompanyScraper
from linkedin_scraper.scrapers.company_posts import CompanyPostsScraper
from linkedin_scraper.scrapers.person import PersonScraper


@pytest.fixture
def person_parser():
    return PersonScraper(page=None)


@pytest.fixture
def posts_parser():
    return CompanyPostsScraper(page=None)


@pytest.mark.unit
def test_parse_work_times_en_dash(person_parser):
    assert person_parser._parse_work_times("2000 – Present") == (
        "2000",
        "Present",
        None,
    )


@pytest.mark.unit
def test_parse_work_times_with_duration(person_parser):
    assert person_parser._parse_work_times("Jan 2025 – Present · 1 yr 11 mos") == (
        "Jan 2025",
        "Present",
        "1 yr 11 mos",
    )


@pytest.mark.unit
def test_parse_education_times_range(person_parser):
    assert person_parser._parse_education_times("1973 – 1975") == ("1973", "1975")


@pytest.mark.unit
def test_parse_education_times_single_year(person_parser):
    assert person_parser._parse_education_times("2015") == ("2015", "2015")


@pytest.mark.unit
def test_parse_accomplishment_issued_by(person_parser):
    acc = person_parser._parse_accomplishment(
        ["Sigillum Magnum", "Issued by University of Bologna · Sep 2023"],
        "honor",
    )
    assert acc.title == "Sigillum Magnum"
    assert acc.issuer == "University of Bologna"
    assert acc.issued_date == "Sep 2023"


@pytest.mark.unit
def test_parse_accomplishment_publication(person_parser):
    acc = person_parser._parse_accomplishment(
        ["Superagency", "Authors Equity · Jan 28, 2025"],
        "publication",
    )
    assert acc.title == "Superagency"
    assert acc.issuer == "Authors Equity"
    assert acc.issued_date == "Jan 28, 2025"


@pytest.mark.unit
def test_parse_post_count(posts_parser):
    assert posts_parser._parse_count("1,234 reactions") == 1234


@pytest.mark.unit
def test_parse_post_time(posts_parser):
    assert posts_parser._extract_time_from_text("8h • Edited") == "8h"


@pytest.mark.unit
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.linkedin.com/company/microsoft/", "https://www.linkedin.com/company/microsoft/about/"),
        ("https://www.linkedin.com/company/microsoft/about/", "https://www.linkedin.com/company/microsoft/about/"),
        ("https://www.linkedin.com/company/microsoft/life/", "https://www.linkedin.com/company/microsoft/about/"),
    ],
)
def test_build_about_url(url, expected):
    assert CompanyScraper(page=None)._build_about_url(url) == expected


@pytest.mark.unit
@pytest.mark.asyncio
async def test_company_posts_skips_sponsored_cards():
    class _FakePage:
        async def evaluate(self, script, arg=None):
            return [
                {
                    "urn": "urn:li:activity:111",
                    "sponsored": False,
                    "text": "organic post about books",
                    "timeText": "10h",
                    "reactions": "152",
                    "comments": "21",
                    "reposts": "13",
                    "images": [],
                },
                {
                    "urn": None,
                    "sponsored": True,
                    "text": "Joey, Hiring Pro goes beyond job posting",
                    "timeText": "",
                    "reactions": "",
                    "comments": "",
                    "reposts": "",
                    "images": [],
                },
                {
                    "urn": "urn:li:activity:222",
                    "sponsored": False,
                    "text": "another organic post about mentors",
                    "timeText": "1d",
                    "reactions": "182",
                    "comments": "22",
                    "reposts": "27",
                    "images": [],
                },
            ]

    posts = await CompanyPostsScraper(page=_FakePage())._extract_posts_via_js()
    assert [p.urn for p in posts] == ["urn:li:activity:111", "urn:li:activity:222"]
    assert all(p.linkedin_url for p in posts)
