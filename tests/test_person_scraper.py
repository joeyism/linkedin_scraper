"""Tests for PersonScraper."""
import inspect
import pytest
from linkedin_scraper import PersonScraper
from linkedin_scraper.models import Person
from linkedin_scraper.scrapers._person_links import profile_detail_url
from linkedin_scraper.scrapers._person_parsing import (
    parse_experience_lines,
    parse_experiences_text,
)
from linkedin_scraper.scrapers.person import PersonScraper as PersonScraperCls


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
def test_unwrap_linkedin_safety_redirect():
    raw = (
        "https://www.linkedin.com/safety/go/?url="
        "https%3A%2F%2Fgithub.com%2FKaustubh-Rathi&urlhash=x"
    )
    assert PersonScraperCls._unwrap_href(raw) == "https://github.com/Kaustubh-Rathi"


@pytest.mark.unit
def test_classify_github_link():
    contact = PersonScraperCls._classify_link(
        "https://github.com/Kaustubh-Rathi", "GitHub"
    )
    assert contact.type == "github"
    assert "github.com" in contact.value


@pytest.mark.unit
def test_parse_educations_skips_grade_skills():
    text = """
Education
Indian Institute Of Information Technology Allahabad
Bachelor of Technology - BTech, Information Technology
Grade: 8.52/10
Skills: Keras, PyTorch, +11 skills
More profiles for you
"""
    scraper = PersonScraperCls.__new__(PersonScraperCls)
    edus = scraper._parse_educations_from_text(text)
    assert len(edus) == 1
    assert "Allahabad" in (edus[0].institution_name or "")
    assert "BTech" in (edus[0].degree or "")


@pytest.mark.unit
def test_parse_grouped_experience_retains_roles_and_description():
    lines = [
        "Amazon",
        "2 yrs 8 mos",
        "Software Development Engineer II",
        "Jan 2025 - Present · 1 yr 7 mos",
        "Bengaluru, Karnataka, India · Hybrid",
        "Built distributed services.",
        "Software Development Engineer",
        "May 2023 - Jan 2025 · 1 yr 9 mos",
        "Bengaluru, Karnataka, India",
        "Owned production APIs.",
    ]

    experiences = parse_experience_lines(
        lines, "https://www.linkedin.com/company/amazon/"
    )

    assert [experience.position_title for experience in experiences] == [
        "Software Development Engineer II",
        "Software Development Engineer",
    ]
    assert all(experience.institution_name == "Amazon" for experience in experiences)
    assert all(experience.linkedin_url for experience in experiences)
    assert experiences[0].description == "Built distributed services."


@pytest.mark.unit
def test_parse_single_role_experience_keeps_title_and_company():
    lines = [
        "CEO",
        "Acme Corp · Full-time",
        "Jan 2020 - Present · 6 yrs",
        "Remote",
        "Led product and engineering.",
    ]

    experiences = parse_experience_lines(
        lines, "https://www.linkedin.com/company/acme-corp/"
    )

    assert len(experiences) == 1
    assert experiences[0].position_title == "CEO"
    assert experiences[0].institution_name == "Acme Corp"
    assert experiences[0].linkedin_url == "https://www.linkedin.com/company/acme-corp/"
    assert experiences[0].location == "Remote"
    assert experiences[0].description == "Led product and engineering."


@pytest.mark.unit
def test_parse_single_role_company_first_layout():
    """Some cards emit company logo text before the job title."""
    lines = [
        "Microsoft",
        "Chairman and CEO",
        "Feb 2014 - Present · 12 yrs 6 mos",
        "Greater Seattle Area",
        "Member Board Of Trustees",
    ]

    experiences = parse_experience_lines(
        lines, "https://www.linkedin.com/company/microsoft/"
    )

    assert len(experiences) == 1
    assert experiences[0].position_title == "Chairman and CEO"
    assert experiences[0].institution_name == "Microsoft"
    assert experiences[0].linkedin_url == "https://www.linkedin.com/company/microsoft/"


