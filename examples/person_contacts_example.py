import os

from dotenv import load_dotenv
from selenium import webdriver

from linkedin_scraper import Person, actions


def main():
    load_dotenv()
    driver = webdriver.Chrome()
    actions.login(driver, os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASSWORD"))

    # Example profile
    person = Person(
        "https://www.linkedin.com/in/stickerdaniel/", contacts=[], driver=driver
    )

    for contact in person.contacts:
        print(
            "Contact: "
            + contact.name
            + " - "
            + contact.occupation
            + " -> "
            + contact.url
        )


if __name__ == "__main__":
    main()
