"""Offline regression checks for endpoint credentials in public summaries."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluate import redact_api_base


class EndpointRedactionCase(unittest.TestCase):
    def test_query_without_path_is_not_part_of_the_host(self):
        self.assertEqual(redact_api_base('https://example.test?token=REVIEW_TOKEN'),
                         'https://example.test')

    def test_fragment_without_path_is_removed(self):
        self.assertEqual(redact_api_base('https://example.test#REVIEW_TOKEN'),
                         'https://example.test')

    def test_userinfo_path_and_query_are_removed(self):
        self.assertEqual(redact_api_base('https://user:REVIEW_TOKEN@example.test/v1?key=REVIEW_TOKEN'),
                         'https://example.test')

    def test_ipv6_and_port_are_preserved(self):
        self.assertEqual(redact_api_base('http://user:REVIEW_TOKEN@[::1]:8080/v1'),
                         'http://[::1]:8080')

    def test_invalid_or_empty_url_does_not_expose_the_input(self):
        self.assertEqual(redact_api_base('https://example.test:REVIEW_TOKEN/v1'), '<redacted>')
        self.assertEqual(redact_api_base('https://[REVIEW_TOKEN'), '<redacted>')
        self.assertEqual(redact_api_base(''), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
