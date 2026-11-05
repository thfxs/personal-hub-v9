#!/usr/bin/env python3
"""Personal Hub 1.9 visual and touch-screen structural regression gates.
Screenshots and WebView hardware remain separate runtime acceptance tasks.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'web'
RES=ROOT/'android/app/src/main/res'

class Display19(unittest.TestCase):
 def test_legacy_hud_style_remains_byte_for_byte_unchanged(self):
  import hashlib
  self.assertEqual(hashlib.sha256((WEB/'styles.css').read_bytes()).hexdigest(),'0877293e76b59c33fcfc0de1c9c5b0c814699bf23238fd1bb3662b2c0bf87d78')
 def test_two_row_mobile_header_and_centered_vector_icons(self):
  html=(WEB/'index.html').read_text()
  css=(WEB/'layout-v19.css').read_text()
  self.assertIn('grid-template-areas:',css)
  self.assertIn("'title clock' 'actions actions'",css)
  self.assertIn('white-space:nowrap',css)
  self.assertEqual(html.count('class="icon-button"'),7)
  self.assertEqual(len(re.findall(r'aria-hidden="true"',html)),7)
  self.assertIn('justify-content:center',css)
 def test_old_webview_scrolling_and_viewport_fallback(self):
  css=(WEB/'layout-v19.css').read_text()
  js=(WEB/'viewport-v19.js').read_text()
  for required in ['min-height:0','overflow-y:auto','-webkit-overflow-scrolling:touch','touch-action:pan-y']:
   self.assertIn(required,css)
  self.assertIn('--ph-window-height',css)
  self.assertIn('window.innerHeight',js)
  self.assertIn('orientationchange',js)
 def test_non_obscuring_backup_alert(self):
  html=(WEB/'index.html').read_text()
  js=(WEB/'safety/guard-auto.js').read_text()
  self.assertIn('id="system-alerts"',html)
  self.assertIn("getElementById('system-alerts')",js)
  self.assertNotIn('position:fixed;right:14px;bottom:15px',js)
 def test_android_launcher_icon_resources_configured(self):
  manifest=(ROOT/'android/app/src/main/AndroidManifest.xml').read_text()
  self.assertIn('android:icon="@mipmap/ic_launcher"',manifest)
  self.assertIn('android:roundIcon="@mipmap/ic_launcher_round"',manifest)
  for rel in ['drawable/ic_launcher_foreground.xml','drawable/ic_launcher_background.xml','mipmap-anydpi-v26/ic_launcher.xml','mipmap-anydpi-v26/ic_launcher_round.xml']:
   self.assertTrue((RES/rel).is_file(),rel)
 def test_android_assets_copied_exactly(self):
  from subprocess import run
  from sys import executable
  result=run([executable,str(ROOT/'tools/sync_android_assets.py'),'--check'],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_version_upgrade_is_explicit(self):
  g=(ROOT/'android/app/build.gradle').read_text()
  self.assertIn('versionCode 6',g)
  self.assertIn("versionName '1.9.0-preview'",g)
  self.assertIn('EXPECTED_VERSION_CODE=6',(ROOT/'tools/verify_android_apk.py').read_text())

if __name__=='__main__': unittest.main(verbosity=2)
