#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from runtime_toolchain_inventory import inventory


class ToolchainInventoryTests(unittest.TestCase):
    @patch('runtime_toolchain_inventory.platform.machine', return_value='x86_64')
    def test_native_compiler_identity_and_rejects_mismatches(self, _):
        candidate = {'image_id': 'sha256:' + 'a' * 64, 'manifest_digest': 'sha256:' + 'b' * 64, 'arch': 'amd64'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'package.json').write_text(json.dumps({'name': 'typescript', 'version': '7.0.2'}))
            platform_root = root / 'node_modules/@typescript/typescript-linux-x64'
            (platform_root / 'lib').mkdir(parents=True)
            binary = platform_root / 'lib/tsc'
            binary.write_bytes(b'\x7fELFfixture')
            native = {'name': '@typescript/typescript-linux-x64', 'version': '7.0.2', 'cpu': ['x64'], 'os': ['linux']}
            (platform_root / 'package.json').write_text(json.dumps(native))
            with patch('runtime_toolchain_inventory.shutil.which', return_value=str(binary)):
                result = inventory(candidate, root)
                self.assertEqual(result['candidate'], candidate)
                self.assertEqual(result['native_compilers'][0]['sha256'], hashlib.sha256(binary.read_bytes()).hexdigest())
                for change in ({'arch': 'arm64'}, {'image_id': ''}, {'manifest_digest': ''}):
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        inventory(dict(candidate, **change), root)
                for change in ({'version': '7.1.0-beta'}, {'cpu': ['arm64']}, {'os': ['win32']}):
                    (platform_root / 'package.json').write_text(json.dumps(dict(native, **change)))
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        inventory(candidate, root)
                (platform_root / 'package.json').write_text(json.dumps(native))
                binary.write_bytes(b'not-elf')
                with self.assertRaises(ValueError):
                    inventory(candidate, root)


if __name__ == '__main__':
    unittest.main()
