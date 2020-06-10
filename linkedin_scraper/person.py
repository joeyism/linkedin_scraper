import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .objects import Experience, Education, Scraper, Interest, Accomplishment
import os

class Person(Scraper):

    __TOP_CARD = "pv-top-card"

    def __init__(self, linkedin_url=None, name=None, experiences=[], educations=[], interests=[], accomplishments=[], driver=None, get=True, scrape=True, close_on_complete=True):
        self.linkedin_url = linkedin_url
        self.name = name
        self.experiences = experiences
        self.educations = educations
        self.interests = interests
        self.accomplishments = accomplishments
        self.also_viewed_urls = []

        if driver is None:
            try:
                if os.getenv("CHROMEDRIVER") == None:
                    driver_path = os.path.join(os.path.dirname(
                        __file__), 'drivers/chromedriver')
                else:
                    driver_path = os.getenv("CHROMEDRIVER")

                driver = webdriver.Chrome(driver_path)
            except:
                driver = webdriver.Chrome()

        if get:
            driver.get(linkedin_url)

        self.driver = driver

        if scrape:
            self.scrape(close_on_complete)

    def add_experience(self, experience):
        self.experiences.append(experience)

    def add_education(self, education):
        self.educations.append(education)

    def add_interest(self, interest):
        self.interests.append(interest)

    def add_accomplishment(self, accomplishment):
        self.accomplishments.append(accomplishment)

    def add_location(self, location):
        self.location = location

    def scrape(self, close_on_complete=True):

        if self.is_signed_in():
            self.scrape_logged_in(close_on_complete=close_on_complete)
        else:
            print('you are not logged in!')
            x = input(
                'please verify the capcha then press any key to continue...')
            self.scrape_not_logged_in(close_on_complete=close_on_complete)

    def scrape_logged_in(self, close_on_complete=True):
        driver = self.driver
        duration = None

        root = driver.find_element_by_class_name(self.__TOP_CARD)
        self.name = root.find_elements_by_xpath(
            "//section/div/div/div/*/li")[0].text.strip()

        driver.execute_script(
            "window.scrollTo(0, Math.ceil(document.body.scrollHeight/2));")

        # get experience
        try:
            _ = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.ID, "experience-section")))
            exp = driver.find_element_by_id("experience-section")
        except:
            exp = None

        if (exp is not None):
            for position in exp.find_elements_by_class_name("pv-position-entity"):
                position_title = position.find_element_by_tag_name(
                    "h3").text.encode('utf-8').strip()

                try:
                    company = position.find_elements_by_tag_name(
                        "p")[1].text.encode('utf-8').strip()
                    times = str(position.find_elements_by_tag_name("h4")[
                                0].find_elements_by_tag_name("span")[1].text.strip())
                    from_date = " ".join(times.split(' ')[:2])
                    to_date = " ".join(times.split(' ')[3:])
                    duration = position.find_elements_by_tag_name(
                        "h4")[1].find_elements_by_tag_name("span")[1].text.strip()
                    location = position.find_elements_by_tag_name(
                        "h4")[2].find_elements_by_tag_name("span")[1].text.strip()
                except:
                    company = None
                    from_date, to_date, duration, location = (
                        None, None, None, None)

                experience = Experience(position_title=position_title, from_date=from_date,
                                        to_date=to_date, duration=duration, location=location)
                experience.institution_name = company
                self.add_experience(experience)

        # get location
        location = driver.find_element_by_class_name(
            f'{self.__TOP_CARD}--list-bullet')
        location = location.find_element_by_tag_name('li').text
        self.add_location(location)

        driver.execute_script(
            "window.scrollTo(0, Math.ceil(document.body.scrollHeight/1.5));")

        # get education
        try:
            _ = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.ID, "education-section")))
            edu = driver.find_element_by_id("education-section")
        except:
            edu = None

        if (edu is not None):
            for school in edu.find_elements_by_class_name("pv-profile-section__list-item"):
                university = school.find_element_by_class_name(
                    "pv-entity__school-name").text.encode('utf-8').strip()

                try:
                    degree = school.find_element_by_class_name(
                        "pv-entity__degree-name").find_elements_by_tag_name("span")[1].text.encode('utf-8').strip()
                    times = school.find_element_by_class_name(
                        "pv-entity__dates").find_elements_by_tag_name("span")[1].text.strip()
                    from_date, to_date = (times.split(
                        " ")[0], times.split(" ")[2])
                except:
                    degree = None
                    from_date, to_date = (None, None)
                education = Education(
                    from_date=from_date, to_date=to_date, degree=degree)
                education.institution_name = university
                self.add_education(education)

        # get interest
        try:
            _ = WebDriverWait(driver, 3).until(EC.presence_of_element_located(
                (By.XPATH, "//*[@class='pv-profile-section pv-interests-section artdeco-container-card ember-view']")))
            interestContainer = driver.find_element_by_xpath(
                "//*[@class='pv-profile-section pv-interests-section artdeco-container-card ember-view']")
            for interestElement in interestContainer.find_elements_by_xpath("//*[@class='pv-entity__summary-info ember-view']"):
                interest = Interest(interestElement.find_element_by_tag_name(
                    "h3").text.encode('utf-8').strip())
                self.add_interest(interest)
        except:
            pass

        # get accomplishment
        try:
            _ = WebDriverWait(driver, 3).until(EC.presence_of_element_located(
                (By.XPATH, "//*[@class='pv-profile-section pv-accomplishments-section artdeco-container-card ember-view']")))
            acc = driver.find_element_by_xpath(
                "//*[@class='pv-profile-section pv-accomplishments-section artdeco-container-card ember-view']")
            for block in acc.find_elements_by_xpath("//div[@class='pv-accomplishments-block__content break-words']"):
                category = block.find_element_by_tag_name("h3")
                for title in block.find_element_by_tag_name("ul").find_elements_by_tag_name("li"):
                    accomplishment = Accomplishment(category.text, title.text)
                    self.add_accomplishment(accomplishment)
        except:
            pass

        if close_on_complete:
            driver.quit()

    def scrape_not_logged_in(self, close_on_complete=True, retry_limit=10):
        driver = self.driver
        retry_times = 0
        while self.is_signed_in() and retry_times <= retry_limit:
            page = driver.get(self.linkedin_url)
            retry_times = retry_times + 1

        # get name
        self.name = driver.find_element_by_class_name("top-card-layout__title").text.strip()

        # get experience
        try:
            _ = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CLASS_NAME, "experience")))
            exp = driver.find_element_by_class_name("experience")
        except:
            exp = None

        if(exp is not None):
        	for position in exp.find_elements_by_class_name("experience-item__contents"):
        	    position_title = position.find_element_by_class_name(
        	        "experience-item__title").text.strip()
        	    company = position.find_element_by_class_name(
        	        "experience-item__subtitle").text.strip()

        	    try:
        	        times = position.find_element_by_class_name(
        	            "experience-item__duration")
        	        from_date = times.find_element_by_class_name(
        	            "date-range__start-date").text.strip()
        	        try:
        	            to_date = times.find_element_by_class_name(
        	                "date-range__end-date").text.strip()
        	        except:
        	            to_date = "Present"
        	        duration = position.find_element_by_class_name(
        	            "date-range__duration").text.strip()
        	        location = position.find_element_by_class_name(
        	            "experience-item__location").text.strip()
        	    except:
        	        from_date, to_date, duration, location = (
        	            None, None, None, None)

        	    experience = Experience(position_title=position_title, from_date=from_date,
        	                            to_date=to_date, duration=duration, location=location)
        	    experience.institution_name = company
        	    self.add_experience(experience)
        driver.execute_script(
            "window.scrollTo(0, Math.ceil(document.body.scrollHeight/1.5));")

        # get education
        edu = driver.find_element_by_class_name("education__list")
        for school in edu.find_elements_by_class_name("result-card"):
            university = school.find_element_by_class_name(
                "result-card__title").text.strip()
            degree = school.find_element_by_class_name(
                "education__item--degree-info").text.strip()
            try:
                times = school.find_element_by_class_name("date-range")
                from_date = times.find_element_by_class_name(
                    "date-range__start-date").text.strip()
                to_date = times.find_element_by_class_name(
                    "date-range__end-date").text.strip()
            except:
                from_date, to_date = (None, None)
            education = Education(from_date=from_date,
                                  to_date=to_date, degree=degree)
            education.institution_name = university
            self.add_education(education)

        if close_on_complete:
            driver.close()

    def __repr__(self):
        return "{name}\n\nExperience\n{exp}\n\nEducation\n{edu}\n\nInterest\n{int}\n\nAccomplishments\n{acc}".format(name=self.name, exp=self.experiences, edu=self.educations, int=self.interests, acc=self.accomplishments)
