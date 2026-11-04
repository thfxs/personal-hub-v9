
#!/usr/bin/env python3
"""Mirror packaged static web into Android assets, with explicit --check and no private JSON."""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
DEST = ROOT / 'android/app/src/main/assets/web'
ALLOW = {'.html','.js','.css','.png','.svg','.webmanifest','.txt'}

def eligible():
    result = {}
    for p in WEB.rglob('*'):
        if p.is_symlink():
            raise ValueError('WEB contains a symbolic link: ' + str(p))
        if not p.is_file():
            continue
        rel = p.relative_to(WEB)
        if p.name.startswith('.'):
            continue
        if p.suffix not in ALLOW:
            raise ValueError('Unexpected web resource suffix: ' + str(rel))
        if p.stat().st_size > 2_000_000:
            raise ValueError('Web resource too large: ' + str(rel))
        result[rel] = p
    return result

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='verify embedded assets; never modify files')
    args = parser.parse_args(argv)
    src = eligible()
    missing = [str(k) for k,v in src.items() if not (DEST/k).is_file() or (DEST/k).read_bytes()!=v.read_bytes()]
    stale = [str(p.relative_to(DEST)) for p in DEST.rglob('*') if p.is_file() and p.relative_to(DEST) not in src]
    if args.check:
        print(('PASS' if not missing and not stale else 'FAIL'),len(src),'assets; changed/missing:',missing[:6],'; unexpected:',stale[:6])
        return 0 if not missing and not stale else 1
    for p in list(DEST.rglob('*')):
        if p.is_symlink():
            raise ValueError('Android asset directory contains symlink: ' + str(p))
    for p in DEST.rglob('*'):
        if p.is_file() and p.relative_to(DEST) not in src:
            p.unlink()
    for rel,from_file in src.items():
        target = DEST/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.is_file() or target.read_bytes()!=from_file.read_bytes():
            shutil.copyfile(from_file,target)
    print('PASS synchronized',len(src),'public web assets into Android source')
    return 0

if __name__=='__main__':sys.exit(main())
