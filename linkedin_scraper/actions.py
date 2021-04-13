import getpass
from linkedin_scraper.objects import Scraper
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

def __prompt_email_password():
  u = input("Email: ")
  p = getpass.getpass(prompt="Password: ")
  return (u, p)

def page_has_loaded(driver):
    page_state = driver.execute_script('return document.readyState;')
    return page_state == 'complete'

def login(driver, email=None, password=None):
  if not email or not password:
    email, password = __prompt_email_password()

  driver.get("https://www.linkedin.com/login")
  element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))

  email_elem = driver.find_element_by_id("username")
  email_elem.send_keys(email)

  password_elem = driver.find_element_by_id("password")
  password_elem.send_keys(password)
  password_elem.submit()

  element = WebDriverWait(driver, 300).until(EC.presence_of_element_located((By.ID, "profile-nav-item")))
