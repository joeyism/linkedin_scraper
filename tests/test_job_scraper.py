"""Tests for JobScraper and JobSearchScraper."""
import pytest
from linkedin_scraper import JobScraper, JobSearchScraper
from linkedin_scraper.models import Job


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.skip(reason="Job search selector '.jobs-search__results-list' not found - LinkedIn page structure may have changed")
async def test_job_search_scraper(browser_with_session, test_job_search_params, silent_callback):
    """Test job search functionality."""
    scraper = JobSearchScraper(browser_with_session.page, callback=silent_callback)
    job_urls = await scraper.search(
        keywords=test_job_search_params["keywords"],
        location=test_job_search_params["location"],
        limit=test_job_search_params["limit"]
    )
    
    assert isinstance(job_urls, list)
    assert len(job_urls) > 0
    assert len(job_urls) <= test_job_search_params["limit"]
    
    # Check URLs are valid
    for url in job_urls:
        assert "linkedin.com/jobs/view/" in url


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.skip(reason="Job search selector '.jobs-search__results-list' not found - LinkedIn page structure may have changed")
async def test_job_scraper(browser_with_session, test_job_search_params, silent_callback):
    """Test job scraping functionality."""
    # First search for jobs
    search_scraper = JobSearchScraper(browser_with_session.page, callback=silent_callback)
    job_urls = await search_scraper.search(
        keywords=test_job_search_params["keywords"],
        location=test_job_search_params["location"],
        limit=1
    )
    
    if len(job_urls) == 0:
        pytest.skip("No job URLs found in search")
    
    # Then scrape the first job
    job_scraper = JobScraper(browser_with_session.page, callback=silent_callback)
    job = await job_scraper.scrape(job_urls[0])
    
    assert isinstance(job, Job)
    assert job.linkedin_url == job_urls[0]
    assert job.job_title is not None or job.company is not None


@pytest.mark.unit
def test_job_model_to_dict():
    """Test Job model to_dict conversion."""
    from linkedin_scraper.models import Job
    
    job = Job(
        linkedin_url="https://linkedin.com/jobs/view/123456",
        job_title="Software Engineer",
        company="Test Company",
        location="San Francisco, CA"
    )
    
    data = job.to_dict()
    assert data["job_title"] == "Software Engineer"
    assert data["company"] == "Test Company"
    assert isinstance(data, dict)


@pytest.mark.unit
def test_job_model_to_json():
    """Test Job model to_json conversion."""
    from linkedin_scraper.models import Job
    
    job = Job(
        linkedin_url="https://linkedin.com/jobs/view/123456",
        job_title="Software Engineer"
    )
    
    json_str = job.to_json()
    assert isinstance(json_str, str)
    assert "Software Engineer" in json_str
