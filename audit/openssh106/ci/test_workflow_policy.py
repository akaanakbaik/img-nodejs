"""Regression checks for the static-only OpenSSH audit workflow boundary."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "openssh-audit.yml"
CI_DIR = Path(__file__).resolve().parent


class WorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = WORKFLOW.read_text(encoding="utf-8")
        cls.lines = []
        for raw_line in cls.raw.splitlines():
            line = raw_line.split("#", 1)[0].rstrip()
            if line.strip():
                cls.lines.append(line)

    def root_keys(self):
        return [
            match.group(1)
            for line in self.lines
            if (match := re.match(r"^([A-Za-z0-9_-]+):(?:\s|$)", line))
        ]

    def section(self, key):
        marker = f"{key}:"
        start = self.lines.index(marker) + 1
        end = start
        while end < len(self.lines) and self.lines[end][:1].isspace():
            end += 1
        return self.lines[start:end]

    def test_workflow_has_only_expected_top_level_sections(self):
        self.assertEqual(self.root_keys(), ["name", "on", "permissions", "jobs"])

    def test_only_opened_synchronized_or_reopened_pull_requests_trigger(self):
        self.assertEqual(
            self.section("on"),
            [
                "  pull_request:",
                "    types: [opened, synchronize, reopened]",
                "    paths:",
                '      - ".github/workflows/openssh-audit.yml"',
                '      - "audit/openssh106/**"',
                '      - "README.md"',
            ],
        )

    def test_permissions_are_contents_read_only(self):
        self.assertEqual(self.section("permissions"), ["  contents: read"])

    def test_single_job_is_same_repository_static_only(self):
        self.assertEqual(
            self.section("jobs"),
            [
                "  policy-check:",
                "    if: github.event.pull_request.head.repo.full_name == github.repository",
                "    name: Enforce audit workflow no-publish boundary",
                "    runs-on: ubuntu-24.04",
                "    timeout-minutes: 5",
                "    steps:",
                "      - name: Check out source",
                "        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
                "        with:",
                "          persist-credentials: false",
                "      - name: Test workflow policy (static only)",
                "        run: python3 -I -S audit/openssh106/ci/test_workflow_policy.py -v",
            ],
        )

    def test_ci_directory_has_only_the_allowlisted_checker(self):
        python_files = sorted(path.name for path in CI_DIR.glob("*.py"))
        self.assertEqual(python_files, ["test_workflow_policy.py"])

    def test_all_external_actions_use_reviewed_full_sha_pins(self):
        uses_lines = [line.strip() for line in self.lines if re.match(r"^\s*uses:", line)]
        self.assertEqual(len(uses_lines), 1)
        self.assertRegex(
            uses_lines[0],
            r"^uses: actions/checkout@[0-9a-f]{40}$",
        )
        self.assertEqual(
            uses_lines[0],
            "uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        )

    def test_workflow_contains_no_publish_scan_or_artifact_capability(self):
        forbidden = (
            r"(?m)^\s*(?:push|workflow_dispatch|pull_request_target|schedule|workflow_run|repository_dispatch)\s*:",
            r"(?m)^\s*packages\s*:",
            r"(?m)^\s*push\s*:\s*true\s*$",
            r"(?i)docker/(?:login|build-push)-action",
            r"(?i)\bghcr\.io\b",
            r"(?i)\b(?:trivy|upload-artifact|cache-to|artifact upload)\b",
            r"(?i)\$\{\{\s*secrets\.",
            r"(?i)unittest\s+discover",
        )
        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.raw))

    def test_checkout_does_not_persist_credentials(self):
        self.assertEqual(self.raw.count("persist-credentials: false"), 1)

    def test_job_runs_only_the_explicit_checker(self):
        run_lines = [line.strip() for line in self.lines if re.match(r"^\s*run:", line)]
        self.assertEqual(
            run_lines,
            ["run: python3 -I -S audit/openssh106/ci/test_workflow_policy.py -v"],
        )
        self.assertEqual(self.raw.count("uses:"), 1)


if __name__ == "__main__":
    unittest.main()
