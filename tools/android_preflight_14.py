#!/usr/bin/env python3
"""Read-only Android 1.4 preparation audit; never builds or signs an APK."""
import re
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ANDROID=ROOT/'android'
WEB=ROOT/'web'
ASSETS=ANDROID/'app/src/main/assets/web'

def main():
    errors=[]
    gradle=(ANDROID/'app/build.gradle').read_text(encoding='utf8')
    manifest=(ANDROID/'app/src/main/AndroidManifest.xml').read_text(encoding='utf8')
    java=(ANDROID/'app/src/main/java/dev/personalhub/v9preview/MainActivity.java').read_text(encoding='utf8')
    tests=(('preview package isolated',"applicationId 'dev.personalhub.v9preview'" in gradle),
           ('release build only with external secrets','haveReleaseKeys' in gradle),
           ('LAN cleartext prohibited inside APK','usesCleartextTraffic="false"' in manifest),
           ('system backup disabled','allowBackup="false"' in manifest),
           ('same-origin HTTPS asset loader','WebViewAssetLoader' in java and 'appassets.androidplatform.net' in java),
           ('untrusted external pages open OS browser','Intent.ACTION_VIEW' in java),
           ('WebView JavaScript necessary for app','setJavaScriptEnabled(true)' in java))
    for label,passed in tests:
        print(('[PASS]' if passed else '[FAIL]'),label)
        if not passed:errors.append(label)
    actual=[p.relative_to(WEB) for p in WEB.rglob('*') if p.is_file()]
    missing=[str(p) for p in actual if not (ASSETS/p).is_file() or (ASSETS/p).read_bytes()!=(WEB/p).read_bytes()]
    print('[PASS]' if not missing else '[FAIL]',str(len(actual))+' packaged static assets checked')
    if missing:errors.append('web assets mismatch: '+str(missing[:4]))
    for program in ('java','gradle','adb','apksigner'):
        print('[ENV]',program,shutil.which(program) or 'not installed')
    print('[NOT VERIFIED] no Gradle build, no APK, no signature identity, no V9 device test; SAF implementation not run')
    if errors:print('Failures:',errors);return 1
    print('[PASS] Android source preparation static checks; build/test still required')
    return 0
if __name__=='__main__':sys.exit(main())
