"""Tests for PersonScraper."""
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
