
Linkedin Scraper
================

Scrapes Linkedin User Data

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

Usage
-----

To use it, just create the class.

SAMPLE USAGE

.. code-block:: python

   from linkedin_scraper import Person, actions
   from selenium import webdriver
   driver = webdriver.Chrome()

   email = "some-email@email.address"
   password = "password123"
   actions.login(driver, email, password) # if email and password isnt given, it'll prompt in terminal
   person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver=driver)

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

Overall, to a Person object can be created with the following inputs:

.. code-block:: python

   Person(linkedin_url=None, experiences=[], educations=[], driver=None, scrape=True)

``linkedin_url``
~~~~~~~~~~~~~~~~~~~~

This is the linkedin url of their profile

``experiences``
~~~~~~~~~~~~~~~~~~~

This is the past experiences they have. A list of ``linkedin_scraper.scraper.Experience``

``educations``
~~~~~~~~~~~~~~~~~~

This is the past educations they have. A list of ``linkedin_scraper.scraper.Education``

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is the meat of the code, where execution of this function scrapes the profile. If *close_on_complete* is True (which it is by default), then the browser will close upon completion. If scraping of other profiles are desired, then you might want to set that to false so you can keep using the same driver.

Company
^^^^^^^

.. code-block:: python

   Company(linkedin_url=None, name=None, about_us=one, website=None, headquarters=None, founded=None, company_type=None, company_size=None, specialties=None, showcase_pages=], affiliated_companies=[], driver=None, scrape=True, get_employees=True)

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is the meat of the code, where execution of this function scrapes the company. If *close_on_complete* is True (which it is by default), then the browser will close upon completion. If scraping of other companies are desired, then you might want to set that to false so you can keep using the same driver.

Versions
--------

**2.4.0**


* Added ``actions`` for login

**2.3.1**


* Fixed bugs

**2.2.x**


* Scraping employees allowed

**2.1.x**


* Scraping allowed after logged in

**2.0.x**


* Modified the way the objects are called
* Added Company
* Changed name from ``linkedin_user_scraper`` to ``linkedin_scraper``

**1.2.x**


* Allows scraping later

**1.1.x**


* Addes additional API where user can use their own webdriver

**1.0.x**


* first publish and fixes