@pytest.mark.unit
def test_parse_single_role_company_first_with_employment_type():
    lines = [
        "Microsoft",
        "Chairman and CEO · Full-time",
        "Feb 2014 - Present · 12 yrs 6 mos",
        "Greater Seattle Area",
    ]

    experiences = parse_experience_lines(
        lines, "https://www.linkedin.com/company/microsoft/"
    )

    assert len(experiences) == 1
    assert experiences[0].position_title == "Chairman and CEO"
    assert experiences[0].institution_name == "Microsoft"


@pytest.mark.unit
def test_parse_experiences_text_splits_flat_section():
    text = """
Experience
Chairman and CEO
Microsoft
Feb 2014 - Present · 12 yrs 6 mos
Greater Seattle Area
Member Board Of Trustees
University of Chicago
2018 - Present · 8 yrs 7 mos
Board Member
Starbucks
2017 - 2024 · 7 yrs
More profiles for you
"""
    experiences = parse_experiences_text(text)
    assert len(experiences) >= 3
    assert experiences[0].position_title == "Chairman and CEO"
    assert experiences[0].institution_name == "Microsoft"
    assert experiences[1].position_title == "Member Board Of Trustees"
    assert experiences[1].institution_name == "University of Chicago"


@pytest.mark.unit
def test_parse_experience_without_company_url():
    lines = [
        "Independent Consultant",
        "Self-employed",
        "Mar 2019 - Present · 7 yrs",
    ]

    experiences = parse_experience_lines(lines)

    assert len(experiences) == 1
    assert experiences[0].position_title == "Independent Consultant"
    assert experiences[0].institution_name == "Self-employed"
    assert experiences[0].linkedin_url is None


@pytest.mark.unit
def test_parse_education_without_school_url():
    from linkedin_scraper.scrapers._person_parsing import parse_education_lines

    education = parse_education_lines(
        [
            "Example University",
            "Bachelor of Science - BS, Computer Science",
            "2015 - 2019",
        ]
    )

    assert education is not None
    assert education.institution_name == "Example University"
    assert education.linkedin_url is None
    assert "Computer Science" in (education.degree or "")


@pytest.mark.unit
def test_missing_section_heading_does_not_parse_whole_page():
    scraper = PersonScraperCls.__new__(PersonScraperCls)
    assert (
        scraper._section_lines("Name\nHeadline\nFooter", "Experience", {"Footer"}) == []
    )


@pytest.mark.unit
def test_detail_url_handles_profile_without_trailing_slash():
    assert (
        profile_detail_url("https://www.linkedin.com/in/example", "details/experience/")
        == "https://www.linkedin.com/in/example/details/experience/"
    )


@pytest.mark.unit
def test_scrape_keeps_complete_sections_enabled_by_default():
    parameters = inspect.signature(PersonScraperCls.scrape).parameters
    assert parameters["include_interests"].default is True
    assert parameters["include_accomplishments"].default is True


@pytest.mark.unit
def test_plain_contact_fields_are_retained():
    assert PersonScraperCls._map_contact_heading_to_type("Birthday") == "birthday"
    assert PersonScraperCls._map_contact_heading_to_type("Address") == "address"
    assert (
        PersonScraperCls._plain_contact_value("Phone\n+1 555 0100", "Phone")
        == "+1 555 0100"
    )


@pytest.mark.unit
def test_location_from_header_not_suggested_profile():
    text = """
Reid Hoffman
He/Him
Co-Founder, LinkedIn.
United States
·
Contact info
2,781,927 followers
People who follow Reid also follow
Demis Hassabis
Nobel Laureate | Co-Founder & CEO, Google DeepMind
"""
    loc = PersonScraperCls._location_from_header_lines(text, "Reid Hoffman")
    assert loc == "United States"


@pytest.mark.unit
def test_location_from_header_without_headline():
    text = """
Ada Lovelace
London, England, United Kingdom
Contact info
500+ connections
"""
    loc = PersonScraperCls._location_from_header_lines(text, "Ada Lovelace")
    assert loc == "London, England, United Kingdom"
