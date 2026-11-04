#!/usr/bin/env python3
"""Add the isolated safety module to an existing Personal Hub web root.
Defaults to dry run; does not touch existing JS/CSS/database/Gradle.
"""
import argparse
import difflib
import hashlib
import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'safety'
INSERT = '<script src="./safety/guard-core.js"></script>\n<script src="./safety/guard-auto.js"></script>\n'
ASSETS = ['guard-core.js', 'guard-auto.js', 'safety.html', 'safety-ui.js', 'safety.css']


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def integrate(root, apply):
    index = root / 'index.html'
    if not index.exists():
        raise ValueError('未找到 index.html；请指定现有 0.8 Web 资源目录，而不是 Android 工程根目录')
    old = index.read_text(encoding='utf-8')
    if old.count('</body>') != 1:
        raise ValueError('index.html 中 </body> 不唯一，拒绝自动修改')
    updated = old
    if './safety/guard-core.js' not in old and './safety/guard-auto.js' not in old:
        updated = old.replace('</body>', INSERT + '</body>')
    elif not ('./safety/guard-core.js' in old and './safety/guard-auto.js' in old):
        raise ValueError('发现只集成了一半的脚本，请人工核对后重试')
    dest = root / 'safety'
    for name in ASSETS:
        fp = dest / name
        if fp.exists() and sha256(fp) != sha256(SRC / name):
            raise ValueError(f'发现现有文件与当前补丁不同，禁止覆盖：{fp}')
    print('[INFO] 现有 index.html:', index)
    print('[INFO] 原始字节数:', len(old.encode('utf-8')))
    print('[INFO] 所需集成文件:', ', '.join(ASSETS))
    print('[INFO] 主程序 JS/CSS/Gradle 不会改动')
    if old != updated:
        print(''.join(difflib.unified_diff(old.splitlines(True), updated.splitlines(True), fromfile='original/index.html', tofile='integrated/index.html')))
    else:
        print('[PASS] index.html 的脚本入口已存在，保持不变')
    if not apply:
        print('[DRY-RUN] 尚未修改任何文件。可添加 --apply 实际写入。')
        return
    backup_dir = root / '.personal_hub_09_rollback'
    backup_dir.mkdir(exist_ok=True)
    backup_index = backup_dir / 'index.html.before_09'
    if not backup_index.exists():
        shutil.copy2(index, backup_index)
    dest.mkdir(exist_ok=True)
    for name in ASSETS:
        target = dest / name
        if not target.exists():
            shutil.copy2(SRC / name, target)
    if old != updated:
        temp = root / '.index.html.09.tmp'
        temp.write_text(updated, encoding='utf-8')
        temp.replace(index)
    print('[PASS] 已以非破坏方式添加 0.9 数据保护模块')
    print('[INFO] 修改前 index.html 备份:', backup_index)
    print('[WARN] 若使用 Service Worker 离线缓存白名单，还需人工按原结构更新缓存版本与资源路径')


def main():
    parser = argparse.ArgumentParser(description='在原有 0.8 Web 前端上集成独立 0.9 数据保护功能')
    parser.add_argument('--web-root', type=Path, required=True, help='已有 0.8 index.html 所在目录')
    parser.add_argument('--apply', action='store_true', help='明确确认后写入；默认仅预览变更')
    args = parser.parse_args()
    try:
        integrate(args.web_root.resolve(), args.apply)
    except Exception as exc:
        print('[FAIL]', exc)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
