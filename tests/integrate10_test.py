#!/usr/bin/env python3
"""Dry-run / apply / idempotence / no-clobber / static audit tests."""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
import sys
sys.path.insert(0, str(TOOLS))
import integrate_10
import inspect_web_root


class InstallTests(unittest.TestCase):
    def make_webroot(self, parent):
        root = pathlib.Path(parent)
        (root / 'index.html').write_text('<!doctype html><html><body><script src="app.js"></script></body></html>', encoding='utf-8')
        (root / 'app.js').write_text('window.MY_CURRENT_APP="unchanged";', encoding='utf-8')
        return root

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_webroot(td)
            old_index = (root / 'index.html').read_bytes()
            rc = integrate_10.main(['--web-root', td])
            self.assertEqual(rc, 0)
            self.assertEqual(old_index, (root / 'index.html').read_bytes())
            self.assertFalse((root / 'safety').exists())
            self.assertFalse((root / 'diag').exists())

    def test_apply_and_idempotent_no_main_js_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_webroot(td)
            old_js = (root / 'app.js').read_bytes()
            self.assertEqual(integrate_10.main(['--web-root', td, '--apply']), 0)
            first = (root / 'index.html').read_bytes()
            self.assertTrue((root / 'safety' / 'guard-core.js').is_file())
            self.assertTrue((root / 'diag' / 'v9-check.html').is_file())
            self.assertEqual(first.count(b'guard-core.js'), 1)
            self.assertEqual(integrate_10.main(['--web-root', td, '--apply']), 0)
            self.assertEqual(first, (root / 'index.html').read_bytes())
            self.assertEqual((root / 'app.js').read_bytes(), old_js)
            self.assertTrue((root / '.personal_hub_09_rollback' / 'index.html.before_09').is_file())
            self.assertEqual(inspect_web_root.main(['--web-root', td]), 0)

    def test_conflicting_existing_diagnostic_refused_without_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_webroot(td)
            old_index = (root / 'index.html').read_bytes()
            (root / 'diag').mkdir()
            (root / 'diag' / 'v9-check.js').write_text('original user code', encoding='utf-8')
            self.assertEqual(integrate_10.main(['--web-root', td, '--apply']), 2)
            self.assertEqual(old_index, (root / 'index.html').read_bytes())

    def test_missing_index_refused(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(integrate_10.main(['--web-root', td, '--apply']), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
