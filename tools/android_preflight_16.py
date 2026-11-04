#!/usr/bin/env python3
"""Additional pre-build guards; only static source validation, never claims APK built."""
import re
import sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
files={name:(P/name).read_text(encoding='utf8') for name in [
    'android/app/build.gradle','android/app/src/main/AndroidManifest.xml',
    'android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java',
    '.github/workflows/android-preview.yml','bridge/server.py','bridge/sync_store.py',
    'web/sync/sync.js','web/bridge-launch.js']}
gradle=files['android/app/build.gradle'];ci=files['.github/workflows/android-preview.yml']
checks={
    'isolated appId': "applicationId 'dev.personalhub.v9preview'" in gradle,
    'min SDK for V9': 'minSdk 26' in gradle,
    'target SDK 35': 'targetSdk 35' in gradle,
    'preview version code incremental': ('versionCode 3' in gradle or 'versionCode 4' in gradle or 'versionCode 5' in gradle),
    'android compilation platform 36': 'compileSdk 36' in gradle and "platforms;android-36" in ci,
    'Android SDK tool verification': 'tools/verify_android_apk.py' in ci and '--sha-output' in ci,
    'CI requires build and certificate verification': 'assembleDebug' in ci and 'assembleRelease' in ci and 'apksigner' in (P/'tools/verify_android_apk.py').read_text(),
    'CI artifacts are temporary': 'retention-days: 7' in ci,
    'release secrets never hardcoded': 'PH_KEYSTORE_B64' in ci and not (P/'android/personal-release.keystore').exists(),
    'no cleartext permission in APK': 'usesCleartextTraffic="false"' in files['android/app/src/main/AndroidManifest.xml'],
    'Native Android LAN HTTP still forbidden': 'MIXED_CONTENT_NEVER_ALLOW' in files['android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java'],
    'native source variant': ('PersonalHubV9Shell/1.6' in files['android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java'] or 'PersonalHubV9Shell/1.7' in files['android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java'] or 'PersonalHubV9Shell/1.8' in files['android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java']),
    'bridge non-TLS mobile denied': '_remote_transport_ok' in files['bridge/server.py'] and 'self.server.tls_enabled' in files['bridge/server.py'],
    'remote sync both TLS and vault': 'self.server.tls_enabled and self.server.vault_encrypted' in files['bridge/server.py'],
    'encrypted computer vault': "'AES-256-GCM'" in files['bridge/sync_store.py'] and 'hashlib.scrypt' in files['bridge/sync_store.py'],
    'HTTPS page navigation default': "return (host==='127.0.0.1'?'http://':'https://')" in files['web/bridge-launch.js'],
    'no private keys in public web directory': not list((P/'web').rglob('*.key')) and not list((P/'web').rglob('*.pem')),
}
for label,passed in checks.items():print(('[PASS]' if passed else '[FAIL]'),label)
print('[NOT TESTED] Android compile, APK signature, V9 WebView, phone certificate trust, real accounts')
sys.exit(0 if all(checks.values()) else 1)
