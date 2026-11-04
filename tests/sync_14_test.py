#!/usr/bin/env python3
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))
import server as bridge
from sync_store import SyncStore, SyncError, SyncConflict


def sample():
    return {'version': 1, 'createdAt': '2026-11-04T10:00:00Z', 'updatedAt':'2026-11-04T10:00:00Z',
            'settings': {'motion': True}, 'projects': [], 'tasks': [], 'business': [],
            'jobs': [], 'ideas': [], 'health': [], 'links': []}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'vault' / 'main.json'
        self.store = SyncStore(self.path)

    def test_create_and_reload(self):
        a = sample()
        self.assertEqual(self.store.snapshot()['revision'], 0)
        self.assertEqual(self.store.update(0, a, 'request-00001')['revision'], 1)
        self.assertEqual(SyncStore(self.path).snapshot()['state'], a)

    def test_compare_and_swap_blocks_stale_edits(self):
        self.store.update(0, sample(), 'request-00002')
        with self.assertRaises(SyncConflict):
            self.store.update(0, sample(), 'request-00003')

    def test_duplicate_request_id_is_idempotent(self):
        a = sample()
        self.store.update(0, a, 'request-00004')
        self.assertTrue(self.store.update(0, a, 'request-00004')['replayed'])
        a['tasks'] = [{'id': 'new'}]
        with self.assertRaises(SyncConflict):
            self.store.update(1, a, 'request-00004')

    def test_keeps_prior_server_revisions(self):
        a = sample(); self.store.update(0,a,'request-00005')
        a['tasks']=[{'id':'a'}]
        self.store.update(1,a,'request-00006')
        old = list((self.path.parent / 'sync-history').glob('revision-*.json'))
        self.assertEqual(len(old),1)
        self.assertEqual(json.loads(old[0].read_text())['revision'],1)
        self.assertEqual(os.stat(self.path).st_mode & 0o077,0)

    def test_corrupted_storage_fails_closed(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('not json')
        with self.assertRaises(SyncError):
            self.store.update(0,sample(),'request-00007')
        self.assertEqual(self.path.read_text(),'not json')

    def test_symlink_storage_fails_closed(self):
        external = Path(self.tmp.name) / 'elsewhere.json'; external.write_text('safe')
        self.path.parent.mkdir(parents=True)
        self.path.symlink_to(external)
        with self.assertRaises(SyncError):
            self.store.update(0,sample(),'request-00008')
        self.assertEqual(external.read_text(),'safe')

    def test_bad_or_huge_record_rejected(self):
        a=sample();a['tasks']=[{'id':'a'},{'id':'a'}]
        with self.assertRaises(SyncError): self.store.update(0,a,'request-00009')
        a=sample();a['health']=[{'id':'a','note':'x'*1_000_000}]
        with self.assertRaises(SyncError): self.store.update(0,a,'request-00010')

    def test_rejects_dangerous_top_level_key(self):
        data = sample()
        data['__proto__'] = {'polluted': True}
        with self.assertRaises(SyncError):
            self.store.update(0, data, 'danger-request14')

    def test_competing_threads_one_wins(self):
        errors=[]; successes=[]
        def send(i):
            try: successes.append(self.store.update(0,sample(),'race-request-'+str(i)))
            except SyncConflict as e: errors.append(e)
        threads=[threading.Thread(target=send,args=(i,)) for i in range(12)]
        [t.start() for t in threads];[t.join() for t in threads]
        self.assertEqual(self.store.snapshot()['revision'],1)
        self.assertEqual(len(successes),1)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        state = bridge.BridgeState(injector=lambda text: {'status': 'fake'})
        cls.http = bridge.BridgeServer(('127.0.0.1', 0),state)
        cls.http.sync_store = SyncStore(Path(cls.tmp.name) / 'sync.json')
        cls.thread = threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
        cls.port = cls.http.server_address[1]
        cls.pin = state.pin

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.tmp.cleanup()

    def fetch(self,method,path,data=None,cookie=None,origin=True):
        conn = http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        h={'Host':'127.0.0.1:'+str(self.port)}
        if cookie: h['Cookie']=cookie
        if data is not None:
            h['Content-Type']='application/json';h['X-Bridge-Request']='1'
            h['Origin'] = ('http://127.0.0.1:'+str(self.port) if origin else 'https://evil.example')
        conn.request(method,path,body=json.dumps(data).encode() if data is not None else None,headers=h)
        r=conn.getresponse();body=r.read();hdr=dict(r.getheaders());code=r.status;conn.close();return code,hdr,body

    def test_all_endpoints_secured_and_static_whitelisted(self):
        self.assertEqual(self.fetch('GET','/api/sync')[0],401)
        self.assertEqual(self.fetch('GET','/hub/')[0],200)
        self.assertEqual(self.fetch('GET','/hub/sync/index.html')[0],200)
        self.assertEqual(self.fetch('GET','/hub/../README.md')[0],404)
        self.assertEqual(self.fetch('GET','/hub/.gitignore')[0],404)

    def test_pair_then_sync_and_origin_reject(self):
        code, headers, body = self.fetch('POST','/api/pair',{'pin':self.pin})
        self.assertEqual(code,200)
        cookie=headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.fetch('GET','/api/sync',cookie=cookie)[0],200)
        self.assertEqual(self.fetch('POST','/api/sync',{'revision':0,'state':sample(),'request_id':'post-request1'},cookie,origin=False)[0],403)
        code,_,body=self.fetch('POST','/api/sync',{'revision':0,'state':sample(),'request_id':'post-request1'},cookie)
        self.assertEqual(code,200,body)
        self.assertEqual(json.loads(body)['revision'],1)
        self.assertEqual(self.fetch('POST','/api/sync',{'revision':0,'state':sample(),'request_id':'post-request2'},cookie)[0],409)
        self.assertEqual(json.loads(self.fetch('GET','/api/sync',cookie=cookie)[2])['state'],sample())


if __name__=='__main__':
    unittest.main(verbosity=2)
