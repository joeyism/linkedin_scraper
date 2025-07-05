import os
from pprint import pprint

from dotenv import load_dotenv
from selenium import webdriver

from linkedin_scraper import Person, actions


def main():
    load_dotenv()
    driver = webdriver.Chrome()
    actions.login(
        driver,
        os.getenv("LINKEDIN_EMAIL"),
        os.getenv("LINKEDIN_PASSWORD"),
        interactive=True,
    )

    # Example profile
    person = Person("https://www.linkedin.com/in/stickerdaniel/", driver=driver)

    print("Person Profile:")
    pprint(vars(person))


if __name__ == "__main__":
    main()
