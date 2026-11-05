#!/usr/bin/env python3
"""Single command to run all portable automated tests (no live keyboard injection)."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ('bridge_test.py', 'reliability_11_test.py', 'ui11_static_test.py',
         'integrate10_test.py', 'integration_test.py', 'android_upgrade_test.py',
         'integration_12_test.py', 'monitor_13_test.py', 'integration_13_test.py', 'sync_14_test.py', 'integration_14_test.py', 'native_15_test.py', 'security_16_test.py', 'android_release_16_test.py', 'native_secure_17_test.py', 'android_compile_18_test.py', 'display_19_test.py', 'display_191_test.py', 'display_192_test.py')


def main():
    errors = []
    for filename in TESTS:
        print('\n== RUN:', filename, '==', flush=True)
        code = subprocess.call([sys.executable, str(ROOT / 'tests' / filename)], cwd=str(ROOT))
        if code:
            errors.append(filename)
    if shutil.which('node'):
        print('\n== RUN: portable JS tests ==', flush=True)
        code = subprocess.call(['node', '--test', str(ROOT / 'tests' / 'core.test.js'),
                                str(ROOT / 'tests' / 'launcher_12.test.js'),
                                str(ROOT / 'tests' / 'ops_13.test.js'),
                                str(ROOT / 'tests' / 'sync_14.test.js'),
                                str(ROOT / 'tests' / 'native_15.test.js'),
                                str(ROOT / 'tests' / 'native_transport_17.test.js')], cwd=str(ROOT))
        if code:
            errors.append('portable JS tests')
    else:
        errors.append('Node.js runtime required to run JavaScript tests')
        print('[FAIL] 缺少 Node.js，无法将本轮结果标记为全部通过')
    if errors:
        print('\n[FAIL] 存在失败的测试组:', ', '.join(errors))
        return 1
    print('\n[PASS] 已执行的全部自动化测试组通过（不代表 V9 真机 / Chromium / 真实键盘测试）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
