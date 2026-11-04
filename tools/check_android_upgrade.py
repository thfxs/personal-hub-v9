#!/usr/bin/env python3
# Conservative static audit for Android upgrade identity. No files modified unless --record-baseline.
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def find_gradle(project):
    files = list(project.glob('**/build.gradle')) + list(project.glob('**/build.gradle.kts'))
    files = [p for p in files if 'build/' not in str(p) and '.gradle/' not in str(p)]
    matches = []
    for p in files:
        txt = p.read_text(encoding='utf-8', errors='replace')
        match_id = re.search(r'(?m)^\s*applicationId\s*(?:=\s*)?["\']([^"\']+)["\']', txt)
        match_version = re.search(r'(?m)^\s*versionCode\s*(?:=\s*)?(\d+)\b', txt)
        if match_id and match_version:
            matches.append((p, match_id.group(1), int(match_version.group(1)), txt))
    if len(matches) != 1:
        raise RuntimeError(f'应当且仅能找到一个明确的 Android 应用模块，当前找到 {len(matches)} 个。请检查 applicationId/versionCode。')
    return matches[0]


def cert(apk):
    exe = shutil.which('apksigner')
    if not exe:
        return None, '未找到 Android SDK apksigner，无法自动比较证书 SHA-256'
    cmd = [exe, 'verify', '--print-certs', str(apk)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=25)
        found = re.search(r'(?im)^Signer #\d+ certificate SHA-256 digest:\s*([0-9a-f:]+)', proc.stdout)
        if not found:
            return None, '无法从 apksigner 输出解析签名证书 SHA-256'
        return found.group(1).lower().replace(':', ''), None
    except Exception as e:
        return None, '证书检查失败：' + str(e)


def main():
    parser = argparse.ArgumentParser(description='Personal Hub 0.9 - Android 升级安全审计（不自动签名或安装）')
    parser.add_argument('--project', required=True, type=Path, help='Android 工程目录')
    parser.add_argument('--baseline', type=Path, help='已安装旧版本的受信任记录 JSON')
    parser.add_argument('--record-baseline', type=Path, help='仅首次从实际已装版本确认后使用')
    parser.add_argument('--installed-apk', type=Path, help='手机已装旧版本对应的 APK')
    parser.add_argument('--candidate-apk', type=Path, help='准备安装的新 APK')
    args = parser.parse_args()
    try:
        gradle, app_id, version, src = find_gradle(args.project.resolve())
    except Exception as exc:
        print('[FAIL]', exc); return 2
    print('[INFO] Gradle 模块:', gradle)
    print('[INFO] applicationId:', app_id)
    print('[INFO] versionCode:', version)
    failed = False
    if re.search(r'(?m)^\s*signingConfig\s*(?:=\s*)?signingConfigs\.(debug|\.getByName\(["\']debug)', src):
        print('[WARN] 检测到 debug 签名配置引用；正式 APK 必须使用长期固定的 release 签名')
    elif 'signingConfig' not in src:
        print('[WARN] 未在模块构建脚本检测到签名配置，请检查是否由共享 Gradle 脚本提供')
    if 'applicationIdSuffix' in src:
        print('[WARN] 存在 applicationIdSuffix；请确认 release 构建没有更改应用标识')
    if args.baseline:
        try: b = json.loads(args.baseline.read_text(encoding='utf-8'))
        except Exception as exc: print('[FAIL] 无法读取基线:', exc); return 2
        if b.get('applicationId') != app_id:
            print('[FAIL] applicationId 与旧版不同，升级会变成另一个应用'); failed = True
        else: print('[PASS] applicationId 未变化')
        old = b.get('versionCode')
        if not isinstance(old, int) or version <= old:
            print('[FAIL] versionCode 必须大于旧版的', old); failed = True
        else: print('[PASS] versionCode 严格递增')
    else:
        print('[WARN] 未提供 --baseline，无法证明应用包名及版本号与已安装版一致')
    old_cert = new_cert = None
    if args.installed_apk and args.candidate_apk:
        old_cert, msg1 = cert(args.installed_apk)
        new_cert, msg2 = cert(args.candidate_apk)
        if msg1: print('[WARN]', msg1)
        if msg2: print('[WARN]', msg2)
        if old_cert and new_cert:
            if old_cert != new_cert:
                print('[FAIL] APK 签名证书不同，无法覆盖升级'); failed = True
            else: print('[PASS] 旧版/新版 APK 签名证书 SHA-256 相同')
    else:
        print('[WARN] 未同时提供旧版及新版 APK，签名证书未验证')
    if args.baseline and isinstance(b.get('signingCertSha256'), str) and new_cert:
        if b['signingCertSha256'].lower().replace(':', '') != new_cert:
            print('[FAIL] 候选 APK 的签名与已记录基线不匹配'); failed = True
    if args.record_baseline:
        if args.record_baseline.exists():
            print('[FAIL] 基线文件已存在，禁止静默覆盖'); return 2
        baseline = {'applicationId': app_id, 'versionCode': version}
        if old_cert: baseline['signingCertSha256'] = old_cert
        args.record_baseline.write_text(json.dumps(baseline, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        print('[INFO] 已记录基线；请对照设备实际上已安装的 APK 信息进行人工确认:', args.record_baseline)
    print('[FAIL] 未达到安全升级条件' if failed else '[INFO] 静态检查结束。警告项目必须人工核实；此结果不能代表真机可覆盖升级')
    return 1 if failed else 0


if __name__ == '__main__': sys.exit(main())
