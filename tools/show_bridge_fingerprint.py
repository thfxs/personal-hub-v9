#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only computer-side certificate fingerprint and IP SAN display.
No private key read, no network calls, no certificate auto-creation.
"""
from pathlib import Path
import argparse
import sys

DEFAULT=Path.home()/'.personal-hub-bridge'/'security'/'server.crt'

def describe(path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from datetime import datetime,timezone
    path=Path(path).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError('电脑证书不存在，先运行安全初始化脚本；拒绝读取链接文件')
    cert=x509.load_pem_x509_certificate(path.read_bytes())
    sha=cert.fingerprint(hashes.SHA256()).hex().upper()
    try:
        san=cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        ips=[str(v) for v in san.get_values_for_type(x509.IPAddress)]
    except x509.ExtensionNotFound:
        ips=[]
    valid_after=cert.not_valid_after_utc
    return {'fingerprint':':'.join(sha[i:i+2] for i in range(0,len(sha),2)),
            'ip_sans':ips,'expires':valid_after.isoformat(),
            'expired':datetime.now(timezone.utc)>valid_after}

def main():
    parser=argparse.ArgumentParser(description='在电脑本机显示 HTTPS 证书指纹，以供 Android 手工绑定')
    parser.add_argument('--cert',default=str(DEFAULT))
    args=parser.parse_args()
    try:r=describe(args.cert)
    except (OSError,ValueError,ImportError) as exc:
        print('ERROR:',exc,file=sys.stderr);return 1
    print('服务器证书 SHA-256 指纹（不是密码，可以在手机中手工核对）：')
    print(r['fingerprint'])
    print('证书包含的电脑 IP:',', '.join(r['ip_sans']) or '(无)')
    print('UTC 到期日期:',r['expires'])
    if r['expired']:
        print('ERROR: 证书已过期，不能用于同步。请人工备份并更新证书，再重新配对。');return 2
    print('重要：先在电脑本机确认 IP 在上述列表中，再在 V9 逐字核对证书指纹。证书更新后不会自动接受新指纹。')
    return 0
if __name__=='__main__':sys.exit(main())
