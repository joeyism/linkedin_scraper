"""Tests for PersonScraper."""
from pathlib import Path

import pytest
from linkedin_scraper import PersonScraper
from linkedin_scraper.models import Person


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_basic(browser_with_session, test_profile_urls, silent_callback):
    """Test basic person scraping functionality."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["bill_gates"])
    
    assert isinstance(person, Person)
    assert person.name == "Bill Gates"
    assert person.linkedin_url == test_profile_urls["bill_gates"]
    assert person.location is not None
    assert len(person.experiences) > 0
    assert len(person.educations) > 0


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_experiences(browser_with_session, test_profile_urls, silent_callback):
    """Test experience extraction."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["satya_nadella"])
    
    assert len(person.experiences) > 0
    
    # Check first experience has required fields
    exp = person.experiences[0]
    assert exp.position_title is not None
    assert exp.institution_name is not None
    assert exp.linkedin_url is not None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_educations(browser_with_session, test_profile_urls, silent_callback):
    """Test education extraction."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["bill_gates"])
    
    assert len(person.educations) > 0
    
    # Check first education has required fields
    edu = person.educations[0]
    assert edu.institution_name is not None
    assert edu.linkedin_url is not None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_about(browser_with_session, test_profile_urls, silent_callback):
    """Test about section extraction."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["bill_gates"])
    
    # Bill Gates has an about section
    assert person.about is not None
    assert len(person.about) > 0


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_person_scraper_complex_profile(browser_with_session, test_profile_urls, silent_callback):
    """Test scraping a complex profile with many experiences."""
    scraper = PersonScraper(browser_with_session.page, callback=silent_callback)
    person = await scraper.scrape(test_profile_urls["reid_hoffman"])
    
    # Reid Hoffman has many experiences
    assert len(person.experiences) > 10
    assert person.name == "Reid Hoffman"
    assert person.about is not None


@pytest.mark.unit
def test_person_model_to_dict():
    """Test Person model to_dict conversion."""
    from linkedin_scraper.models import Person, Experience
    
    person = Person(
        linkedin_url="https://linkedin.com/in/test",
        name="Test User",
        location="Test Location",
        about="Test About",
        open_to_work=False,
        experiences=[],
        educations=[],
        interests=[],
        accomplishments=[],
        contacts=[]
    )
    
    data = person.to_dict()
    assert data["name"] == "Test User"
    assert data["location"] == "Test Location"
    assert isinstance(data, dict)


@pytest.mark.unit
def test_person_model_to_json():
    """Test Person model to_json conversion."""
    from linkedin_scraper.models import Person
    
    person = Person(
        linkedin_url="https://linkedin.com/in/test",
        name="Test User",
        location="Test Location",
        about=None,
        open_to_work=False,
        experiences=[],
        educations=[],
        interests=[],
        accomplishments=[],
        contacts=[]
    )
    
    json_str = person.to_json()
    assert isinstance(json_str, str)
    assert "Test User" in json_str


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_scraper_grouped_experiences_main_page(browser, silent_callback):
    """Parse grouped main-page experiences without misassigning company names."""
    fixture_path = Path(__file__).parent / "fixtures" / "person_experience_grouped.html"
    html = fixture_path.read_text(encoding="utf-8")

    await browser.page.set_content(html)

    scraper = PersonScraper(browser.page, callback=silent_callback)
    experiences = await scraper._get_experiences_from_main_page()

    assert len(experiences) == 2
    titles = {exp.position_title for exp in experiences}
    assert titles == {"Mobile Engineer", "Backend Engineer"}
    assert all(exp.institution_name == "Example Corp" for exp in experiences)
    assert all(exp.employment_type == "Full-time" for exp in experiences)
    assert all(
        exp.linkedin_url == "https://www.linkedin.com/company/999999/"
        for exp in experiences
    )

    mobile = next(exp for exp in experiences if exp.position_title == "Mobile Engineer")
    assert mobile.from_date == "Oct 2021"
    assert mobile.to_date == "Aug 2022"
    assert mobile.duration is None
    assert mobile.location == "Remote"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_person_scraper_grouped_experiences_details_page(browser, silent_callback):
    """Parse grouped details-page experiences without misassigning company names."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "person_experience_details_grouped.html"
    )
    html = fixture_path.read_text(encoding="utf-8")

    await browser.page.set_content(html)

    scraper = PersonScraper(browser.page, callback=silent_callback)
    items = await browser.page.locator(".pvs-list__paged-list-item").all()
    experiences = []

    for item in items:
        result = await scraper._parse_experience_item(item)
        if result:
            if isinstance(result, list):
                experiences.extend(result)
            else:
                experiences.append(result)

    assert len(experiences) == 3

    example_roles = [
        exp for exp in experiences if exp.institution_name == "Example Holdings"
    ]
    assert {exp.position_title for exp in example_roles} == {
        "Lead Engineer",
        "Full Stack Developer",
    }
    assert all(
        exp.linkedin_url == "https://www.linkedin.com/company/111111/"
        for exp in example_roles
    )
    assert all(exp.employment_type == "Full-time" for exp in example_roles)

    technical = next(
        exp for exp in example_roles if exp.position_title == "Lead Engineer"
    )
    assert technical.from_date == "Jan 2021"
    assert technical.to_date == "Present"
    assert technical.duration == "5 yrs 2 mos"
    assert technical.location == "Sample City, Country"
    assert technical.description and "Led API work" in technical.description

    pixx = next(exp for exp in experiences if exp.position_title == "Software Engineer")
    assert pixx.institution_name == "Acme Labs"
    assert pixx.employment_type == "Contract"
    assert pixx.from_date == "Apr 2018"
    assert pixx.to_date == "Dec 2018"
    assert pixx.duration == "9 mos"
    assert pixx.location == "Coastal Region"
