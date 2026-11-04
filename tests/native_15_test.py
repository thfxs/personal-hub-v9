#!/usr/bin/env python3
"""Portable source and integration tests; not Android instrumentation tests."""
import re
import unittest
import json
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT/'web'

class ScriptHTML(HTMLParser):
    def __init__(self):super().__init__();self.scripts=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='script' and d.get('src'):self.scripts.append(d['src'])
        if tag=='link' and d.get('href'):self.links.append(d['href'])

class NativeV15(unittest.TestCase):
    def test_html_scripts_load_in_safe_order_and_exist(self):
        for entry in ('index.html','safety/safety.html','device.html'):
            p=WEB/entry;parser=ScriptHTML();parser.feed(p.read_text())
            for value in parser.scripts+parser.links:
                if not value.startswith(('http:','https:')):
                    self.assertTrue((p.parent/value.split('#')[0].split('?')[0]).is_file(),entry+':'+value)
            self.assertTrue(parser.scripts,entry)
        core=(WEB/'index.html').read_text()
        self.assertLess(core.index('native-file.js'),core.index('app.js'))
        safety=(WEB/'safety/safety.html').read_text()
        self.assertLess(safety.index('native-file.js'),safety.index('safety-ui.js'))

    def test_external_backup_never_reports_picker_open_as_saved(self):
        ui=(WEB/'safety/safety-ui.js').read_text()
        app=(WEB/'app.js').read_text()
        self.assertIn('var how=await download(',ui)
        self.assertIn("how==='native'",ui)
        self.assertIn('.then(function(){toast(',app)
        self.assertIn('isShell()',ui)

    def test_static_no_lan_cleartext_or_webview_data_overscope(self):
        j=(ROOT/'android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java').read_text()
        manifest=(ROOT/'android/app/src/main/AndroidManifest.xml').read_text()
        self.assertNotRegex(j,r'\.addJavascriptInterface\s*\(')
        self.assertIn('mainFrame',j)
        self.assertIn('ORIGIN.equals(origin.toString())',j)
        self.assertIn('MAX_EXPORT_BYTES',j)
        self.assertNotIn('android.permission.WRITE_EXTERNAL_STORAGE',manifest)
        self.assertNotIn('android.permission.READ_EXTERNAL_STORAGE',manifest)
        self.assertIn('usesCleartextTraffic="false"',manifest)
        self.assertIn('isPublicGitHubApi(request)',j)
        self.assertIn('\"api.github.com\".equals(u.getHost())',j)
        self.assertNotIn('cleartextTrafficPermitted',manifest)

    def test_preference_page_and_swipe(self):
        page=(WEB/'device.html').read_text()
        for key in ('immersive','awake','swipe'):
            self.assertIn('id="'+key+'"',page)
        js=(WEB/'swipe-nav.js').read_text()
        self.assertIn("(orientation: landscape)",js)
        self.assertIn('touchcancel',js)
        self.assertIn("#modal-root:not(:empty)",js)

    def test_web_and_android_assets_match(self):
        source={p.relative_to(WEB):p.read_bytes() for p in WEB.rglob('*') if p.is_file() and not p.name.startswith('.')}
        asset=ROOT/'android/app/src/main/assets/web'
        embedded={p.relative_to(asset):p.read_bytes() for p in asset.rglob('*') if p.is_file()}
        self.assertEqual(source,embedded)

    def test_sw_offline_precache_excludes_private_data(self):
        sw=(WEB/'sw.js').read_text()
        self.assertRegex(sw,r'personal-hub-shell-v1[67]')
        for filename in ('./native-file.js','./device.html','./device.js','./swipe-nav.js'):
            self.assertIn(filename,sw)
        self.assertNotIn('personal-hub-backup',sw)

if __name__=='__main__':unittest.main(verbosity=2)
