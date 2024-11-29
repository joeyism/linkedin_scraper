import os
from typing import List
from time import sleep
import urllib.parse

from .objects import Scraper
from .jobs import Job

class PeopleSearch(Scraper):
    AREAS = ["recommended_jobs", None, "still_hiring", "more_jobs"]

    def __init__(self, driver, base_url="https://www.linkedin.com/", close_on_complete=False, scrape=True, scrape_recommended_jobs=True):
        super().__init__()
        self.driver = driver
        self.base_url = base_url

        if scrape:
            self.scrape(close_on_complete, scrape_recommended_jobs)


    def scrape(self, close_on_complete=True, scrape_recommended_jobs=True):
        if self.is_signed_in():
            self.scrape_logged_in(close_on_complete=close_on_complete, scrape_recommended_jobs=scrape_recommended_jobs)
        else:
            raise NotImplemented("This part is not implemented yet")


    def scrape_people_card(self, base_element) -> Job:
        title_span = self.wait_for_element_to_load(name="entity-result__title-text", base=base_element)
        people_link = self.wait_for_element_to_load(name="app-aware-link", base=title_span)
        return people_link.get_attribute("href").split("?")[0]


    def scrape_logged_in(self, close_on_complete=True, scrape_recommended_jobs=True):
        driver = self.driver
        driver.get(self.base_url)
        if scrape_recommended_jobs:
            self.focus()
            sleep(self.WAIT_FOR_ELEMENT_TIMEOUT)
            job_area = self.wait_for_element_to_load(name="scaffold-finite-scroll__content")
            areas = self.wait_for_all_elements_to_load(name="artdeco-card", base=job_area)
            for i, area in enumerate(areas):
                area_name = self.AREAS[i]
                if not area_name:
                    continue
                area_results = []
                for job_posting in area.find_elements_by_class_name("jobs-job-board-list__item"):
                    job = self.scrape_people_card(job_posting)
                    area_results.append(job)
                setattr(self, area_name, area_results)
        return


    def search(self, search_term: str) -> List[Job]:
        url = os.path.join(self.base_url, "search/results/people/") + f"?keywords={urllib.parse.quote(search_term)}&refresh=true"
        self.driver.get(url)
        self.scroll_to_bottom()
        #self.focus()
        sleep(self.WAIT_FOR_ELEMENT_TIMEOUT)

        people_list_class_name = "entity-result"
        job_listing = self.wait_for_element_to_load(name=people_list_class_name)

        self.scroll_class_name_element_to_page_percent(people_list_class_name, 0.3)
        #self.focus()
        sleep(self.WAIT_FOR_ELEMENT_TIMEOUT)

        self.scroll_class_name_element_to_page_percent(people_list_class_name, 0.6)
        #self.focus()
        sleep(self.WAIT_FOR_ELEMENT_TIMEOUT)

        self.scroll_class_name_element_to_page_percent(people_list_class_name, 1)
        #self.focus()
        sleep(self.WAIT_FOR_ELEMENT_TIMEOUT)

        people_profiles = []
        for people_card in self.wait_for_all_elements_to_load(name="entity-result__item", base=job_listing):
            people = self.scrape_people_card(people_card)
            people_profiles.append(people)
        return people_profiles
