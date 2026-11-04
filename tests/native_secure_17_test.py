#!/usr/bin/env python3
"""Real TLS and JDK smoke tests for the isolated Android-native transport class.
Does NOT claim an Android APK build or V9 compatibility.
"""
import datetime
import hashlib
import http.server
import ipaddress
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'android/app/src/main/java/dev/personalhub/v9preview/PinnedBridgeClient.java'

HARNESS='''package dev.personalhub.v9preview;
public class BridgeProbe {
 public static void main(String[] x) throws Exception {
  PinnedBridgeClient c = new PinnedBridgeClient("127.0.0.1",Integer.parseInt(x[0]),x[1],true);
  String mode=x[2];
  if ("good".equals(mode)) {
   System.out.println("status="+c.request("GET","/api/status",null).status);
   System.out.println("pair="+c.request("POST","/api/pair","{\\"pin\\":\\"12345678\\"}").status);
   System.out.println("sync="+c.request("GET","/api/sync",null).status);
  } else if ("admin".equals(mode)) {
   c.request("POST","/api/admin/arm","{}");
  } else {System.out.println("status="+c.request("GET","/api/status",null).status);}
 }
}'''

class TestTLSServer(http.server.ThreadingHTTPServer):
    daemon_threads=True
    block_on_close=False
    def get_request(self):
        raw,addr=super().get_request()
        raw.settimeout(6)
        return self.tls_context.wrap_socket(raw,server_side=True,do_handshake_on_connect=False),addr

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*args): pass
    def output(self,status,obj,cookie=None):
        import json
        body=json.dumps(obj).encode()
        self.send_response(status);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path=='/api/status':
            self.output(200,{'paired':'phb_session=abcDE_12345678901234567890' in self.headers.get('Cookie','')});return
        if self.path=='/api/sync':
            self.output(200 if 'phb_session=abcDE_12345678901234567890' in self.headers.get('Cookie','') else 401,{'ok':True});return
        self.output(404,{'error':'not found'})
    def do_POST(self):
        if self.path=='/api/pair' and self.headers.get('X-Bridge-Request')=='1':
            n=int(self.headers.get('Content-Length','0'));self.rfile.read(n)
            self.output(200,{'ok':True},'phb_session=abcDE_12345678901234567890; HttpOnly; SameSite=Strict; Path=/; Secure');return
        self.output(404,{'error':'not found'})

@unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'JDK unavailable')
class NativePinned17(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes,serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
        except ImportError:
            raise unittest.SkipTest('cryptography required for TLS test fixture')
        cls.tmp=tempfile.TemporaryDirectory()
        cls.work=Path(cls.tmp.name)
        folder=cls.work/'dev/personalhub/v9preview';folder.mkdir(parents=True)
        shutil.copyfile(SRC,folder/'PinnedBridgeClient.java')
        (folder/'BridgeProbe.java').write_text(HARNESS)
        subprocess.run(['javac','-encoding','UTF-8','-d',str(cls.work),str(folder/'PinnedBridgeClient.java'),str(folder/'BridgeProbe.java')],check=True,capture_output=True)
        cls.certs=[]
        for label,ip,expired in [('right','127.0.0.1',False),('wrong-san','192.168.10.99',False),('expired','127.0.0.1',True)]:
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'test-native-transport')])
            now=datetime.datetime.now(datetime.timezone.utc)
            cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now-datetime.timedelta(days=10))
                .not_valid_after(now-datetime.timedelta(days=1 if expired else -7))
                .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]),critical=False)
                .sign(key,hashes.SHA256()))
            fp=cert.fingerprint(hashes.SHA256()).hex()
            keyfile=cls.work/(label+'.key');certfile=cls.work/(label+'.crt')
            keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.TraditionalOpenSSL,serialization.NoEncryption()))
            certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            cls.certs.append((certfile,keyfile,fp))

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def run_probe(self,which,fp=None,mode='single'):
        cert,key,correct=self.certs[which]
        server=TestTLSServer(('127.0.0.1',0),Handler)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(str(cert),str(key))
        server.tls_context=tls
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            return subprocess.run(['java','-cp',str(self.work),'dev.personalhub.v9preview.BridgeProbe',str(server.server_port),fp or correct,mode],capture_output=True,text=True,timeout=12)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)

    def test_pinned_tls_pair_cookie_and_follow_up(self):
        p=self.run_probe(0,mode='good')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('status=200',p.stdout)
        self.assertIn('pair=200',p.stdout)
        self.assertIn('sync=200',p.stdout)

    def test_wrong_fingerprint_rejected(self):
        p=self.run_probe(0,'00'*32)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('SSLHandshakeException',p.stderr)

    def test_same_fingerprint_wrong_ip_san_rejected(self):
        p=self.run_probe(1)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('SSLHandshakeException',p.stderr)

    def test_expired_certificate_rejected(self):
        p=self.run_probe(2)
        self.assertNotEqual(p.returncode,0)
        self.assertIn('SSLHandshakeException',p.stderr)

    def test_admin_endpoint_never_requested(self):
        p=self.run_probe(0,mode='admin')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('请求路径不在白名单中',p.stderr)

    def test_pure_java_source_compiles(self):
        self.assertTrue((self.work/'dev/personalhub/v9preview/PinnedBridgeClient.class').is_file())

if __name__=='__main__':unittest.main(verbosity=2)
