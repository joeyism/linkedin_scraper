from distutils.core import setup
setup(
        name = 'linkedin_user_scraper',
        packages = ['linkedin_user_scraper'], # this must be the same as the name above
        version = '0.0.1',
        description = 'Scrapes user data from Linkedin',
        author = 'Joey Sham',
        author_email = 'sham.joey@gmail.com',
        url = 'https://github.com/joeyism/linkedin_user_scraper', # use the URL to the github repo
        download_url = 'https://github.com/joeyism/linkedin_user_scraper/archive/0.0.1.tar.gz',
        keywords = ['linkedin', 'scraping', 'scraper'], 
        classifiers = [],
        install_requires=['lxml', 'request', 'selenium'],
        )
