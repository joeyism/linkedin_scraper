import requests
from lxml import html
from selenium import webdriver
from .functions import time_divide
import os

class Person(object):
    name = None
    experiences = []
    educations = []
    also_viewed_urls = []
    linkedin_url = None
    driver = None

    def __init__(self, linkedin_url = None, experiences = [], educations = [], driver = None, scrape = True):
        self.linkedin_url = linkedin_url
        self.experiences = experiences
        self.educations = educations

        if driver is None:
            try:
                if os.getenv("CHROMEDRIVER") == None:
                    driver_path = os.path.join(os.path.dirname(__file__), 'drivers/chromedriver')
                else:
                    driver_path = os.getenv("CHROMEDRIVER")

                driver = webdriver.Chrome(driver_path)
            except:
                driver = webdriver.Chrome()

        driver.get(linkedin_url)
        self.driver = driver

        if scrape:
            self.scrape()


    def add_experience(self, experience):
        self.experiences.append(experience)

    def add_education(self, education):
        self.educations.append(education)

    def scrape(self, close_on_complete=True):
        driver = self.driver
        page = driver.get(self.linkedin_url)

        # get name
        self.name = driver.find_element_by_id("name").text

        # get experience
        exp = driver.find_element_by_id("experience")
        for position in exp.find_elements_by_class_name("position"):
            position_title = position.find_element_by_class_name("item-title").text
            company = position.find_element_by_class_name("item-subtitle").text

            try:
                times = position.find_element_by_class_name("date-range").text
                from_date, to_date, duration = time_divide(times)
            except:
                from_date, to_date = (None, None)
            experience = Experience( position_title = position_title , from_date = from_date , to_date = to_date)
            experience.institution_name = company
            self.add_experience(experience)

        # get education
        edu = driver.find_element_by_id("education")
        for school in edu.find_elements_by_class_name("school"):
            university = school.find_element_by_class_name("item-title").text
            degree = school.find_element_by_class_name("original").text
            try:
                times = school.find_element_by_class_name("date-range").text
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


