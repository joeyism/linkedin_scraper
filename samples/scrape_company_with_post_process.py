import os
import re

from linkedin_scraper import Company, actions
from selenium import webdriver
driver = webdriver.Chrome("./chromedriver")

Company.employees_count = None   # Patch to register more company fields


def post_profile_parsing(driver, cls, data):
    labels = data.get('labels')
    values = data.get('values')
    x_off = data.get('x_off')
    num_attributes = min(len(labels), len(values))

    for i in range(num_attributes):
        txt = labels[i].text.strip()
        if txt == 'Company size':
            try:
                employee_count_txt = values[i + x_off + 1].text.strip()
                if 'on LinkedIn' in employee_count_txt:
                    cls.employees_count = re.sub(r"\D+", "", employee_count_txt, 0, re.MULTILINE)
            except Exception as e:
                assert e


email = os.getenv("LINKEDIN_USER")
password = os.getenv("LINKEDIN_PASSWORD")
actions.login(driver, email, password) # if email and password isn't given, it'll prompt in terminal


company = Company(
    'https://www.linkedin.com/company/national-basketball-association/',
    post_event=post_profile_parsing,
    get_employees=False,
    driver=driver
)
