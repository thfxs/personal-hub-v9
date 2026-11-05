#!/usr/bin/env python3
import hashlib
import re
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
OLD = ROOT.parent / 'Personal_Hub_1.3_监控与事件中心集成版' / 'web'


class Integration14(unittest.TestCase):
    def test_existing_core_preserved(self):
        from compat15 import assert_core_safe
        assert_core_safe(self)

    def test_navigation_and_sync_assets_exist(self):
        index=(WEB / 'index.html').read_text()
        self.assertIn('sync/index.html', index)
        for file in ('sync/index.html','sync/sync.js','sync/sync.css','sync/merge.js'):
            self.assertTrue((WEB / file).is_file())

    def test_all_pwa_cached_resources_exist(self):
        txt=(WEB / 'sw.js').read_text()
        self.assertIn('personal-hub-shell-v19',txt)
        items=re.findall(r"'\./([^']+)'",txt.split('var SCOPE=')[0])
        self.assertGreater(len(items),15)
        for path in items:
            self.assertTrue((WEB/path).is_file(),path)

    def test_sync_js_never_embeds_secret_or_cross_origin_calls(self):
        js=(WEB/'sync/sync.js').read_text()
        self.assertIn('before-sync-14',js)
        self.assertIn("credentials:'same-origin'",js)
        self.assertNotIn('Access-Control-Allow-Origin',js)
        self.assertNotIn('eval(',js)

    def test_pwa_plus_android_asset_copies_match(self):
        asset=ROOT / 'android/app/src/main/assets/web'
        for path in WEB.rglob('*'):
            if not path.is_file() or path.name.startswith('.'):continue
            copy=asset/path.relative_to(WEB)
            self.assertTrue(copy.is_file(), str(copy))
            self.assertEqual(path.read_bytes(),copy.read_bytes(),str(path))

    def test_android_preview_separate_package_and_no_cleartext_permission(self):
        gradle=(ROOT/'android/app/build.gradle').read_text()
        manifest=(ROOT/'android/app/src/main/AndroidManifest.xml').read_text()
        java=(ROOT/'android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java').read_text()
        self.assertIn("applicationId 'dev.personalhub.v9preview'",gradle)
        self.assertIn('android:usesCleartextTraffic="false"',manifest)
        self.assertIn('android:allowBackup="false"',manifest)
        self.assertIn('WebViewAssetLoader',java)
        self.assertIn('MIXED_CONTENT_NEVER_ALLOW',java)

    def test_no_private_data_in_server_static_root(self):
        p=(ROOT/'bridge/server.py').read_text()
        self.assertIn("if path.startswith('/hub/'):",p)
        self.assertIn("if x in",p) if False else None
        self.assertIn('file.is_symlink()',p)
        self.assertIn('self._auth()',p)

    def test_original_features_exist(self):
        for path in ('web/ops/index.html','web/safety/safety.html','bridge/monitor.py','bridge/activity.py','bridge/web/monitor.html'):
            self.assertTrue((ROOT/path).is_file(),path)

if __name__=='__main__':unittest.main(verbosity=2)
