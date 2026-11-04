#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create computer-only LAN HTTPS certificate and encryption password.
Never put generated secrets inside the source or repository.
Requires cryptography; intended for one-time local setup.
"""
import argparse
import datetime
import ipaddress
import os
import socket
import stat
from pathlib import Path

DEFAULT = Path.home() / '.personal-hub-bridge' / 'security'


def detect_ips():
    values = {'127.0.0.1'}
    try:
        for ans in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = ipaddress.ip_address(ans[4][0])
            if ip.is_private or ip.is_loopback:
                values.add(str(ip))
    except OSError:
        pass
    return sorted(values)


def generate(folder=DEFAULT, addresses=None, days=365):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    folder = Path(folder).expanduser()
    if folder.is_symlink():
        raise ValueError('安全目录不能是符号链接')
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != 'nt':
        folder.chmod(0o700)
    cert = folder / 'server.crt'
    key = folder / 'server.key'
    passfile = folder / 'vault-passphrase.txt'
    if any(x.is_symlink() for x in (cert,key,passfile)):
        raise ValueError('安全文件不能是符号链接')
    if cert.exists() != key.exists():
        raise ValueError('证书与私钥缺失其一。为避免错配，请检查旧文件，勿自动重建覆盖')
    if not cert.exists():
        key_obj = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Personal Hub local-only bridge')])
        now = datetime.datetime.now(datetime.timezone.utc)
        ips = set(addresses or detect_ips())
        ips.add('127.0.0.1')
        san = [x509.IPAddress(ipaddress.ip_address(p)) for p in sorted(ips)]
        san.append(x509.DNSName('localhost'))
        cert_obj = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key_obj.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-datetime.timedelta(minutes=5))
            .not_valid_after(now+datetime.timedelta(days=days))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False,path_length=None), critical=True)
            .sign(key_obj,hashes.SHA256()))
        pemkey = key_obj.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        pemcert = cert_obj.public_bytes(serialization.Encoding.PEM)
        def create_new(path,body):
            fd = os.open(str(path),os.O_CREAT | os.O_EXCL | os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as f:
                f.write(body)
        create_new(key,pemkey)
        create_new(cert,pemcert)
    else:
        cert_obj = x509.load_pem_x509_certificate(cert.read_bytes())
    if not passfile.exists():
        import secrets
        secret = secrets.token_urlsafe(40).encode('ascii') + b'\n'
        fd = os.open(str(passfile),os.O_CREAT | os.O_EXCL | os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as out:
            out.write(secret)
    elif os.name != 'nt' and stat.S_IMODE(passfile.stat().st_mode) & 0o077:
        raise ValueError('密码文件权限过宽：请先 chmod 600，再启动服务')
    from cryptography.hazmat.primitives.serialization import Encoding
    pub_fp = cert_obj.fingerprint(hashes.SHA256()).hex().upper()
    return {'cert':str(cert),'key':str(key),'passfile':str(passfile),
            'certificate_sha256':':'.join(pub_fp[i:i+2] for i in range(0,len(pub_fp),2)),
            'sans':str(cert_obj.extensions.get_extension_for_class(x509.SubjectAlternativeName).value),
            'expires_utc':str(cert_obj.not_valid_after_utc)}


def main():
    parser=argparse.ArgumentParser(description='Personal Hub 电脑端 HTTPS 初次设置（不会覆盖已有证书或密码）')
    parser.add_argument('--directory',default=str(DEFAULT))
    parser.add_argument('--ip',action='append',default=[],help='额外电脑局域网 IP，可多次输入')
    args=parser.parse_args()
    try:
        result=generate(args.directory,sorted(set(detect_ips()+args.ip)))
    except (ValueError,OSError,ImportError) as e:
        parser.error(str(e))
    print('电脑桥配置已准备；不要将下列证书私钥或密码文件上传到 GitHub。')
    for k,v in result.items():print(k+':',v)
    print('注意：生成证书不等于手机信任。手机浏览器需要预先信任此设备证书，否则不得忽略证书警告而发送私人数据。')

if __name__=='__main__':main()
