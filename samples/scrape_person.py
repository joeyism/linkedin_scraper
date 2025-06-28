import os

from selenium import webdriver

from linkedin_scraper import Person, actions

driver = webdriver.Chrome("./chromedriver")

email = os.getenv("LINKEDIN_USER")
password = os.getenv("LINKEDIN_PASSWORD")
actions.login(
    driver, email, password
)  # if email and password isnt given, it'll prompt in terminal
person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver=driver)
