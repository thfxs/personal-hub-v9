#!/usr/bin/env python3
"""Read-only static audit for an existing Personal Hub web project."""
import argparse
import json
import re
import sys
from pathlib import Path


def main(argv=None):
    p = argparse.ArgumentParser(description='只读检查已有 0.8 / 0.9 Personal Hub 工程兼容性')
    p.add_argument('--web-root', type=Path, required=True)
    p.add_argument('--out', type=Path)
    a = p.parse_args(argv)
    root = a.web_root.expanduser().resolve()
    if not (root / 'index.html').is_file():
        print('index.html 不存在：', root, file=sys.stderr)
        return 2
    files = [x for x in root.rglob('*') if x.is_file() and x.suffix.lower() in ('.js', '.html')
             and '.git' not in x.parts and 'node_modules' not in x.parts]
    entries = []
    texts = []
    for file in files[:400]:
        if file.stat().st_size > 2_000_000:
            continue
        try:
            source = file.read_text(encoding='utf-8')
        except (UnicodeError, OSError):
            continue
        entries.append(file.relative_to(root).as_posix())
        texts.append(source)
    corpus = '\n'.join(texts)
    db_names = sorted(set(re.findall(r"(?:DB_NAME\s*=\s*|indexedDB\.open\s*\(\s*)['\"]([a-zA-Z0-9_\-]+)['\"]", corpus)))
    output = {
        'web_root': str(root),
        'index_exists': True,
        'js_html_file_count': len(entries),
        'javascript_html_files': entries,
        'found_indexeddb_name_literals': db_names,
        'v09_safety_installed': all((root / 'safety' / x).exists() for x in ('guard-core.js','guard-auto.js','safety.html')),
        'v10_diag_installed': (root / 'diag' / 'v9-check.html').is_file(),
        'service_worker_present': (root / 'sw.js').is_file(),
        'caution': '静态文本检索可能遗漏动态数据库名/原生 WebView 内的数据；未运行 APK，也未读取任何个人记录。',
    }
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    print(rendered)
    if a.out:
        a.out.write_text(rendered + '\n', encoding='utf-8')
    return 0

if __name__ == '__main__':
    sys.exit(main())
