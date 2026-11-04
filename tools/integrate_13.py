#!/usr/bin/env python3
"""Non-destructive installation of the 1.3 standalone public-monitor page.
Does not change the legacy app, styles, Service Worker, Android package or secrets.
The 1.3 full web/ package already contains an integrated entry and SW cache.
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/'web'
ASSETS=['ops/index.html','ops/ops.js','ops/ops.css','ops/logic.js']

def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()

def install(web_root, apply=False):
    target=Path(web_root).expanduser().resolve()
    if not (target/'index.html').is_file():
        raise ValueError('目标目录没有 index.html')
    conflicts=[p for p in ASSETS if (target/p).exists() and digest(target/p)!=digest(SOURCE/p)]
    if conflicts:
        raise ValueError('冲突：'+', '.join(conflicts)+'。任何旧文件均未修改。')
    print('目标：',target)
    print('增加独立访问路径：',target/'ops/index.html')
    print('保留原主程序、CSS、Web 清单、SW、数据、Android 签名和所有既有入口')
    if not apply:
        print('[DRY RUN] 没有修改文件。')
        return
    for p in ASSETS:
        dest=target/p
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            shutil.copy2(SOURCE/p, dest)
    print('[PASS] 模块安装完成。旧版入口未修改；独立访问 ./ops/index.html。')
    print('若原有 Service Worker 采用固定离线白名单，需人工核对缓存，不自动改 SW。')

def main():
    p=argparse.ArgumentParser(description='1.3 旧工程安全集成工具；默认仅预览')
    p.add_argument('--web-root',required=True)
    p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    try:
        install(args.web_root,args.apply)
        return 0
    except (OSError,ValueError) as exc:
        print('[FAIL]',exc)
        return 2

if __name__=='__main__':
    sys.exit(main())
