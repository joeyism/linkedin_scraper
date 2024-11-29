"""
Test Utils
"""
from typing import Dict, Any
from linkedin_scraper.utils import to_dict
from linkedin_scraper.objects import Contact, Institution
from dataclasses import dataclass
import unittest

@dataclass
class SampleClass:
    _test_var: str
    contact: Contact
    institution: Institution
    def to_dict(self) -> Dict[str, Any]:
        return to_dict(self)

class TestUtils(unittest.TestCase):
    """
    Test Utils
    """
    def test_to_dict(self):
        test_class = SampleClass(
            _test_var = 'test var',
            contact=Contact(
                name='test_name'
            ),
            institution=Institution(
                institution_name= 'test_place'
            )
        )

        test_class_dict = to_dict(test_class)
        expected_output = {
            'contact': {'name':'test_name',
                        'occupation': None,
                        'url': None},
            'institution': {
                'company_size': None,
                'founded': None,
                'headquarters': None,
                'industry': None,
                'institution_name': 'test_place',
                'linkedin_url': None,
                'type': None,
                'website': None
            }
        }
        self.assertEqual(test_class_dict, expected_output)
if __name__ == "__main__":
    unittest.main()