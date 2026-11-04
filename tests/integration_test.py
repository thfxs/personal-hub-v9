#!/usr/bin/env python3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
TOOL=Path(__file__).resolve().parents[1]/'tools'/'integrate_09.py'

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.original='<!doctype html><body>原有 0.8 功能<script src="app.js"></script></body>\n'
        (self.root/'index.html').write_text(self.original,encoding='utf-8')
    def go(self,apply=False):
        args=[sys.executable,str(TOOL),'--web-root',str(self.root)]
        if apply:args.append('--apply')
        return subprocess.run(args,capture_output=True,text=True)
    def test_dry_run_no_changes(self):
        self.assertEqual(self.go().returncode,0)
        self.assertEqual((self.root/'index.html').read_text(),self.original)
        self.assertFalse((self.root/'safety').exists())
    def test_preserves_original_scripts_and_adds_guard(self):
        p=self.go(True);self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        doc=(self.root/'index.html').read_text()
        self.assertIn('src="app.js"',doc)
        self.assertIn('safety/guard-auto.js',doc)
        self.assertEqual((self.root/'.personal_hub_09_rollback/index.html.before_09').read_text(),self.original)
    def test_idempotent(self):
        self.go(True);original=(self.root/'index.html').read_bytes()
        self.assertEqual(self.go(True).returncode,0)
        self.assertEqual((self.root/'index.html').read_bytes(),original)
    def test_does_not_overwrite_user_changed_safety_files(self):
        self.go(True);(self.root/'safety'/'guard-auto.js').write_text('user edits')
        self.assertEqual(self.go(True).returncode,2)

if __name__=='__main__': unittest.main(verbosity=2)
