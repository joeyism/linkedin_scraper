import os
import urllib.parse
from time import sleep

from selenium.webdriver.common.by import By

from .jobs import Job
from .objects import Scraper


class JobSearch(Scraper):
    AREAS = ["recommended_jobs", None, "still_hiring", "more_jobs"]

    def __init__(
        self,
        driver,
        base_url="https://www.linkedin.com/jobs/",
        close_on_complete=False,
        scrape=True,
        scrape_recommended_jobs=True,
    ):
        super().__init__()
        self.driver = driver
        self.base_url = base_url

        if scrape:
            self.scrape(close_on_complete, scrape_recommended_jobs)

    def scrape(self, close_on_complete=True, scrape_recommended_jobs=True):
        if self.is_signed_in():
            self.scrape_logged_in(
                close_on_complete=close_on_complete,
                scrape_recommended_jobs=scrape_recommended_jobs,
            )
        else:
            raise NotImplementedError("This part is not implemented yet")

    def scrape_job_card(self, base_element) -> Job:
        try:
            # Try to find job title and URL using updated selectors
            job_link = base_element.find_element(
                By.CLASS_NAME, "job-card-container__link"
            )
            job_title = job_link.text.strip()
            linkedin_url = job_link.get_attribute("href")

            # Find company name
            company = base_element.find_element(
                By.CLASS_NAME, "artdeco-entity-lockup__subtitle"
            ).text.strip()

            # Find location (try multiple possible selectors)
            location = ""
            try:
                location = base_element.find_element(
                    By.CLASS_NAME, "job-card-container__metadata-wrapper"
                ).text.strip()
            except:
                try:
                    location = base_element.find_element(
                        By.CLASS_NAME, "job-card-container__metadata-item"
                    ).text.strip()
                except:
                    location = "Location not found"

            job = Job(
                linkedin_url=linkedin_url,
                job_title=job_title,
                company=company,
                location=location,
                scrape=False,
                driver=self.driver,
            )
            return job
        except Exception as e:
            print(f"Error scraping job card: {e}")
            return None

    def scrape_logged_in(self, close_on_complete=True, scrape_recommended_jobs=True):
        driver = self.driver
        driver.get(self.base_url)
        if scrape_recommended_jobs:
            sleep(3)  # Wait for page to load

            # Find recommended job cards directly
            job_cards = driver.find_elements(By.CLASS_NAME, "job-card-container")
            print(f"Found {len(job_cards)} recommended jobs")

            recommended_jobs = []
            for job_card in job_cards:
                job = self.scrape_job_card(job_card)
                if job:
                    recommended_jobs.append(job)

            # Set the recommended_jobs attribute
            self.recommended_jobs = recommended_jobs
            print(f"Successfully scraped {len(recommended_jobs)} recommended jobs")

        if close_on_complete:
            driver.close()
        return

    def search(self, search_term: str) -> list[Job]:
        url = (
            os.path.join(self.base_url, "search")
            + f"?keywords={urllib.parse.quote(search_term)}&refresh=true"
        )
        self.driver.get(url)
        self.scroll_to_bottom()
        self.focus()
        sleep(self.WAIT_FOR_ELEMENT_TIMEOUT)

        # Wait for page to load and scroll to load more jobs
        sleep(2)
        self.scroll_to_bottom()
        sleep(2)

        job_results = []
        # Find job cards directly - LinkedIn now uses job-card-container
        job_cards = self.driver.find_elements(By.CLASS_NAME, "job-card-container")

        for job_card in job_cards:
            job = self.scrape_job_card(job_card)
            if job:  # Only add successfully scraped jobs
                job_results.append(job)
        return job_results
