#!/usr/bin/env python3
"""1.9.2 immersive landscape: static + portable logic assertions (not V9 device acceptance)."""
from pathlib import Path
import subprocess
import unittest
import hashlib
ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'web'

class Immersive192(unittest.TestCase):
 def test_original_core_and_hud_preserved(self):
  from sys import path
  path.insert(0,str(ROOT/'tests'))
  from compat15 import assert_core_safe
  assert_core_safe(self)
  self.assertEqual(hashlib.sha256((WEB/'styles.css').read_bytes()).hexdigest(),'0877293e76b59c33fcfc0de1c9c5b0c814699bf23238fd1bb3662b2c0bf87d78')
 def test_landscape_hides_chrome_without_affecting_portrait(self):
  css=(WEB/'immersive-v192.css').read_text()
  self.assertIn('@media (orientation:landscape)',css)
  for value in ['.shell>.sidebar','.workspace>.topbar','.workspace>.footer','.workspace>.system-alerts']:
   self.assertIn(value,css)
  self.assertIn('display:none!important',css)
  self.assertIn('width:100%',css)
 def test_swipe_only_page_indicator(self):
  js=(WEB/'landscape-pages-v20.js').read_text()
  self.assertIn('ph20-dots',js)
  self.assertNotIn('ph20-prev',js)
  self.assertNotIn('ph20-next',js)
  self.assertIn('ev.stopImmediatePropagation()',js)
  self.assertIn('setPage(nextIndex)',js)
  self.assertIn("!main.classList.contains('ph20-active')",(WEB/'swipe-nav.js').read_text())
  self.assertIn('main.addEventListener(\'touchend\'',js)
 def test_progress_not_faked(self):
  script="""const r=require('./web/progress-ring-v192.js');
   const val=[null,'进度：待录入','进度：0%','进度：75.5%','进度：100%','进度：123%'].map(r.progressFromText);
   if(JSON.stringify(val)!==JSON.stringify([null,null,0,75.5,100,null]))process.exit(2);
   console.log('PASS');"""
  run=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(run.returncode,0,run.stdout+run.stderr)
  self.assertIn('完成率待录入',(WEB/'progress-ring-v192.js').read_text())
 def test_web_and_android_assets_match(self):
  result=subprocess.run(['python3',str(ROOT/'tools/sync_android_assets.py'),'--check'],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_version_and_precache(self):
  self.assertIn("'1.9.2-preview'",(ROOT/'android/app/build.gradle').read_text())
  self.assertIn('versionCode 8',(ROOT/'android/app/build.gradle').read_text())
  self.assertIn('personal-hub-shell-v192',(WEB/'sw.js').read_text())
  for f in ['immersive-v192.css','progress-ring-v192.js']:
   self.assertIn(f,(WEB/'index.html').read_text())
   self.assertIn(f,(WEB/'sw.js').read_text())

if __name__=='__main__':unittest.main(verbosity=2)
