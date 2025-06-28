import os

from dotenv import load_dotenv
from selenium import webdriver

from linkedin_scraper import Person, actions


def main():
    load_dotenv()
    driver = webdriver.Chrome()
    actions.login(driver, os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD"))
    person = Person("https://www.linkedin.com/in/stickerdaniel/", driver=driver)
    print(person)


if __name__ == "__main__":
    main()
