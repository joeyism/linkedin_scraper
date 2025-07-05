from os.path import basename, dirname, isfile

from .company import Company
from .job_search import JobSearch
from .jobs import Job
from .objects import Contact, Education, Experience, Institution
from .person import Person

__version__ = "2.11.5"

import glob

modules = glob.glob(dirname(__file__) + "/*.py")
__all__ = [
    basename(f)[:-3] for f in modules if isfile(f) and not f.endswith("__init__.py")
] + [
    "Company",
    "JobSearch",
    "Job",
    "Contact",
    "Education",
    "Experience",
    "Institution",
    "Person",
]
