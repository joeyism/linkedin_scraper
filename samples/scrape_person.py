import os
from linkedin_scraper import Person, actions, Company
from selenium import webdriver

driver = webdriver.Chrome()

email = os.getenv("LINKEDIN_USER")
password = os.getenv("LINKEDIN_PASSWORD")
actions.login(driver, email, password)  # if email and password isnt given, it'll prompt in terminal
user_input = []
urls = []
while True:
    user_input = input("Enter a comma-separated list of strings: ")
    if user_input == "exit":
        break
    urls = user_input.split(",")
    results = []
    for url in urls:
        print(f'scraping {url}')
        person = Person(url,  driver=driver, close_on_complete=False)
        company = Company(person.experiences[0].linkedin_url, get_employees=False, driver=driver, close_on_complete=False)
        results.append((person, company))

    print('name,location,exp_title,exp_company,exp_linkedin,company_industry,company_website,company_size')
    for person, company in results:
        experience = person.experiences[0]
        print(f'"{person.name}", '
              f'"{person.location}", '
              f'"{experience.position_title}", '
              f'"{experience.institution_name}", '
              f'"{experience.linkedin_url}", '
              f'"{company.industry}", '
              f'"{company.website}", '
              f'"{company.company_size}", '
              )
