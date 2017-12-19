Linkedin User Scraper
=====================

Scrapes Linkedin User Data

Installation
------------

::

    > pip3 install --user linkedin_user_scraper

Setup
-----

First, you must set your chromedriver location by

.. code:: bash

    export CHROMEDRIVER=~/chromedriver

Usage
-----

To use it, just create the class

.. code:: python

    from linkedin_user_scraper.scraper import Person
    person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5")

API
---

Overall, to a Person object can be created with the following inputs:

.. code:: python

    Person( linkedin_url=None, experiences = [], educations = [], driver = None, scrape = True)

``linkedin_url``
^^^^^^^^^^^^^^^^

This is the linkedin url of their profile

``experiences``
^^^^^^^^^^^^^^^

This is the past experiences they have. A list of
``linkedin_user_scraper.scraper.Experience``

``educations``
^^^^^^^^^^^^^^

This is the past educations they have. A list of
``linkedin_user_scraper.scraper.Education``

``driver``
^^^^^^^^^^

This is the driver from which to scraper the Linkedin profile. A driver
using Chrome is created by default. However, if a driver is passed in,
that will be used instead.

For example

.. code:: python

    driver = webdriver.Chrome()
    person = Person("https://www.linkedin.com/in/andre-iguodala-65b48ab5", driver = driver)

``scrape(close_on_complete=True)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the meat of the code, where execution of this function scrapes
the profile. If *close_on_complete* is True (which it is by default),
then the browser will close upon completion. If scraping of other
profiles are desired, then you might want to set that to false so you
can keep using the same driver.

``scrape``
^^^^^^^^^^

When this is **True**, the scraping happens automatically. To scrape
afterwards, that can be run by the ``scrape()`` function from the
``Person`` object.

Versions
--------

**1.2.x** \* Allows scraping later

**1.1.x** \* Addes additional API where user can use their own webdriver

**1.0.x** \* first publish and fixes
