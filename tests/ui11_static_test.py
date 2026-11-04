#!/usr/bin/env python3
"""Validate portable V9 front-end markup without pretending browser execution."""
import pathlib
import subprocess
import unittest
from html.parser import HTMLParser

ROOT=pathlib.Path(__file__).resolve().parents[1]

class IDs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.scripts=[]
        self.buttons=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='script':self.scripts.append(attrs.get('src'))
        if tag=='button':self.buttons.append(attrs)

class UiTests(unittest.TestCase):
    def test_pages_have_unique_ids_and_activity_panel(self):
        for page in ('index.html','pc.html'):
            with self.subTest(page=page):
                p=IDs()
                p.feed((ROOT/'bridge'/'web'/page).read_text(encoding='utf-8'))
                self.assertEqual(len(p.ids),len(set(p.ids)))
                for expected in ('status','pair','connected','activity','message','queue'):
                    self.assertIn(expected,p.ids)
                self.assertIn('/ui.js',p.scripts)
    def test_custom_and_presets_still_available(self):
        p=IDs();p.feed((ROOT/'bridge'/'web'/'index.html').read_text())
        self.assertGreaterEqual(len([b for b in p.buttons if b.get('data-preset')]),7)
        self.assertIn('sendCustom',p.ids)
    def test_javascript_syntax(self):
        r=subprocess.run(['node','--check',str(ROOT/'bridge'/'web'/'ui.js')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
