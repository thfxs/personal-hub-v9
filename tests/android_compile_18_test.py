#!/usr/bin/env python3
"""Test that the portable Java compile gate detects, and isn't bypassed by, a bad MainActivity."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]
SRC = R/'android/app/src/main/java/dev/personalhub/v9preview'
GATE = R/'tools/android_source_compile_gate.py'

@unittest.skipUnless(shutil.which('javac'),'JDK is required to compile Java sources')
class AndroidSourceGate(unittest.TestCase):
    def test_main_activity_and_tls_client_compilable(self):
        p = subprocess.run(['python3',str(GATE)],capture_output=True,text=True,timeout=25)
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        self.assertIn('Both real Android Java sources compiled',p.stdout)

    def test_uncompilable_main_activity_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            for name in ('MainActivity.java','PinnedBridgeClient.java'):
                shutil.copy2(SRC/name,d/name)
            source=d/'MainActivity.java'
            content=source.read_text()
            self.assertIn('public final class MainActivity',content)
            source.write_text(content.replace('public final class MainActivity', 'public final class MainActivityBroken'))
            p=subprocess.run(['python3',str(GATE)],capture_output=True,text=True,timeout=25,
                env={**os.environ,'PH_ANDROID_SOURCE_DIR':str(d)})
            self.assertNotEqual(p.returncode,0)
            self.assertIn('error:',p.stdout+p.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
