import os
from pprint import pprint

from dotenv import load_dotenv
from selenium import webdriver

from linkedin_scraper import JobSearch, actions


def main():
    load_dotenv()
    driver = webdriver.Chrome()
    actions.login(driver, os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD"))

    # Create JobSearch instance and scrape recommended jobs
    job_search = JobSearch(
        driver=driver,
        close_on_complete=False,
        scrape=True,
        scrape_recommended_jobs=True,
    )
    recommended_jobs = getattr(job_search, "recommended_jobs", [])

    print("Recommended Jobs:")
    if recommended_jobs:
        for i, job in enumerate(recommended_jobs):
            print(f"\n--- Recommendation {i + 1} ---")
            pprint(vars(job))
    else:
        print("No recommended jobs found.")


if __name__ == "__main__":
    main()
