from setuptools import setup, find_packages
from codecs import open
from os import path
import re

here = path.abspath(path.dirname(__file__))

version_match = re.search(
    r'^__version__\s*=\s*"(.*)"',
    open('linkedin_scraper/__init__.py').read(),
    re.M
)
if version_match:
    version = version_match.group(1)
else:
    raise RuntimeError("Unable to find version string in linkedin_scraper/__init__.py")

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Basic dependencies only (no database/storage dependencies)
basic_requirements = [
    'playwright>=1.40.0',
    'requests>=2.31.0',
    'lxml>=5.0.0',
    'pydantic>=2.0.0',
    'python-dotenv>=1.0.0',
    'aiofiles>=23.0.0',
]

setup(
    name='linkedin_scraper',
    packages=find_packages(exclude=['tests', 'tests.*', 'samples', 'samples.*']),
    version=version,
    description='Async LinkedIn scraper for profiles, companies, and jobs',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Joey Sham',
    author_email='sham.joey@gmail.com',
    url='https://github.com/joeyism/linkedin_scraper',
    download_url='https://github.com/joeyism/linkedin_scraper/archive/refs/tags/' + version + '.tar.gz',
    keywords=['linkedin', 'scraping', 'scraper', 'async', 'playwright', 'profiles'],
    license='Apache 2.0',
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
    ],
    install_requires=basic_requirements,
    include_package_data=True,
    project_urls={
        'Bug Reports': 'https://github.com/joeyism/linkedin_scraper/issues',
        'Source': 'https://github.com/joeyism/linkedin_scraper',
        'Documentation': 'https://github.com/joeyism/linkedin_scraper#readme',
    },
)
