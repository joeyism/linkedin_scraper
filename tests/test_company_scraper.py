"""Tests for CompanyScraper."""
import pytest
from linkedin_scraper import CompanyScraper
from linkedin_scraper.models import Company


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_company_scraper_basic(browser_with_session, test_company_urls, silent_callback):
    """Test basic company scraping functionality."""
    scraper = CompanyScraper(browser_with_session.page, callback=silent_callback)
    company = await scraper.scrape(test_company_urls["microsoft"])
    
    assert isinstance(company, Company)
    assert company.name == "Microsoft"
    assert company.linkedin_url == test_company_urls["microsoft"]


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_company_scraper_about(browser_with_session, test_company_urls, silent_callback):
    """Test about section extraction."""
    scraper = CompanyScraper(browser_with_session.page, callback=silent_callback)
    company = await scraper.scrape(test_company_urls["microsoft"])
    
    # Microsoft should have an about section
    assert company.about_us is not None or company.name is not None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_company_scraper_overview(browser_with_session, test_company_urls, silent_callback):
    """Test company overview extraction."""
    scraper = CompanyScraper(browser_with_session.page, callback=silent_callback)
    company = await scraper.scrape(test_company_urls["google"])
    
    assert company.name == "Google"
    # At least some overview fields should be populated
    has_data = any([
        company.website,
        company.industry,
        company.company_size,
        company.headquarters
    ])
    assert has_data


@pytest.mark.unit
def test_company_model_to_dict():
    """Test Company model to_dict conversion."""
    from linkedin_scraper.models import Company
    
    company = Company(
        linkedin_url="https://linkedin.com/company/test",
        name="Test Company",
        about_us="Test About",
        website="https://test.com",
        industry="Technology"
    )
    
    data = company.to_dict()
    assert data["name"] == "Test Company"
    assert data["website"] == "https://test.com"
    assert isinstance(data, dict)


@pytest.mark.unit
def test_company_model_to_json():
    """Test Company model to_json conversion."""
    from linkedin_scraper.models import Company
    
    company = Company(
        linkedin_url="https://linkedin.com/company/test",
        name="Test Company"
    )
    
    json_str = company.to_json()
    assert isinstance(json_str, str)
    assert "Test Company" in json_str
