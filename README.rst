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
