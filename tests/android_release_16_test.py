#!/usr/bin/env python3
"""APK artifact checker offline unit tests. Not an actual Android build."""
import hashlib
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import verify_android_apk as gate

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.apk=self.path/'example.apk'
        self.web=self.path/'web';self.web.mkdir()
        for name in gate.REQUIRED:
            if name.startswith('assets/web/'):
                p=self.web/name[len('assets/web/'):];p.parent.mkdir(parents=True,exist_ok=True);p.write_text('data for '+name)
        self.make_apk()

    def make_apk(self,omit=(),leak=()):
        with zipfile.ZipFile(self.apk,'w') as z:
            for name in gate.REQUIRED-set(omit):
                if name.startswith('assets/web/'):
                    z.writestr(name,(self.web/name[len('assets/web/'):]).read_bytes())
                else:z.writestr(name,b'fake binary')
            z.writestr('classes.dex',b'dex\n035')
            for name in leak:z.writestr(name,b'private')

    def tool(self,name,text):
        tool=self.path/name
        tool.write_text('#!/bin/sh\nprintf '+"'%s\\n' "+"'"+text.replace("'","'\\''")+"'\n")
        tool.chmod(0o700)

    def test_package_zip_assets_hash(self):
        result=gate.inspect_zip(self.apk,self.web)
        self.assertEqual(result['sha256'],hashlib.sha256(self.apk.read_bytes()).hexdigest())
        self.assertGreater(result['entries'],10)

    def test_missing_component_or_private_key_rejected(self):
        self.make_apk(omit={'assets/web/sync/sync.js'})
        with self.assertRaisesRegex(ValueError,'缺少'): gate.inspect_zip(self.apk,self.web)
        self.make_apk(leak=['res/backup-2026.json'])
        with self.assertRaisesRegex(ValueError,'证书私钥'): gate.inspect_zip(self.apk,self.web)

    def test_asset_mismatch_rejected(self):
        (self.web/'app.js').write_text('different')
        with self.assertRaisesRegex(ValueError,'资源与当前源码不一致'):
            gate.inspect_zip(self.apk,self.web)

    def test_signature_and_package_checked_by_sdk_tools(self):
        self.tool('aapt',"package: name='dev.personalhub.v9preview' versionCode='8' versionName='1.9.2-preview'\\nsdkVersion:'26'\\ntargetSdkVersion:'35'")
        self.tool('apksigner',"Verified using v2 scheme (APK Signature Scheme v2): true\\nSigner #1 certificate SHA-256 digest: " + 'ab'*32)
        result=gate.verify(self.apk,self.web,self.path,expected_cert='ab:'*31+'ab')
        self.assertEqual(result['package'],gate.PKG)
        self.assertEqual(result['version_code'],8)
        with self.assertRaisesRegex(ValueError,'证书不匹配'):
            gate.verify(self.apk,self.web,self.path,expected_cert='cd'*32)

    def test_wrong_package_or_missing_v2_rejected(self):
        self.tool('aapt',"package: name='com.wrong.app' versionCode='8' versionName='1.9.2-preview'\\nsdkVersion:'26'\\ntargetSdkVersion:'35'")
        self.tool('apksigner',"Verified using v2 scheme (APK Signature Scheme v2): false\\nSigner #1 certificate SHA-256 digest: " + 'ab'*32)
        with self.assertRaisesRegex(ValueError,'包名'):
            gate.verify(self.apk,self.web,self.path)
        self.tool('aapt',"package: name='dev.personalhub.v9preview' versionCode='8' versionName='1.9.2-preview'\\nsdkVersion:'26'\\ntargetSdkVersion:'35'")
        with self.assertRaisesRegex(ValueError,'V2'):
            gate.verify(self.apk,self.web,self.path)

if __name__=='__main__':unittest.main(verbosity=2)
