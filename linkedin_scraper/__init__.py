from os.path import dirname, basename, isfile
from .person import Person
from .objects import Institution, Experience, Education, Contact
from .company import Company

__version__ = "2.8.1"

import glob
modules = glob.glob(dirname(__file__)+"/*.py")
__all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
