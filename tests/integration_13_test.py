import functools
import http.server
import pathlib
import re
import tempfile
import threading
import unittest
import urllib.request
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from integrate_13 import install
WEB=ROOT/'web'
class Integration13Tests(unittest.TestCase):
    def test_new_resource_links_resolve(self):
        for file in ('index.html','ops/index.html','bridge-launch.html'):
            base=WEB/file
            for u in re.findall(r'(?:src|href)="(\./[^"#?]+)"',base.read_text()):
                self.assertTrue((base.parent/u).is_file(),u)

    def test_offline_cache_13_contains_monitors(self):
        text=(WEB/'sw.js').read_text()
        self.assertIn('personal-hub-shell-v17',text) # 1.5 bumps cache key, retaining previous resources
        for item in ('./ops/index.html','./ops/ops.css','./ops/logic.js','./ops/ops.js'):
            self.assertIn(item,text)

    def test_original_app_and_styles_remain_byte_identical_to_12(self):
        from compat15 import assert_core_safe
        assert_core_safe(self)

    def test_installer_dry_run_idempotent_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            (path/'index.html').write_text('keep index')
            install(path)
            self.assertEqual(list(path.iterdir()),[path/'index.html'])
            install(path,True)
            install(path,True)
            self.assertEqual((path/'index.html').read_text(),'keep index')
            (path/'ops/ops.js').write_text('OLD FILE')
            with self.assertRaisesRegex(ValueError,'冲突'):
                install(path,True)
            self.assertEqual((path/'ops/ops.js').read_text(),'OLD FILE')

    def test_local_http_resources(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*_):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(WEB)))
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            for uri in ('/','/ops/index.html','/ops/logic.js','/ops/ops.js','/ops/ops.css','/sw.js'):
                with urllib.request.urlopen('http://127.0.0.1:'+str(server.server_address[1])+uri,timeout=5) as response:
                    self.assertEqual(response.status,200)
        finally:
            server.shutdown();server.server_close();t.join(timeout=2)

    def test_no_secret_keys_bundled_into_public_web(self):
        for file in WEB.rglob('*'):
            if file.is_file() and file.suffix in ('.js','.html','.json'):
                self.assertNotIn('sk-',file.read_text(encoding='utf-8'),str(file))

if __name__=='__main__':unittest.main()
