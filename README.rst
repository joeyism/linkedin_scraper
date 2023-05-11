.. role:: raw-html-m2r(raw)
   :format: html


Linkedin Scraper
================

Scrapes Linkedin User Data

`Linkedin Scraper <#linkedin-scraper>`_


* `Installation <#installation>`_
* `Setup <#setup>`_
* `Usage <#usage>`_

  * `Sample Usage <#sample-usage>`_
  * `User Scraping <#user-scraping>`_
  * `Company Scraping <#company-scraping>`_
  * `Job Scraping <#job-scraping>`_
  * `Job Search Scraping <#job-search-scraping>`_
  * `Scraping sites where login is required first <#scraping-sites-where-login-is-required-first>`_
  * `Scraping sites and login automatically <#scraping-sites-and-login-automatically>`_

* `API <#api>`_

  * `Person <#person>`_

    * `\ ``linkedin_url`` <#linkedin_url>`_
    * `\ ``name`` <#name>`_
    * `\ ``about`` <#about>`_
    * `\ ``experiences`` <#experiences>`_
    * `\ ``educations`` <#educations>`_
    * `\ ``interests`` <#interests>`_
    * `\ ``accomplishment`` <#accomplishment>`_
    * `\ ``company`` <#company>`_
    * `\ ``job_title`` <#job_title>`_
    * `\ ``driver`` <#driver>`_
    * `\ ``scrape`` <#scrape>`_
    * `\ ``scrape(close_on_complete=True)`` <#scrapeclose_on_completetrue>`_

  * `Company <#company>`_

    * `\ ``linkedin_url`` <#linkedin_url-1>`_
    * `\ ``name`` <#name-1>`_
    * `\ ``about_us`` <#about_us>`_
    * `\ ``website`` <#website>`_
    * `\ ``headquarters`` <#headquarters>`_
    * `\ ``founded`` <#founded>`_
    * `\ ``company_type`` <#company_type>`_
    * `\ ``company_size`` <#company_size>`_
    * `\ ``specialties`` <#specialties>`_
    * `\ ``showcase_pages`` <#showcase_pages>`_
    * `\ ``affiliated_companies`` <#affiliated_companies>`_
    * `\ ``driver`` <#driver-1>`_
    * `\ ``get_employees`` <#get_employees>`_
    * `\ ``scrape(close_on_complete=True)`` <#scrapeclose_on_completetrue-1>`_

* `Contribution <#contribution>`_

Installation
------------

.. code-block:: bash

   pip3 install --user linkedin_scraper

Version **2.0.0** and before is called ``linkedin_user_scraper`` and can be installed via ``pip3 install --user linkedin_user_scraper``

Setup
-----

First, you must set your chromedriver location by

.. code-block:: bash

   export CHROMEDRIVER=~/chromedriver

Sponsor 
-----

.. image:: https://raw.githubusercontent.com/joeyism/linkedin_scraper/master/docs/proxycurl.png
   :alt: Proxycurl API
   :target: https://nubela.co/proxycurl/?utm_campaign=influencer%20marketing&utm_source=github&utm_medium=social&utm_term=-&utm_content=joeyism

Scrape public LinkedIn profile data at scale with `Proxycurl APIs <https://nubela.co/proxycurl/?utm_campaign=influencer%20marketing&utm_source=github&utm_medium=social&utm_term=-&utm_content=joeyism>`_.

• Scraping Public profiles are battle tested in court in HiQ VS LinkedIn case.
• GDPR, CCPA, SOC2 compliant
• High rate limit - 300 requests/minute
• Fast - APIs respond in ~2s
• Fresh data - 88% of data is scraped real-time, other 12% are not older than 29 days
• High accuracy
• Tons of data points returned per profile

Built for developers, by developers.

Usage
-----

To use it, just create the class.

Sample Usage
^^^^^^^^^^^^

.. code-block:: python

   from linkedin_scraper import Person, actions
   from selenium import webdriver
   driver = webdriver.Chrome()

   email = "some-email@email.address"
   password = "password123"
   actions.login(driver, email, password) # if email and password isnt given, it'll prompt in terminal
   person = Person("https://www.linkedin.com/in/joey-sham-aa2a50122", driver=driver)

**NOTE**\ : The account used to log-in should have it's language set English to make sure everything works as expected.

User Scraping
^^^^^^^^^^^^^

.. code-block:: python

   from linkedin_scraper import Person
   person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5")

Company Scraping
^^^^^^^^^^^^^^^^

.. code-block:: python

   from linkedin_scraper import Company
   company = Company("https://ca.linkedin.com/company/google")

Job Scraping
^^^^^^^^^^^^

.. code-block:: python

   from linkedin_scraper import JobSearch, actions
   from selenium import webdriver

   driver = webdriver.Chrome()
   email = "some-email@email.address"
   password = "password123"
   actions.login(driver, email, password) # if email and password isnt given, it'll prompt in terminal
   input("Press Enter")
   job = Job("https://www.linkedin.com/jobs/collections/recommended/?currentJobId=3456898261", driver=driver, close_on_complete=False)

Job Search Scraping
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

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

Scraping sites where login is required first
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


#. Run ``ipython`` or ``python``
#. In ``ipython``\ /\ ``python``\ , run the following code (you can modify it if you need to specify your driver)
#. 
   .. code-block:: python

      from linkedin_scraper import Person
      from selenium import webdriver
      driver = webdriver.Chrome()
      person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver = driver, scrape=False)

