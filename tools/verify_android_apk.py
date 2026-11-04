#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed APK artifact verification for CI and user-provided build outputs.
No certificate, secret or APK content is uploaded anywhere.
"""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PKG='dev.personalhub.v9preview'
EXPECTED_VERSION_CODE=5
EXPECTED_MIN=26
REQUIRED={'AndroidManifest.xml','resources.arsc','assets/web/index.html','assets/web/app.js',
          'assets/web/styles.css','assets/web/safety/guard-core.js','assets/web/sync/merge.js',
          'assets/web/sync/sync.js','assets/web/native-file.js','assets/web/swipe-nav.js',
          'assets/web/device.js','assets/web/ops/ops.js',
          'assets/web/sync/native-transport.js','assets/web/remote.html','assets/web/remote.js'}


def inspect_zip(path, web=None):
    path=Path(path)
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise ValueError('文件不存在或不是 APK ZIP 文件')
    with zipfile.ZipFile(path) as z:
        names=set(z.namelist())
        absent=REQUIRED-names
        if absent:raise ValueError('APK 缺少内置模块：'+','.join(sorted(absent)))
        if not any(re.fullmatch(r'classes\d*\.dex',name) for name in names):
            raise ValueError('APK 缺少 Android DEX 可执行文件')
        leaked=[name for name in names if name.lower().endswith(('.jks','.keystore','.pem','.p12','.pfx'))
                or 'backup-' in name.lower() or name.startswith('assets/web/.git/')]
        if leaked:raise ValueError('APK 疑似包含证书私钥/备份：'+', '.join(leaked[:3]))
        if web:
            web=Path(web)
            for name in REQUIRED:
                if not name.startswith('assets/web/'):
                    continue
                relative=name[len('assets/web/'):]
                local=web/relative
                if not local.is_file() or local.read_bytes()!=z.read(name):
                    raise ValueError('APK 资源与当前源码不一致：'+relative)
    return {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,
            'entries':len(names)}


def find_tool(name,build_tools=None):
    if build_tools:
        candidate=Path(build_tools)/(name+('.exe' if sys.platform=='win32' else ''))
        if candidate.is_file():return str(candidate)
    result=shutil.which(name)
    if not result:raise ValueError('缺少 Android 构建工具 '+name+'；不能宣称 APK 已验收')
    return result


def run(cmd):
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=35)
    if proc.returncode:
        raise ValueError('工具校验失败：'+cmd[0]+' ('+str(proc.returncode)+') '+(proc.stderr or proc.stdout)[-450:])
    return proc.stdout


def verify(apk,web=None,build_tools=None,expected_cert=None):
    result=inspect_zip(apk,web)
    output=run([find_tool('aapt',build_tools),'dump','badging',str(apk)])
    pkg=re.search(r"package:\s+name='([^']+)'\s+versionCode='(\d+)'",output)
    mn=re.search(r"sdkVersion:'(\d+)'",output)
    target=re.search(r"targetSdkVersion:'(\d+)'",output)
    if not pkg or not mn or not target:
        raise ValueError('aapt 输出不完整，无法核对包名和系统版本')
    if pkg.group(1)!=PKG or int(pkg.group(2))!=EXPECTED_VERSION_CODE or int(mn.group(1))!=EXPECTED_MIN or int(target.group(1))!=35:
        raise ValueError('包名、versionCode 或 SDK 配置不符合独立测试版约束')
    signing=run([find_tool('apksigner',build_tools),'verify','--verbose','--print-certs',str(apk)])
    if 'Verified using v2 scheme (APK Signature Scheme v2): true' not in signing:
        raise ValueError('没有验证到 APK V2 签名，拒绝作为可安装结果')
    match=re.search(r'Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]+)',signing)
    if not match:raise ValueError('无法读取 APK 证书 SHA-256 指纹')
    signature=match.group(1).lower()
    if expected_cert and signature!=re.sub(r'[^0-9a-fA-F]','',expected_cert).lower():
        raise ValueError('APK 签名证书不匹配，不能尝试覆盖安装')
    result.update({'package':pkg.group(1),'version_code':int(pkg.group(2)),
                   'min_sdk':int(mn.group(1)),'target_sdk':int(target.group(1)),
                   'certificate_sha256':signature})
    return result


def main():
    p=argparse.ArgumentParser(description='检查实际 APK 资源、独立包名、安装版本和 V2 签名')
    p.add_argument('apk')
    p.add_argument('--web',help='校验内置 web 资源和工作区 Web 源码一致')
    p.add_argument('--build-tools',help='Android SDK build-tools/35.0.0 目录')
    p.add_argument('--expected-cert',help='已知旧 APK 签名 SHA-256（用于安全升级核对）')
    p.add_argument('--sha-output',help='将 APK SHA256 写入独立 .sha256 文件')
    args=p.parse_args()
    try:
        result=verify(args.apk,args.web,args.build_tools,args.expected_cert)
        for key,value in result.items():print('[PASS]',key,':',value)
        if args.sha_output:
            Path(args.sha_output).write_text(result['sha256']+'  '+Path(args.apk).name+'\n')
        return 0
    except (ValueError,OSError,subprocess.TimeoutExpired,zipfile.BadZipFile) as e:
        print('[FAIL] APK 验收失败：',e,file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
