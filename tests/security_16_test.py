#!/usr/bin/env python3
"""Real TLS handshake + encrypted disk integration checks (no external accounts)."""
import copy
import http.client
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'bridge'))
sys.path.insert(0, str(ROOT/'tools'))
import server
from sync_store import SyncStore, SyncError, SyncConflict
from setup_secure_bridge import generate


def sample():
    return {'version':1,'settings':{'motion':False},'projects':[], 'tasks':[{'id':'task-1','note':'仅限本机同步的测试资料'}],
            'business':[], 'jobs':[], 'ideas':[], 'health':[], 'links':[]}

class CryptVaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'secure.json'
        self.passphrase=b'correct-horse-fairly-long-password-16'
        self.vault=SyncStore(self.path, password=self.passphrase)

    def test_aes_gcm_roundtrip_no_plaintext_leak(self):
        state=sample()
        self.assertEqual(self.vault.update(0,state,'enc-00000001')['revision'],1)
        disk=self.path.read_bytes()
        self.assertNotIn('仅限本机'.encode('utf8'),disk)
        self.assertNotIn(b'task-1',disk)
        self.assertEqual(json.loads(disk)['format'],2)
        self.assertEqual(SyncStore(self.path,password=self.passphrase).snapshot()['state'],state)
        self.assertEqual(os.stat(self.path).st_mode & 0o077,0)

    def test_encrypted_history_and_cas(self):
        state=sample()
        self.vault.update(0,state,'enc-00000002')
        updated=copy.deepcopy(state);updated['tasks'][0]['note']='已更改的秘密字段'
        self.vault.update(1,updated,'enc-00000003')
        history=list((self.path.parent/'sync-history').glob('revision-*.json'))
        self.assertEqual(len(history),1)
        self.assertNotIn('仅限本机'.encode('utf8'),history[0].read_bytes())
        self.assertEqual(json.loads(history[0].read_bytes())['format'],2)
        with self.assertRaises(SyncConflict): self.vault.update(1,state,'enc-00000004')
        self.assertTrue(self.vault.update(2,updated,'enc-00000003')['replayed'])

    def test_wrong_password_and_tamper_fail_closed(self):
        self.vault.update(0,sample(),'enc-00000005')
        before=self.path.read_bytes()
        with self.assertRaises(SyncError): SyncStore(self.path,password=b'wrong-wrong-very-long-password').snapshot()
        self.assertEqual(self.path.read_bytes(),before)
        envelope=json.loads(before)
        envelope['ciphertext']=envelope['ciphertext'][:-4]+'AAAA'
        self.path.write_text(json.dumps(envelope))
        with self.assertRaises(SyncError): self.vault.update(1,sample(),'enc-00000006')
        self.assertEqual(json.loads(self.path.read_bytes()),envelope)

    def test_plaintext_to_encrypted_never_silent_overwrite(self):
        SyncStore(self.path).update(0,sample(),'plain-00001')
        old=self.path.read_bytes()
        with self.assertRaisesRegex(SyncError,'明文'): self.vault.update(1,sample(),'enc-00000007')
        self.assertEqual(self.path.read_bytes(),old)
        with self.assertRaises(SyncError): self.vault.snapshot()

    def test_encrypted_cannot_open_without_password(self):
        self.vault.update(0,sample(),'enc-00000008')
        with self.assertRaisesRegex(SyncError,'加密'): SyncStore(self.path).snapshot()

    def test_two_independent_processes_cannot_both_write_revision_one(self):
        # Tests actual OS file locking, not just Python threading.RLock.
        import concurrent.futures
        program = """import sys
from sync_store import SyncStore
s=SyncStore(sys.argv[1],password=b'correct-horse-fairly-long-password-16')
try:
    s.update(0,{'version':1,'settings':{},'projects':[],'tasks':[],'business':[],'jobs':[],'ideas':[],'health':[],'links':[]},sys.argv[2])
    print('OK')
except Exception as e:
    print(type(e).__name__)
"""
        def call(n):
            p=subprocess.run([sys.executable,'-c',program,str(self.path),'mp-request-%08d'%n],
                env=dict(os.environ,PYTHONPATH=str(ROOT/'bridge')),capture_output=True,text=True,timeout=8)
            return p.returncode,p.stdout.strip()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            results=list(ex.map(call,range(5)))
        self.assertEqual([x[1] for x in results].count('OK'),1,results)
        self.assertEqual(self.vault.snapshot()['revision'],1)

    def test_secret_file_symlink_rejected(self):
        secret=Path(self.tmp.name)/'secret';secret.write_text('0123456789abcdefghijk')
        secret.chmod(0o600)
        self.assertEqual(len(server.read_secret_file(secret)),21)
        link=Path(self.tmp.name)/'link';link.symlink_to(secret)
        with self.assertRaises(SyncError): server.read_secret_file(link)
        if os.name!='nt':
            secret.chmod(0o644)
            with self.assertRaises(SyncError): server.read_secret_file(secret)

