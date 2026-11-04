#!/usr/bin/env python3
"""1.7 static native transport source gates; not actual APK compilation."""
from pathlib import Path
import subprocess
import re
import sys
R=Path(__file__).resolve().parents[1]
j=(R/'android/app/src/main/java/dev/personalhub/v9preview/MainActivity.java').read_text()
pin=(R/'android/app/src/main/java/dev/personalhub/v9preview/PinnedBridgeClient.java').read_text()
sync=(R/'web/sync/sync.js').read_text()
transport=(R/'web/sync/native-transport.js').read_text()
ci=(R/'.github/workflows/android-preview.yml').read_text()
html=(R/'web/sync/index.html').read_text()
main=(R/'web/index.html').read_text()
manifest=(R/'android/app/src/main/AndroidManifest.xml').read_text()
gradle=(R/'android/app/build.gradle').read_text()
checks={
 'isolated APK package retained':"applicationId 'dev.personalhub.v9preview'" in gradle,
 '1.7+ APK version bump': any(x in gradle for x in ("versionCode 4", "versionCode 5")) and any(x in gradle for x in ("versionName '1.7.0-preview'", "versionName '1.8.0-preview'")),
 'cleartext disabled': 'usesCleartextTraffic="false"' in manifest,
 'native network worker not UI': 'Executors.newSingleThreadExecutor()' in j and 'networkExecutor.execute' in j,
 'origin and main frame restricted': 'mainFrame' in j and 'ORIGIN.equals(origin.toString())' in j,
 'native bridge limited to two local pages': 'ROOT+"sync/index.html"' in j and 'ROOT+"remote.html"' in j and 'isBridgePage' in j,
 'no javascript interface': not re.search(r'\.\s*addJavascriptInterface\s*\(',j),
 'native non-TOFU certificate binding': 'confirmed' in j and 'validateFingerprint' in pin and 'MessageDigest.isEqual' in pin,
 'strict IP SAN + expiry checks': 'getSubjectAlternativeNames()' in pin and 'checkValidity()' in pin,
 'no HTTP fallback': 'HttpsURLConnection' in pin and not re.search(r'"http://"',pin),
 'native session cookie memory only': 'private String cookie = "";' in pin and 'phb_session=' in pin,
 'native fixed host + redirect refusal': 'setInstanceFollowRedirects(false)' in pin and 'private static void allow' in pin,
 'native sync CAS remains': "'/api/sync'" in sync and 'M.merge(' in sync and 'writeLocal(' in sync,
 'native sync uses APK local DB': 'isNative()' in sync and 'readLocal()' in sync,
 'fingerprint isolation in base key': "'_native_'" in sync and 'nativeConfig.fingerprint' in sync,
 'fingerprint confirmation visible': 'id="nativeVerified"' in html,
 'native remote commands page': (R/'web/remote.html').is_file() and (R/'web/remote.js').is_file() and './remote.html' in main,
 'offline new assets': 'personal-hub-shell-v17' in (R/'web/sw.js').read_text(),
 'CI native gate': 'android_preflight_17.py' in ci,
}
for k,v in checks.items():print(('[PASS]' if v else '[FAIL]'),k)
ret=subprocess.call([sys.executable,str(R/'tools/sync_android_assets.py'),'--check'])
print('[NOT CHECKED] Actual Android Java SDK compile, APK, V9 touchscreen, native WebView bridge availability')
sys.exit(0 if all(checks.values()) and ret==0 else 1)
