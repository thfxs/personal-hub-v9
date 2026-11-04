#!/usr/bin/env python3
"""Offline unit tests for package identity/version checks."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'check_android_upgrade.py'


class AndroidUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        mod = self.root / 'app'
        mod.mkdir()
        self.gradle = mod / 'build.gradle'
        self.baseline = self.root / 'baseline.json'
        self.baseline.write_text(json.dumps({'applicationId': 'dev.personalhub.v9', 'versionCode': 8}))

    def runcheck(self, appid, version):
        self.gradle.write_text(f'''android {{\n  defaultConfig {{\n    applicationId "{appid}"\n    versionCode {version}\n    versionName "0.9"\n  }}\n}}\n''')
        return subprocess.run([sys.executable, str(SCRIPT), '--project', str(self.root), '--baseline', str(self.baseline)], text=True, capture_output=True)

    def test_version_increment(self):
        p = self.runcheck('dev.personalhub.v9', 9)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('[PASS] versionCode 严格递增', p.stdout)

    def test_block_appid_change(self):
        p = self.runcheck('dev.changed.v9', 9)
        self.assertEqual(p.returncode, 1)
        self.assertIn('[FAIL] applicationId', p.stdout)

    def test_block_same_version(self):
        p = self.runcheck('dev.personalhub.v9', 8)
        self.assertEqual(p.returncode, 1)

    def test_block_lower_version(self):
        p = self.runcheck('dev.personalhub.v9', 5)
        self.assertEqual(p.returncode, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
