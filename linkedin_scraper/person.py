import requests
from lxml import html
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .functions import time_divide
from .objects import Experience, Education, Scraper
import os

class Person(Scraper):
    name = None
    experiences = []
    educations = []
    also_viewed_urls = []
    linkedin_url = None

    def __init__(self, linkedin_url=None, name=None, experiences=[], educations=[], driver=None, get=True, scrape=True):
        self.linkedin_url = linkedin_url
        self.name = name
        self.experiences = experiences or []
        self.educations = educations or []

        if driver is None:
            try:
                if os.getenv("CHROMEDRIVER") == None:
                    driver_path = os.path.join(os.path.dirname(__file__), 'drivers/chromedriver')
                else:
                    driver_path = os.getenv("CHROMEDRIVER")

                driver = webdriver.Chrome(driver_path)
            except:
                driver = webdriver.Chrome()

        if get:
            driver.get(linkedin_url)

        self.driver = driver

        if scrape:
            self.scrape()


    def add_experience(self, experience):
        self.experiences.append(experience)

    def add_education(self, education):
        self.educations.append(education)

    def scrape(self, close_on_complete=True):
        if self.is_signed_in():
            self.scrape_logged_in(close_on_complete = close_on_complete)
        else:
            self.scrape_not_logged_in(close_on_complete = close_on_complete)

    def scrape_logged_in(self, close_on_complete=True):
        driver = self.driver
        root = driver.find_element_by_class_name("pv-top-card-v3")
        self.name = root.find_elements_by_xpath("//section/div/div/div/*/li")[0].text.strip()

        driver.execute_script("window.scrollTo(0, Math.ceil(document.body.scrollHeight/2));")

        _ = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, "experience-section")))

        # get experience
        exp = driver.find_element_by_id("experience-section")
        for position in exp.find_elements_by_class_name("pv-position-entity"):
            position_title = position.find_element_by_tag_name("h3").text.strip()
            company = position.find_element_by_class_name("pv-entity__secondary-title").text.strip()

            try:
                times = position.find_element_by_class_name("pv-entity__date-range").text.strip()
                times = "\n".join(times.split("\n")[1:])
                from_date, to_date, duration = time_divide(times)
            except:
                from_date, to_date, duration = ("Unknown", "Unknown", "Unknown")
            try:
                location = position.find_element_by_class_name("pv-entity__location").text.strip()
            except:
                location = None
            experience = Experience( position_title = position_title , from_date = from_date , to_date = to_date, duration = duration, location = location)
            experience.institution_name = company
            self.add_experience(experience)

        driver.execute_script("window.scrollTo(0, Math.ceil(document.body.scrollHeight/1.5));")

        _ = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, "education-section")))

        # get education
        edu = driver.find_element_by_id("education-section")
        for school in edu.find_elements_by_class_name("pv-education-entity"):
            university = school.find_element_by_class_name("pv-entity__school-name").text.strip()
            degree = "Unknown Degree"
            try:
                degree = school.find_element_by_class_name("pv-entity__degree-name").text.strip()
                times = school.find_element_by_class_name("pv-entity__dates").text.strip()
                from_date, to_date, duration = time_divide(times)
            except:
                from_date, to_date = ("Unknown", "Unknown")
            education = Education(from_date = from_date, to_date = to_date, degree=degree)
            education.institution_name = university
            self.add_education(education)

        if close_on_complete:
            driver.close()


    def scrape_not_logged_in(self, close_on_complete=True, retry_limit=10):
        driver = self.driver
        retry_times = 0
        while self.is_signed_in() and retry_times <= retry_limit:
            page = driver.get(self.linkedin_url)
            retry_times = retry_times + 1


        # get name
        self.name = driver.find_element_by_id("name").text.strip()

        # get experience
        exp = driver.find_element_by_id("experience")
        for position in exp.find_elements_by_class_name("position"):
            position_title = position.find_element_by_class_name("item-title").text.strip()
            company = position.find_element_by_class_name("item-subtitle").text.strip()

            try:
                times = position.find_element_by_class_name("date-range").text.strip()
                from_date, to_date, duration = time_divide(times)
            except:
                from_date, to_date, duration = (None, None, None)

            try:
                location = position.find_element_by_class_name("location").text.strip()
            except:
                location = None
            experience = Experience( position_title = position_title , from_date = from_date , to_date = to_date, duration = duration, location = location)
            experience.institution_name = company
            self.add_experience(experience)

        # get education
        edu = driver.find_element_by_id("education")
        for school in edu.find_elements_by_class_name("school"):
            university = school.find_element_by_class_name("item-title").text.strip()
            degree = school.find_element_by_class_name("original").text.strip()
            try:
                times = school.find_element_by_class_name("date-range").text.strip()
                from_date, to_date, duration = time_divide(times)
            except:
                from_date, to_date = (None, None)
            education = Education(from_date = from_date, to_date = to_date, degree=degree)
            education.institution_name = university
            self.add_education(education)

        # get
        if close_on_complete:
            driver.close()

    def __repr__(self):
        return "{name}\n\nExperience\n{exp}\n\nEducation\n{edu}".format(name = self.name, exp = self.experiences, edu = self.educations)