class CertificateSetupTests(unittest.TestCase):
    def test_repeated_setup_keeps_original_secret_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            first=generate(root,['127.0.0.1'])
            before=(root/'vault-passphrase.txt').read_bytes()
            second=generate(root,['127.0.0.1'])
            self.assertEqual(first['certificate_sha256'],second['certificate_sha256'])
            self.assertEqual(before,(root/'vault-passphrase.txt').read_bytes())
            self.assertNotIn(before,Path(first['cert']).read_bytes())

    def test_incomplete_key_pair_refuses_silent_regeneration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);generate(root,['127.0.0.1'])
            (root/'server.key').unlink()
            with self.assertRaisesRegex(ValueError,'缺失其一'):
                generate(root,['127.0.0.1'])

class TLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        root=Path(cls.tmp.name)
        info=generate(root/'security',['127.0.0.1'])
        cls.cert=info['cert']
        cls.vault=SyncStore(root/'secure.json', password=b'not-a-real-user-secret-password-16')
        cls.state=server.BridgeState(injector=lambda text:{'window':'test','process':'fake'})
        cls.srv=server.BridgeServer(('127.0.0.1',0),cls.state,tls=True,sync_store=cls.vault)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(info['cert'],info['key'])
        cls.srv.socket=context.wrap_socket(cls.srv.socket,server_side=True)
        cls.port=cls.srv.server_address[1]
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True)
        cls.thread.start()
        cls.client_context=ssl.create_default_context(cafile=cls.cert)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.srv.server_close();cls.thread.join(timeout=4);cls.tmp.cleanup()

    def request(self,method,path,payload=None,cookie=None,origin=None):
        conn=http.client.HTTPSConnection('127.0.0.1',self.port,context=self.client_context,timeout=5)
        h={'Host':'127.0.0.1:'+str(self.port)}
        if cookie:h['Cookie']=cookie
        if payload is not None:
            h.update({'Content-Type':'application/json','X-Bridge-Request':'1','Origin':origin or 'https://127.0.0.1:'+str(self.port)})
        conn.request(method,path,body=json.dumps(payload).encode() if payload is not None else None,headers=h)
        response=conn.getresponse();data=response.read();status=response.status;headers=dict(response.getheaders())
        conn.close()
        return status,headers,data

    def test_real_verified_tls_and_secure_cookie(self):
        code,headers,_=self.request('POST','/api/pair',{'pin':self.state.pin})
        self.assertEqual(code,200)
        self.assertIn('Secure',headers.get('Set-Cookie',''))
        cookie=headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('GET','/api/sync',cookie=cookie)[0],200)
        code,_,body=self.request('POST','/api/sync',{'revision':0,'state':sample(),'request_id':'tls-00000001'},cookie)
        self.assertEqual(code,200,body)
        self.assertEqual(self.vault.snapshot()['revision'],1)
        self.assertEqual(self.request('POST','/api/sync',{'revision':0,'state':sample(),'request_id':'tls-00000001'},cookie)[0],200)

    def test_untrusted_certificate_fails_tls_validation(self):
        conn=http.client.HTTPSConnection('127.0.0.1',self.port,timeout=4)
        with self.assertRaises(ssl.SSLError):
            conn.request('GET','/api/status')
        conn.close()

    def test_https_cross_origin_rejected(self):
        code,_,_=self.request('POST','/api/pair',{'pin':self.state.pin},origin='http://127.0.0.1:'+str(self.port))
        self.assertEqual(code,403)
        code,_,_=self.request('POST','/api/pair',{'pin':self.state.pin},origin='https://evil.invalid')
        self.assertEqual(code,403)

    def test_transport_fail_closed_for_remote(self):
        handler=server.Handler.__new__(server.Handler)
        handler.client_address=('192.168.1.33',1234)
        class MockServer:
            tls_enabled=False
            vault_encrypted=False
            allow_insecure_lan=False
        handler.server=MockServer()
        self.assertFalse(handler._remote_transport_ok())
        self.assertFalse(handler._sync_transport_ok())
        handler.server.allow_insecure_lan=True
        self.assertTrue(handler._remote_transport_ok())
        self.assertFalse(handler._sync_transport_ok())
        handler.server.tls_enabled=True
        self.assertFalse(handler._sync_transport_ok())
        handler.server.vault_encrypted=True
        self.assertTrue(handler._sync_transport_ok())

if __name__=='__main__':unittest.main(verbosity=2)
