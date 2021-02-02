class Contact:
    
    def __init__(
        self,
        name=None,
        occupation=None,
        url=None
    ):

        self.name = name
        self.occupation = occupation
        self.url = url

    def __repr__(self):
        return "{name} ({occupation})".format(
            name=self.name, occupation=self.occupation
        )


class Institution:

    def __init__(
        self,
        institution_name=None,
        website=None,
        industry=None,
        type=None,
        headquarters=None,
        company_size=None,
        founded=None,
    ):
        self.institution_name = institution_name
        self.website = website
        self.industry = industry
        self.type = type
        self.headquarters = headquarters
        self.company_size = company_size
        self.founded = founded


class Experience(Institution):

    def __init__(
        self,
        from_date=None,
        to_date=None,
        description=None,
        position_title=None,
        duration=None,
        location=None,
    ):
        self.from_date = from_date
        self.to_date = to_date
        self.description = description
        self.position_title = position_title
        self.duration = duration
        self.location = location
        super().__init__(self)

    def __repr__(self):
        return "{position_title} at {company} from {from_date} to {to_date} for {duration} based at {location}".format(
            from_date=self.from_date,
            to_date=self.to_date,
            position_title=self.position_title,
            company=self.institution_name,
            duration=self.duration,
            location=self.location,
        )


class Education(Institution):

    def __init__(self, from_date=None, to_date=None, description=None, degree=None):
        self.from_date = from_date
        self.to_date = to_date
        self.description = description
        self.degree = degree
        super().__init__(self)

    def __repr__(self):
        return "{degree} at {company} from {from_date} to {to_date}".format(
            from_date=self.from_date,
            to_date=self.to_date,
            degree=self.degree,
            company=self.institution_name,
        )


class Interest(Institution):

    def __init__(self, title=None):
        self.title = title
        super().__init__(self)

    def __repr__(self):
        return self.title


class Accomplishment(Institution):

    def __init__(self, category=None, title=None):
        self.category = category
        self.title = title
        super().__init__(self)

    def __repr__(self):
        return self.category + ": " + self.title


class Scraper:
    driver = None

    def is_signed_in(self):
        try:
            self.driver.find_element_by_id("profile-nav-item")
            return True
        except:
            pass
        return False

    def __find_element_by_class_name__(self, class_name):
        try:
            self.driver.find_element_by_class_name(class_name)
            return True
        except:
            pass
        return False

    def __find_element_by_xpath__(self, tag_name):
        try:
            self.driver.find_element_by_xpath(tag_name)
            return True
        except:
            pass
        return False

    def __find_enabled_element_by_xpath__(self, tag_name):
        try:
            elem = self.driver.find_element_by_xpath(tag_name)
            return elem.is_enabled()
        except:
            pass
        return False

    @classmethod
    def __find_first_available_element__(cls, *args):
        for elem in args:
            if elem:
                return elem[0]
