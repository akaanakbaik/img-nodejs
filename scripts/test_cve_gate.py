#!/usr/bin/env python3
"""Exercise the actual jq predicates in the priority-CVE workflow gate."""
import json
from pathlib import Path
import re
import subprocess
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/publish.yml'

class CveGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        section = WORKFLOW.read_text().split('name: Block CVE-2026-111497 at every severity', 1)[1].split('\n      - name:', 1)[0]
        cls.expressions = re.findall(r"jq -e '([^']+)'", section)
        if len(cls.expressions) != 2:
            raise AssertionError('expected schema and CVE predicates from the real workflow')

    def accepts(self, report):
        return all(subprocess.run(['jq', '-e', expression], input=json.dumps(report), text=True, capture_output=True).returncode == 0 for expression in self.expressions)

    def test_priority_cve_blocked_for_every_severity(self):
        for severity in ('UNKNOWN', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
            with self.subTest(severity=severity):
                self.assertFalse(self.accepts({'Results': [{'Vulnerabilities': [{'VulnerabilityID': 'CVE-2026-111497', 'Severity': severity, 'Status': 'affected'}]}]}))

    def test_no_blanket_exception_for_reported_fixed_status(self):
        self.assertFalse(self.accepts({'Results': [{'Vulnerabilities': [{'VulnerabilityID': 'CVE-2026-111497', 'Severity': 'UNKNOWN', 'Status': 'fixed'}]}]}))

    def test_malformed_or_missing_results_rejected(self):
        for report in ({}, None, [], {'Results': None}):
            with self.subTest(report=report):
                self.assertFalse(self.accepts(report))

    def test_report_without_priority_cve_passes_this_gate_only(self):
        # HIGH/CRITICAL gates are separate and are not bypassed by this result.
        self.assertTrue(self.accepts({'Results': []}))
        self.assertTrue(self.accepts({'Results': [{'Vulnerabilities': [{'VulnerabilityID': 'CVE-OTHER', 'Severity': 'HIGH'}]}]}))

if __name__ == '__main__':
    unittest.main()
