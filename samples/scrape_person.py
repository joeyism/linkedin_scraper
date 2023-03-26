from selenium import webdriver
import time
import sys

# setting path
sys.path.append('../linkedin_scraper')
from linkedin_scraper import actions, Person

driver = webdriver.Chrome("./chromedriver")
time.sleep(2)
driver.maximize_window()
time.sleep(3)

email = "info@bargad.ai"
password = "Fizza123@"
actions.login(driver, email, password) # if email and password isnt given, it'll prompt in terminal
time.sleep(2)

person = Person("https://www.linkedin.com/in/swagatobag", driver=driver)

print(vars(person))
