#!/usr/bin/env python3
"""Static (not runtime/compiler) preflight for native document and safe navigation."""
from pathlib import Path
import subprocess
import re
import sys
R=Path(__file__).resolve().parents[1]
J=(R/'android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java').read_text()
G=(R/'android/app/build.gradle').read_text()
M=(R/'android/app/src/main/AndroidManifest.xml').read_text()
I=(R/'web/index.html').read_text()
S=(R/'web/safety/safety-ui.js').read_text()
N=(R/'web/native-file.js').read_text()
W=(R/'.github/workflows/android-preview.yml').read_text()
checks={
 'test application id isolated':"applicationId 'dev.personalhub.v9preview'" in G,
 'non-cleartext WebView': 'usesCleartextTraffic="false"' in M and 'MIXED_CONTENT_NEVER_ALLOW' in J,
 'asset-loader HTTPS source': 'WebViewAssetLoader' in J and 'appassets.androidplatform.net' in J,
 'SAF create document': 'Intent.ACTION_CREATE_DOCUMENT' in J and 'getContentResolver().openOutputStream' in J,
 'SAF import': 'Intent.ACTION_OPEN_DOCUMENT' in J and 'parseResult' in J,
 'origin-scoped main-frame bridge': 'isMainFrame' not in J and 'mainFrame' in J and 'Collections.singleton(ORIGIN)' in J,
 'no unscoped javascript interface': not re.search(r'\.\s*addJavascriptInterface\s*\(',J),
 'byte size bounded': 'MAX_EXPORT_BYTES' in J,
 'no faked save on picker launch': 'RESULT_OK' in J and 'reply(pending.reply, pending.requestId, true' in J,
 'failure if unsupported inside native shell': "isShell()" in S and 'PersonalHubV9Shell' in N,
 'manual CI build': 'workflow_dispatch' in W and 'assembleDebug' in W and 'assembleRelease' in W,
 'original web interface still present': 'app.js' in I and 'styles.css' in I,
 'APK auto backup disabled': 'allowBackup="false"' in M,
}
for n,ok in checks.items():print(('[PASS]' if ok else '[FAIL]'),n)
code=subprocess.call([sys.executable,str(R/'tools/sync_android_assets.py'),'--check'])
print('[NOT VERIFIED] Real Java compilation/Android SDK, actual APK, V9 device, signing certificate, chooser behavior')
sys.exit(0 if all(checks.values()) and code==0 else 1)
