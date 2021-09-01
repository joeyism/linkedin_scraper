import getpass
from . import constants as c
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import random

def __prompt_email_password():
  u = input("Email: ")
  p = getpass.getpass(prompt="Password: ")
  return (u, p)

def page_has_loaded(driver):
    page_state = driver.execute_script('return document.readyState;')
    return page_state == 'complete'

def login(driver, email=None, password=None, cookie = None, timeout=10):
  if cookie is not None:
    return _login_with_cookie(driver, cookie)

  if not email or not password:
    email, password = __prompt_email_password()

  driver.get("https://www.linkedin.com/login")
  element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))

  email_elem = driver.find_element_by_id("username")
  email_elem.send_keys(email)

  password_elem = driver.find_element_by_id("password")
  password_elem.send_keys(password)
  password_elem.submit()

  try:
    if driver.url == 'https://www.linkedin.com/checkpoint/lg/login-submit':
      remember = driver.find_element_by_id(c.REMEMBER_PROMPT)
      if remember:
        remember.submit()

    element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, c.VERIFY_LOGIN_ID)))
  except: pass
  
def pick_random_connection(driver):
    "Choose a LinkedIn connection to follow, at random."
    # Maximise the screen because the chat crap is blocking the button.
    driver.maximize_window()
    connections_list_member = driver.find_elements_by_class_name("feed-follows-module-recommendation.member")
    connections_list_company = driver.find_elements_by_class_name("feed-follows-module-recommendation.company")
    connections_list = connections_list_member + connections_list_company
    random_number = random.randint(0, len(connections_list))
    button = connections_list[random_number].find_element(By.TAG_NAME, "button")
    button.click()
    
def _login_with_cookie(driver, cookie):
  driver.get("https://www.linkedin.com/login")
  driver.add_cookie({
    "name": "li_at",
    "value": cookie
  })
