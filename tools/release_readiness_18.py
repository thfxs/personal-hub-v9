#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explicit release readiness status: source gate != built/signed APK.

Source-only checks can pass without Android SDK. Final mode requires a real APK
and Android Build Tools; it never treats a ZIP or mock APK as signed evidence.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def invoke(cmd):
    r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=40)
    return {'ok':r.returncode==0, 'output':(r.stdout+r.stderr)[-900:]}

def main():
    p=argparse.ArgumentParser(description='Personal Hub 1.8 源码/实际 APK 发布就绪门禁')
    p.add_argument('--source-only',action='store_true',help='仅检查源码和 Android Java 编译，不代表 APK 可安装')
    p.add_argument('--apk',type=Path,help='需要验证的实际 Android APK 路径')
    p.add_argument('--build-tools',type=Path,help='实际 Android SDK 的 build-tools/<version> 目录')
    p.add_argument('--json-output',type=Path,help='保存可机器读取的结果')
    opts=p.parse_args()
    checks={}
    for name,script in [
        ('asset_consistency','tools/sync_android_assets.py'),
        ('android_static_15','tools/android_preflight_15.py'),
        ('android_static_16','tools/android_preflight_16.py'),
        ('android_static_17','tools/android_preflight_17.py'),
        ('java_source_compile','tools/android_source_compile_gate.py')]:
        cmd=[sys.executable,str(ROOT/script)]
        if name=='asset_consistency':cmd.append('--check')
        checks[name]=invoke(cmd)
    status='SOURCE_READY' if all(x['ok'] for x in checks.values()) else 'SOURCE_FAILED'
    apk_detail=None
    if not opts.source_only:
        if not opts.apk:
            status='APK_NOT_PROVIDED' if status=='SOURCE_READY' else 'SOURCE_FAILED'
        elif status=='SOURCE_READY':
            cmd=[sys.executable,str(ROOT/'tools/verify_android_apk.py'),str(opts.apk),'--web',str(ROOT/'web')]
            if opts.build_tools:cmd+=['--build-tools',str(opts.build_tools)]
            apk_detail=invoke(cmd)
            status='APK_ARTIFACT_VERIFIED' if apk_detail['ok'] else 'APK_VERIFICATION_FAILED'
    report={'version':'1.9.2-preview','source':str(ROOT),'checks':checks,
            'apk_verification':apk_detail,'status':status,
            'notice':'SOURCE_READY only verifies portable source checks; Android SDK build + APK signature + device verification are separate'}
    if opts.json_output:
        opts.json_output.parent.mkdir(parents=True,exist_ok=True)
        opts.json_output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for name,result in checks.items():print(('[PASS]' if result['ok'] else '[FAIL]'),name)
    print('STATUS:',status)
    if status!='APK_ARTIFACT_VERIFIED':print('[NOT CLAIMED] No verified signed Android APK is produced by this check')
    return 0 if (status=='SOURCE_READY' and opts.source_only) or status=='APK_ARTIFACT_VERIFIED' else 2

if __name__=='__main__':raise SystemExit(main())
