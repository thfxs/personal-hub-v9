#!/usr/bin/env python3
"""Landscape viewport pagination regression (no claim of HarmonyOS device acceptance)."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'web'

class LandscapePages191(unittest.TestCase):
 def test_layout_and_script_linked(self):
  html=(WEB/'index.html').read_text()
  self.assertIn('landscape-pages-v20.css',html)
  self.assertIn('landscape-pages-v20.js',html)
  self.assertTrue(html.index('swipe-nav.js')<html.index('landscape-pages-v20.js'))
 def test_service_worker_precaches_offline_mode(self):
  sw=(WEB/'sw.js').read_text()
  self.assertIn('personal-hub-shell-v192',sw)
  for name in ['landscape-pages-v20.css','landscape-pages-v20.js']:
   self.assertIn(name,sw)
 def test_no_existing_business_logic_or_hud_mutated(self):
  import hashlib
  self.assertEqual(hashlib.sha256((WEB/'styles.css').read_bytes()).hexdigest(),'0877293e76b59c33fcfc0de1c9c5b0c814699bf23238fd1bb3662b2c0bf87d78')
 def test_accessible_explicit_subpages(self):
  code=(WEB/'landscape-pages-v20.js').read_text()
  for word in ['.ph20-dots','.ph20-count','aria-live','MutationObserver','touchstart','touchend','countPerSlide','makeOverview','makeSettings']:
   self.assertIn(word,code)
  css=(WEB/'landscape-pages-v20.css').read_text()
  self.assertIn('.ph20-slide[hidden]',css)
  self.assertIn('.ph20-viewport',css)
 def test_version_and_android_assets(self):
  gradle=(ROOT/'android/app/build.gradle').read_text()
  self.assertIn('versionCode 8',gradle)
  self.assertIn('1.9.2-preview',gradle)
  r=subprocess.run(['python3',str(ROOT/'tools/sync_android_assets.py'),'--check'],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_js_syntax(self):
  r=subprocess.run(['node','--check',str(WEB/'landscape-pages-v20.js')],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
