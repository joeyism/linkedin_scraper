import os
from pprint import pprint

from dotenv import load_dotenv
from selenium import webdriver

from linkedin_scraper import Person, actions


def main():
    load_dotenv()
    driver = webdriver.Chrome()

    # Use cookie from environment
    cookie = os.getenv("LINKEDIN_COOKIE")
    actions.login(driver, cookie=cookie)

    # Example profile
    person = Person("https://www.linkedin.com/in/stickerdaniel/", driver=driver)

    print("Person Profile:")
    pprint(vars(person))


if __name__ == "__main__":
    main()
