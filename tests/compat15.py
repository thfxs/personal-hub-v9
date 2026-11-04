"""Regression assertion: only one authorized export function changed from v1.4 main app.
Original v1.4 app.js is bundled as an immutable test fixture.
"""
from pathlib import Path
import hashlib
import re

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/'tests/fixtures/web_app_v14.js'
CURRENT=ROOT/'web/app.js'
ORIGINAL_STYLE_SHA256='0877293e76b59c33fcfc0de1c9c5b0c814699bf23238fd1bb3662b2c0bf87d78'
EXPORT_RE=re.compile(r'(function exportBackup\(\)\{).*?(?=\nfunction importBackup\()',re.S)

def assert_core_safe(test):
    source=ORIGINAL.read_text(encoding='utf8')
    revised=CURRENT.read_text(encoding='utf8')
    test.assertEqual(len(EXPORT_RE.findall(source)),1)
    test.assertEqual(len(EXPORT_RE.findall(revised)),1)
    test.assertEqual(EXPORT_RE.sub('EXPORT_ONLY',source),EXPORT_RE.sub('EXPORT_ONLY',revised))
    test.assertIn('window.PersonalHubFiles.saveJson',revised)
    # SHA of expected originally preserved style, set from v1.4 packaged source.
    test.assertEqual(hashlib.sha256((ROOT/'web/styles.css').read_bytes()).hexdigest(),ORIGINAL_STYLE_SHA256)
