import os
from pprint import pprint

from dotenv import load_dotenv
from selenium import webdriver

from linkedin_scraper import Company, actions


def main():
    load_dotenv()
    driver = webdriver.Chrome()
    actions.login(driver, os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD"))

    # Example company - replace with any LinkedIn company URL
    company = Company("https://www.linkedin.com/company/google/", driver=driver)

    print("Company Profile:")
    pprint(vars(company))


if __name__ == "__main__":
    main()
