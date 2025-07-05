# Linkedin Scraper

Scrapes Linkedin User Data

[Linkedin Scraper](#linkedin-scraper)
- [Linkedin Scraper](#linkedin-scraper)
  - [Installation](#installation)
  - [Setup](#setup)
    - [Environment Variables](#environment-variables)
    - [ChromeDriver](#chromedriver)
    - [Running Scripts](#running-scripts)
  - [Contributing](#contributing)
    - [Development Workflow](#development-workflow)
  - [Sponsor](#sponsor)
  - [Usage](#usage)
    - [Sample Usage](#sample-usage)
    - [User Scraping](#user-scraping)
    - [Company Scraping](#company-scraping)
    - [Job Scraping](#job-scraping)
    - [Job Search Scraping](#job-search-scraping)
    - [Scraping sites where login is required first](#scraping-sites-where-login-is-required-first)
    - [Scraping sites and login automatically](#scraping-sites-and-login-automatically)
  - [API](#api)
    - [Person](#person)
      - [`linkedin_url`](#linkedin_url)
      - [`name`](#name)
      - [`about`](#about)
      - [`experiences`](#experiences)
      - [`educations`](#educations)
      - [`interests`](#interests)
      - [`accomplishment`](#accomplishment)
      - [`company`](#company)
      - [`job_title`](#job_title)
      - [`driver`](#driver)
      - [`scrape`](#scrape)
      - [`scrape(close_on_complete=True)`](#scrapeclose_on_completetrue)
    - [Company](#company-1)
      - [`linkedin_url`](#linkedin_url-1)
      - [`name`](#name-1)
      - [`about_us`](#about_us)
      - [`website`](#website)
      - [`phone`](#phone)
      - [`headquarters`](#headquarters)
      - [`founded`](#founded)
      - [`company_type`](#company_type)
      - [`company_size`](#company_size)
      - [`specialties`](#specialties)
      - [`showcase_pages`](#showcase_pages)
      - [`affiliated_companies`](#affiliated_companies)
      - [`driver`](#driver-1)
      - [`get_employees`](#get_employees)
      - [`scrape(close_on_complete=True)`](#scrapeclose_on_completetrue-1)
  - [Contribution](#contribution)

## Installation

```bash
# Clone the repository
git clone https://github.com/joeyism/linkedin_scraper.git
cd linkedin_scraper

# Install dependencies
uv sync
```

## Setup

### Environment Variables
Create a `.env` file (copy from `.env.example`) with your LinkedIn credentials:
```bash
cp .env.example .env
# Edit .env with your credentials
```

### ChromeDriver
First, set your chromedriver location by running:

```bash
export CHROMEDRIVER=~/chromedriver
```

### Running Scripts

```bash
# Try the working examples
# Profile
uv run python examples/person_contacts_example.py
uv run python examples/person_profile_example.py
# Company
uv run python examples/company_profile_example.py
# Job Search
uv run python examples/job_search_example.py "python developer"
# Recommended Jobs
uv run python examples/recommended_jobs_example.py
# Job Details of a specific job
uv run python examples/job_details_example.py "https://www.linkedin.com/jobs/view/4097107717"
```

## Contributing

If you want to contribute to this project:

1. **Install development dependencies**:
   ```bash
   uv sync --dev
   ```

2. **Set up pre-commit hooks** (automatically runs linting/formatting on commit):
   ```bash
   uv run pre-commit install
   ```

### Development Workflow

With pre-commit installed, your code will be automatically linted and formatted on every commit.


## Sponsor
Message me if you'd like to sponsor me

## Usage
To use it, just create the class.

### Sample Usage
Try our working examples to get started quickly:

```bash
# Scrape a person's profile and contacts
uv run python examples/person_profile_example.py
uv run python examples/person_contacts_example.py

# Scrape company information and employees
uv run python examples/company_profile_example.py

# Search for jobs and get recommendations
uv run python examples/job_search_example.py "python developer"
uv run python examples/recommended_jobs_example.py

# Get detailed information about a specific job
uv run python examples/job_details_example.py "https://www.linkedin.com/jobs/view/1234567890"
```

All examples use credentials from your `.env` file automatically.


**NOTE**: The account used to log-in should have it's language set English to make sure everything works as expected.

### User Scraping
```python
from linkedin_scraper import Person
person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5")
```

### Company Scraping
```python
from linkedin_scraper import Company
company = Company("https://ca.linkedin.com/company/google")
```

### Job Scraping
```python
from linkedin_scraper import Job, actions
from selenium import webdriver

driver = webdriver.Chrome()
email = "some-email@email.address"
password = "password123"
actions.login(driver, email, password) # if email and password isnt given, it'll prompt in terminal
input("Press Enter")
job = Job("https://www.linkedin.com/jobs/collections/recommended/?currentJobId=3456898261", driver=driver, close_on_complete=False)
```

### Job Search Scraping
```python
from linkedin_scraper import JobSearch, actions
from selenium import webdriver

driver = webdriver.Chrome()
email = "some-email@email.address"
password = "password123"
actions.login(driver, email, password) # if email and password isnt given, it'll prompt in terminal
input("Press Enter")
job_search = JobSearch(driver=driver, close_on_complete=False, scrape=False)
# job_search contains jobs from your logged in front page:
# - job_search.recommended_jobs
# - job_search.still_hiring
# - job_search.more_jobs

job_listings = job_search.search("Machine Learning Engineer") # returns the list of `Job` from the first page
```

### Scraping sites where login is required first
1. Run `ipython` or `python`
2. In `ipython`/`python`, run the following code (you can modify it if you need to specify your driver)
3.
```python
from linkedin_scraper import Person
from selenium import webdriver
driver = webdriver.Chrome()
person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver = driver, scrape=False)
```
4. Login to Linkedin
5. [OPTIONAL] Logout of Linkedin
6. In the same `ipython`/`python` code, run
```python
person.scrape()
```

The reason is that LinkedIn has recently blocked people from viewing certain profiles without having previously signed in. So by setting `scrape=False`, it doesn't automatically scrape the profile, but Chrome will open the linkedin page anyways. You can login and logout, and the cookie will stay in the browser and it won't affect your profile views. Then when you run `person.scrape()`, it'll scrape and close the browser. If you want to keep the browser on so you can scrape others, run it as

**NOTE**: For version >= `2.1.0`, scraping can also occur while logged in. Beware that users will be able to see that you viewed their profile.

```python
person.scrape(close_on_complete=False)
```
so it doesn't close.

### Scraping sites and login automatically
From verison **2.4.0** on, `actions` is a part of the library that allows signing into Linkedin first. The email and password can be provided as a variable into the function. If not provided, both will be prompted in terminal.

```python
import os
from dotenv import load_dotenv
from linkedin_scraper import Person, actions
from selenium import webdriver

# Load environment variables
load_dotenv()

driver = webdriver.Chrome()
email = os.getenv("LINKEDIN_EMAIL")
password = os.getenv("LINKEDIN_PASSWORD")
actions.login(driver, email, password)
person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver=driver)
```


## API

### Person
A Person object can be created with the following inputs:

```python
Person(linkedin_url=None, name=None, about=[], experiences=[], educations=[], interests=[], accomplishments=[], company=None, job_title=None, driver=None, scrape=True)
```
#### `linkedin_url`
This is the linkedin url of their profile

#### `name`
This is the name of the person

#### `about`
This is the small paragraph about the person

#### `experiences`
This is the past experiences they have. A list of `linkedin_scraper.scraper.Experience`

#### `educations`
This is the past educations they have. A list of `linkedin_scraper.scraper.Education`

#### `interests`
This is the interests they have. A list of `linkedin_scraper.scraper.Interest`

#### `accomplishment`
This is the accomplishments they have. A list of `linkedin_scraper.scraper.Accomplishment`

#### `company`
This the most recent company or institution they have worked at.

#### `job_title`
This the most recent job title they have.

#### `driver`
This is the driver from which to scraper the Linkedin profile. A driver using Chrome is created by default. However, if a driver is passed in, that will be used instead.

For example
```python
driver = webdriver.Chrome()
person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver = driver)
```

#### `scrape`
When this is **True**, the scraping happens automatically. To scrape afterwards, that can be run by the `scrape()` function from the `Person` object.


#### `scrape(close_on_complete=True)`
This is the meat of the code, where execution of this function scrapes the profile. If *close_on_complete* is True (which it is by default), then the browser will close upon completion. If scraping of other profiles are desired, then you might want to set that to false so you can keep using the same driver.




### Company

```python
Company(linkedin_url=None, name=None, about_us=None, website=None, phone=None, headquarters=None, founded=None, company_type=None, company_size=None, specialties=None, showcase_pages=[], affiliated_companies=[], driver=None, scrape=True, get_employees=True)
```

#### `linkedin_url`
This is the linkedin url of their profile

#### `name`
This is the name of the company

#### `about_us`
The description of the company

#### `website`
The website of the company

#### `phone`
The phone of the company

#### `headquarters`
The headquarters location of the company

#### `founded`
When the company was founded

#### `company_type`
The type of the company

#### `company_size`
How many people are employeed at the company

#### `specialties`
What the company specializes in

#### `showcase_pages`
Pages that the company owns to showcase their products

#### `affiliated_companies`
Other companies that are affiliated with this one

#### `driver`
This is the driver from which to scraper the Linkedin profile. A driver using Chrome is created by default. However, if a driver is passed in, that will be used instead.

#### `get_employees`
Whether to get all the employees of company

For example
```python
driver = webdriver.Chrome()
company = Company("https://ca.linkedin.com/company/google", driver=driver)
```


#### `scrape(close_on_complete=True)`
This is the meat of the code, where execution of this function scrapes the company. If *close_on_complete* is True (which it is by default), then the browser will close upon completion. If scraping of other companies are desired, then you might want to set that to false so you can keep using the same driver.

## Contribution

<a href="https://www.buymeacoffee.com/joeyism" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>
