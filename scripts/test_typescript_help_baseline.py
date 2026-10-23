#!/usr/bin/env python3
import unittest
from verify_typescript_help_baseline import PREFIX, verify


class HelpBaselineTests(unittest.TestCase):
    def setUp(self):
        self.reference = 'Version FakeTSVersion\n' + PREFIX + ' ' * 67 + '\x1b[44m     \x1b[39;49m\n--strict  Enable strict checks\n'
        self.actual = self.reference.replace(PREFIX + ' ' * 67, PREFIX + ' ' * 71)

    def test_accepts_only_release_length_padding_delta(self):
        evidence = verify(self.reference, self.actual)
        self.assertEqual(evidence['padding_delta'], 4)
        self.assertFalse(evidence['reference_modified'])
        self.assertFalse(evidence['tests_skipped'])

    def test_rejects_other_changes(self):
        values = [self.reference, self.actual + 'new option\n', self.actual.replace('--strict', '--changed'), self.actual.replace(' ' * 71, ' ' * 70), self.actual.replace('\x1b[44m', '\x1b[42m')]
        for actual in values:
            with self.subTest(actual=repr(actual)), self.assertRaises(ValueError):
                verify(self.reference, actual)


if __name__ == '__main__':
    unittest.main()
