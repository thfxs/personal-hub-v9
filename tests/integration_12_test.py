#!/usr/bin/env python3
from pathlib import Path
import unittest,sys,tempfile,shutil,re,hashlib,http.server,threading,urllib.request,functools
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from integrate_12 import integrate
WEB=ROOT/'web'
class Integration12Tests(unittest.TestCase):
 def test_every_local_reference_resolves(self):
  index=(WEB/'index.html').read_text()
  for url in re.findall(r'(?:href|src)="(\./[^"]+)"',index):
   self.assertTrue((WEB/url[2:]).is_file(),url)
 def test_manifest_and_icons(self):
  import json
  manifest=json.loads((WEB/'manifest.webmanifest').read_text())
  for icon in manifest['icons']:
   self.assertTrue((WEB/icon['src'][2:]).is_file())
  for size in (192,512):
   self.assertTrue((WEB/'assets'/f'icon-{size}.png').read_bytes().startswith(b'\x89PNG'))
 def test_static_sw_offline_assets(self):
  text=(WEB/'sw.js').read_text()
  paths=re.findall(r"'\./([^']+)'",text.split('var SCOPE')[0]);self.assertGreater(len(paths),12)
  for p in paths:self.assertTrue((WEB/p).is_file(),p)
 def test_existing_base_js_css_unchanged(self):
  from compat15 import assert_core_safe
  assert_core_safe(self)
 def test_install_dry_run_and_idempotent(self):
  with tempfile.TemporaryDirectory() as d:
   dest=Path(d);(dest/'index.html').write_text('<html><body><script src="./app.js"></script></body></html>')
   (dest/'app.js').write_text('NO-CHANGE')
   integrate(dest,False)
   self.assertEqual(len(list(dest.rglob('*'))),2)
   integrate(dest,True)
   self.assertEqual((dest/'app.js').read_text(),'NO-CHANGE')
   self.assertIn('guard-auto.js',(dest/'index.html').read_text())
   integrate(dest,True)
   self.assertTrue((dest/'.personal_hub_12_before'/'index.html').exists())
 def test_conflict_does_not_partially_install(self):
  with tempfile.TemporaryDirectory() as d:
   dest=Path(d);(dest/'index.html').write_text('<body></body>');(dest/'bridge-launch.js').write_text('modified')
   with self.assertRaises(ValueError):integrate(dest,True)
   self.assertEqual((dest/'index.html').read_text(),'<body></body>')
   self.assertFalse((dest/'safety').exists())
 def test_http_static_shell(self):
  class Quiet(http.server.SimpleHTTPRequestHandler):
   def log_message(self,*args):pass
  srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(WEB)))
  t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
  try:
   for uri in ('/','/index.html','/bridge-launch.html','/safety/safety.html','/diag/v9-check.html','/sw.js','/assets/icon-192.png'):
    with urllib.request.urlopen('http://127.0.0.1:%d%s'%(srv.server_address[1],uri),timeout=5) as response:
     self.assertEqual(response.status,200,uri)
  finally:srv.shutdown();srv.server_close();t.join(2)
if __name__=='__main__':unittest.main()