#. Login to Linkedin
#. [OPTIONAL] Logout of Linkedin
#. In the same ``ipython``\ /\ ``python`` code, run
   .. code-block:: python

      person.scrape()

The reason is that LinkedIn has recently blocked people from viewing certain profiles without having previously signed in. So by setting ``scrape=False``\ , it doesn't automatically scrape the profile, but Chrome will open the linkedin page anyways. You can login and logout, and the cookie will stay in the browser and it won't affect your profile views. Then when you run ``person.scrape()``\ , it'll scrape and close the browser. If you want to keep the browser on so you can scrape others, run it as 

**NOTE**\ : For version >= ``2.1.0``\ , scraping can also occur while logged in. Beware that users will be able to see that you viewed their profile.

.. code-block:: python

   person.scrape(close_on_complete=False)

so it doesn't close.

Scraping sites and login automatically
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

From verison **2.4.0** on, ``actions`` is a part of the library that allows signing into Linkedin first. The email and password can be provided as a variable into the function. If not provided, both will be prompted in terminal.

.. code-block:: python

   from linkedin_scraper import Person, actions
   from selenium import webdriver
   driver = webdriver.Chrome()
   email = "some-email@email.address"
   password = "password123"
   actions.login(driver, email, password) # if email and password isnt given, it'll prompt in terminal
   person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver=driver)

API
---

Person
^^^^^^

A Person object can be created with the following inputs:

.. code-block:: python

   Person(linkedin_url=None, name=None, about=[], experiences=[], educations=[], interests=[], accomplishments=[], company=None, job_title=None, driver=None, scrape=True)

``linkedin_url``
~~~~~~~~~~~~~~~~~~~~

This is the linkedin url of their profile

``name``
~~~~~~~~~~~~

This is the name of the person

``about``
~~~~~~~~~~~~~

This is the small paragraph about the person

``experiences``
~~~~~~~~~~~~~~~~~~~

This is the past experiences they have. A list of ``linkedin_scraper.scraper.Experience``

``educations``
~~~~~~~~~~~~~~~~~~

This is the past educations they have. A list of ``linkedin_scraper.scraper.Education``

``interests``
~~~~~~~~~~~~~~~~~

This is the interests they have. A list of ``linkedin_scraper.scraper.Interest``

``accomplishment``
~~~~~~~~~~~~~~~~~~~~~~

This is the accomplishments they have. A list of ``linkedin_scraper.scraper.Accomplishment``

``company``
~~~~~~~~~~~~~~~

This the most recent company or institution they have worked at. 

``job_title``
~~~~~~~~~~~~~~~~~

This the most recent job title they have. 

``driver``
~~~~~~~~~~~~~~

This is the driver from which to scraper the Linkedin profile. A driver using Chrome is created by default. However, if a driver is passed in, that will be used instead.

For example

.. code-block:: python

   driver = webdriver.Chrome()
   person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver = driver)

``scrape``
~~~~~~~~~~~~~~

When this is **True**\ , the scraping happens automatically. To scrape afterwards, that can be run by the ``scrape()`` function from the ``Person`` object.

``scrape(close_on_complete=True)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the meat of the code, where execution of this function scrapes the profile. If *close_on_complete* is True (which it is by default), then the browser will close upon completion. If scraping of other profiles are desired, then you might want to set that to false so you can keep using the same driver.

Company
^^^^^^^

.. code-block:: python

   Company(linkedin_url=None, name=None, about_us=None, website=None, headquarters=None, founded=None, company_type=None, company_size=None, specialties=None, showcase_pages=[], affiliated_companies=[], driver=None, scrape=True, get_employees=True)

``linkedin_url``
~~~~~~~~~~~~~~~~~~~~

This is the linkedin url of their profile

``name``
~~~~~~~~~~~~

This is the name of the company

``about_us``
~~~~~~~~~~~~~~~~

The description of the company

``website``
~~~~~~~~~~~~~~~

The website of the company

``headquarters``
~~~~~~~~~~~~~~~~~~~~

The headquarters location of the company

``founded``
~~~~~~~~~~~~~~~

When the company was founded

``company_type``
~~~~~~~~~~~~~~~~~~~~

The type of the company

``company_size``
~~~~~~~~~~~~~~~~~~~~

How many people are employeed at the company

``specialties``
~~~~~~~~~~~~~~~~~~~

What the company specializes in

``showcase_pages``
~~~~~~~~~~~~~~~~~~~~~~

Pages that the company owns to showcase their products

``affiliated_companies``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Other companies that are affiliated with this one

``driver``
~~~~~~~~~~~~~~

This is the driver from which to scraper the Linkedin profile. A driver using Chrome is created by default. However, if a driver is passed in, that will be used instead.

``get_employees``
~~~~~~~~~~~~~~~~~~~~~

Whether to get all the employees of company

For example

.. code-block:: python

   driver = webdriver.Chrome()
   company = Company("https://ca.linkedin.com/company/google", driver=driver)

``scrape(close_on_complete=True)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the meat of the code, where execution of this function scrapes the company. If *close_on_complete* is True (which it is by default), then the browser will close upon completion. If scraping of other companies are desired, then you might want to set that to false so you can keep using the same driver.

Contribution
------------

:raw-html-m2r:`<a href="https://www.buymeacoffee.com/joeyism" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>`
