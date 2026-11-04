#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight local AI/task status reporter, no daemon, no third-party packages.

This tool reports status only for processes launched through `run` or explicit
manual `mark`. It cannot infer completion of existing AI browser conversations.
"""
import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

STATES = ('started', 'done', 'failed', 'attention', 'info')
MAX_TASK = 90
MAX_DETAIL = 200
MAX_BYTES = 524288
KEEP_BYTES = 196608


def default_path():
    return Path.home() / '.personal-hub-bridge' / 'activities.jsonl'


def validate(title, state, detail=''):
    if not isinstance(title, str) or not (1 <= len(title.strip()) <= MAX_TASK):
        raise ValueError('任务名称必须为 1～90 字')
    if state not in STATES:
        raise ValueError('不支持的任务状态')
    if not isinstance(detail, str) or len(detail) > MAX_DETAIL:
        raise ValueError('说明不能超过 200 字')
    for value in (title, detail):
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError('名称和说明必须为单行文本')
    return title.strip(), state, detail


def append_event(title, state, detail='', path=None):
    title, state, detail = validate(title, state, detail)
    path = Path(path) if path else default_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError('拒绝向符号链接事件文件写入')
    event = {'id': secrets.token_hex(8), 'time': int(time.time()), 'task': title,
             'state': state, 'detail': detail}
    encoded = (json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, 0o600)
    try:
        if hasattr(os, 'fchmod'):
            os.fchmod(fd, 0o600)
        n = os.write(fd, encoded)
        if n != len(encoded):
            raise OSError('事件文件写入不完整')
    finally:
        os.close(fd)
    # Small bounded event log; trim opportunistically only after it grows large.
    if path.stat().st_size > MAX_BYTES:
        trim_events(path)
    return event


def trim_events(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('拒绝处理符号链接事件文件')
    with path.open('rb') as f:
        f.seek(max(0, path.stat().st_size - KEEP_BYTES))
        raw = f.read()
    if len(raw) == KEEP_BYTES:
        raw = raw.split(b'\n', 1)[-1]
    temp = path.with_name(path.name + '.' + secrets.token_hex(4) + '.tmp')
    try:
        with temp.open('xb') as f:
            f.write(raw)
        if hasattr(os, 'chmod'):
            os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main(argv=None):
    p = argparse.ArgumentParser(description='Personal Hub 1.1 本地任务状态上报（无需守护进程）')
    sub = p.add_subparsers(dest='mode', required=True)
    mark = sub.add_parser('mark', help='主动写入开始、完成、失败或需要处理状态')
    mark.add_argument('--task', required=True)
    mark.add_argument('--state', required=True, choices=STATES)
    mark.add_argument('--detail', default='')
    mark.add_argument('--events-file', type=Path, default=None, help=argparse.SUPPRESS)
    run = sub.add_parser('run', help='运行一条明确指定的本地命令，并依据退出码报告结果')
    run.add_argument('--task', required=True)
    run.add_argument('--events-file', type=Path, default=None, help=argparse.SUPPRESS)
    run.add_argument('command', nargs=argparse.REMAINDER, help='使用 -- 分隔后续运行命令')
    opts = p.parse_args(argv)
    try:
        if opts.mode == 'mark':
            event = append_event(opts.task, opts.state, opts.detail, opts.events_file)
            print('[PH 1.1] 已记录:', event['task'], event['state'])
            return 0
        command = list(opts.command)
        if command and command[0] == '--':
            command.pop(0)
        if not command:
            p.error('run 模式需要在 -- 后提供可执行程序和参数')
        append_event(opts.task, 'started', path=opts.events_file)
        try:
            completed = subprocess.run(command, check=False)
            rc = completed.returncode
        except OSError as exc:
            append_event(opts.task, 'failed', '启动失败：' + str(exc)[:150], opts.events_file)
            print('[PH 1.1] 启动失败:', exc, file=sys.stderr)
            return 127
        append_event(opts.task, 'done' if rc == 0 else 'failed',
                     '退出码 {}'.format(rc), opts.events_file)
        return rc
    except (ValueError, OSError) as exc:
        print('[PH 1.1] 失败:', exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
