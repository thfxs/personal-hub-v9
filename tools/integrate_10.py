#!/usr/bin/env python3
"""Non-destructive 0.9 safety + 1.0 V9 diagnostic integration into a real web root.

Does NOT replace 0.8 source code, database, native project, or service worker.
Default is dry run. The LAN bridge is a separate desktop program.
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

from integrate_09 import integrate as install_safety

ROOT = Path(__file__).resolve().parents[1]
DIAG_FILES = ('v9-check.html', 'v9-check.js')


def hashfile(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def inspect(root):
    index = root / 'index.html'
    if not index.is_file():
        raise ValueError('目录中没有 index.html，请传入真正的 0.8 Web 根目录')
    for name in DIAG_FILES:
        source = ROOT / 'diag' / name
        dest = root / 'diag' / name
        if dest.exists() and hashfile(dest) != hashfile(source):
            raise ValueError('发现不同的现有诊断文件，拒绝覆盖：' + str(dest))
    return index


def main(argv=None):
    ap = argparse.ArgumentParser(description='0.9 数据保护 + 1.0 V9 诊断安全增量集成；默认只预览')
    ap.add_argument('--web-root', required=True, type=Path)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args(argv)
    try:
        webroot = args.web_root.expanduser().resolve()
        inspect(webroot)
        print('Web 根目录：', webroot)
        print('将新增：diag/v9-check.html、diag/v9-check.js（若不存在）')
        print('将调用：0.9 原版安全模块非破坏式集成脚本')
        print('电脑桥接器将保持独立，不会被复制进面向公网的 GitHub Pages。')
        print('不会改动原有 app.js、styles.css、数据库、SW、APK 包名与签名配置。')
        install_safety(webroot, args.apply)
        if args.apply:
            dest = webroot / 'diag'
            dest.mkdir(exist_ok=True)
            for name in DIAG_FILES:
                src = ROOT / 'diag' / name
                target = dest / name
                if not target.exists():
                    shutil.copy2(src, target)
            print('[PASS] 诊断页面已安装在', dest / 'v9-check.html')
        else:
            print('[DRY-RUN] 当前文件未修改。可显式传入 --apply。')
        print('[NOTE] 诊断页地址：<你的App原网址>/diag/v9-check.html')
        print('[NOTE] SW 离线资源清单未更改，需单独根据真实 0.8 SW 更新。')
        return 0
    except Exception as exc:
        print('[FAIL]', exc)
        return 2


if __name__ == '__main__':
    sys.exit(main())
