#!/usr/bin/env python3
import unittest
from unittest.mock import patch
from vendor_package_inventory import bind_candidate, inventory


class VendorInventoryTests(unittest.TestCase):
    @patch('vendor_package_inventory.Path.rglob', return_value=[])
    @patch('vendor_package_inventory.command')
    def test_records_real_package_source_and_policy(self, command, _):
        command.side_effect = ['libexample1\t1.0-1\tarm64\texample\t1.0-1\tinstalled', 'libexample1:\n  Installed: 1.0-1\n  Candidate: 1.0-2\n']
        result = inventory(['libexample1'])['packages'][0]
        self.assertEqual(result['source_package'], 'example')
        self.assertEqual(result['installed'], '1.0-1')
        self.assertEqual(result['candidate'], '1.0-2')
        self.assertEqual(result['arch'], 'arm64')

    def test_rejects_shell_or_option_injection(self):
        for value in ('--help', 'libc6;id', '../../etc/passwd', 'libc6\nfoo'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                inventory([value])

    @patch('vendor_package_inventory.command')
    def test_rejects_not_installed(self, command):
        command.return_value = 'libexample1\t1.0-1\tarm64\texample\t1.0-1\tnot-installed'
        with self.assertRaises(ValueError):
            inventory(['libexample1'])

    @patch('vendor_package_inventory.command')
    def test_rejects_missing_candidate(self, command):
        command.side_effect = ['libexample1\t1.0-1\tarm64\texample\t1.0-1\tinstalled', '  Candidate: (none)\n']
        with self.assertRaises(ValueError):
            inventory(['libexample1'])

    @patch('vendor_package_inventory.command', return_value='arm64\n')
    def test_binds_exact_candidate_and_observed_arch(self, _):
        candidate = {'image_id': 'sha256:' + 'a' * 64, 'manifest_digest': 'sha256:' + 'b' * 64, 'arch': 'arm64'}
        result = bind_candidate({'packages': [{'arch': 'all'}, {'arch': 'arm64'}]}, candidate)
        self.assertEqual(result['candidate'], candidate)
        self.assertEqual(result['observed_arch'], 'arm64')
        for change in ({'arch': 'amd64'}, {'image_id': ''}, {'manifest_digest': 'bogus'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                bind_candidate({'packages': []}, dict(candidate, **change))
        with self.assertRaises(ValueError):
            bind_candidate({'packages': [{'arch': 'amd64'}]}, candidate)


if __name__ == '__main__':
    unittest.main()
