import os
import sys
from pprint import pprint

from dotenv import load_dotenv
from selenium import webdriver

from linkedin_scraper import Job, actions


def main():
    if len(sys.argv) < 2:
        print("Usage: python job_details_example.py <job_url>")
        print(
            "Example: python job_details_example.py 'https://www.linkedin.com/jobs/view/3543210987'"
        )
        sys.exit(1)

    load_dotenv()
    driver = webdriver.Chrome()
    actions.login(driver, os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD"))

    job = Job(sys.argv[1], driver=driver)

    print("Job Details:")
    pprint(vars(job))


if __name__ == "__main__":
    main()
