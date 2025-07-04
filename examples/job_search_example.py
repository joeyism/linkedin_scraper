import os
import sys
from pprint import pprint

from dotenv import load_dotenv
from selenium import webdriver

from linkedin_scraper import JobSearch, actions


def main():
    if len(sys.argv) < 2:
        print("Usage: python job_search_example.py <keywords>")
        print("Example: python job_search_example.py 'python developer'")
        sys.exit(1)

    load_dotenv()
    driver = webdriver.Chrome()
    actions.login(driver, os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD"))

    keywords = sys.argv[1]

    job_search = JobSearch(driver=driver, close_on_complete=False, scrape=False)
    jobs = job_search.search(keywords)

    print(f"Job Search Results for '{keywords}':")
    for i, job in enumerate(jobs):
        print(f"\n--- Job {i + 1} ---")
        pprint(vars(job))


if __name__ == "__main__":
    main()
