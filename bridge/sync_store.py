#!/usr/bin/env python3
# coding: utf-8
"""Personal Hub 1.4 LAN sync vault: explicit CAS writes, no cloud, no arbitrary path API."""
import copy
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from contextlib import contextmanager
from pathlib import Path

FIELDS = ('projects', 'tasks', 'business', 'jobs', 'ideas', 'health', 'links')
MAX_DATA_BYTES = 1_000_000
DEFAULT_FILE = Path.home() / '.personal-hub-bridge' / 'sync-main.json'


class SyncError(ValueError):
    pass


class SyncConflict(SyncError):
    pass


def validate_main(data):
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
        raise SyncError('只支持 Personal Hub 版本 1 数据')
    if not isinstance(data.get('settings'), dict):
        raise SyncError('设置字段不合法')
    if any(key in data for key in ('__proto__', 'constructor', 'prototype')):
        raise SyncError('业务数据存在危险顶层字段')
    for field in FIELDS:
        items = data.get(field)
        if not isinstance(items, list) or len(items) > 20000:
            raise SyncError(field + ' 记录数量/格式异常')
        seen = set()
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str):
                raise SyncError(field + ' 存在无效记录')
            key = item['id']
            if not (1 <= len(key) <= 160) or key in seen:
                raise SyncError(field + ' 存在重复或无效记录 ID')
            seen.add(key)
    try:
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf8')
    except (TypeError, ValueError, RecursionError) as e:
        raise SyncError('记录不能安全序列化：' + str(e)[:80])
    if len(raw) > MAX_DATA_BYTES:
        raise SyncError('业务数据超过 1MB 上限，本轮拒绝同步；请先使用独立备份')
    return raw


def digest(data):
    return hashlib.sha256(validate_main(data)).hexdigest()


class SyncStore:
    def __init__(self, path=None, password=None):
        self.path = Path(path or DEFAULT_FILE).expanduser()
        if isinstance(password, str):
            password = password.encode('utf-8')
        if password is not None and (not isinstance(password, bytes) or len(password) < 16):
            raise SyncError('电脑保险库密码至少为 16 个 UTF-8 字节')
        if password is not None:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
            except ImportError as exc:
                raise SyncError('缺少 cryptography，加密保险库无法安全启动') from exc
        self.password = password
        self.encrypted = password is not None
        self.lock = threading.RLock()

    def _encode(self, value):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf8')
        if not self.encrypted:
            return raw
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise SyncError('加密保险库需要安装 cryptography 依赖') from exc
        salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
        key = hashlib.scrypt(self.password, salt=salt, n=16384, r=8, p=1, dklen=32)
        ciphertext = AESGCM(key).encrypt(nonce, raw, b'PersonalHubSyncVault/v16')
        b64 = lambda data: base64.b64encode(data).decode('ascii')
        return json.dumps({'kind':'personal-hub-sync-vault','format':2,
            'cipher':'AES-256-GCM','kdf':'scrypt-16384-8-1',
            'salt':b64(salt),'nonce':b64(nonce),'ciphertext':b64(ciphertext)},
            separators=(',', ':')).encode('ascii')

    def _decode(self, raw):
        try:
            obj = json.loads(raw.decode('utf8'))
        except (ValueError, UnicodeError, RecursionError):
            raise SyncError('保险库文件损坏或不是合法 JSON，拒绝覆盖')
        if not isinstance(obj, dict):
            raise SyncError('保险库文件不是 JSON 对象')
        if obj.get('format') == 1:
            if self.encrypted:
                raise SyncError('发现早期明文保险库：拒绝静默转换或覆盖，请先手动安全迁移')
            return obj
        if obj.get('format') != 2 or obj.get('kind') != 'personal-hub-sync-vault':
            raise SyncError('无法识别的保险库文件格式')
        if not self.encrypted:
            raise SyncError('这是加密保险库，请配置原有密码文件；不能降级为明文')
        if obj.get('cipher') != 'AES-256-GCM' or obj.get('kdf') != 'scrypt-16384-8-1':
            raise SyncError('未知加密算法，拒绝读取')
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            salt = base64.b64decode(obj['salt'], validate=True)
            nonce = base64.b64decode(obj['nonce'], validate=True)
            ct = base64.b64decode(obj['ciphertext'], validate=True)
            if len(salt) != 16 or len(nonce) != 12 or len(ct) > MAX_DATA_BYTES + 8192:
                raise ValueError('加密字段异常')
            key = hashlib.scrypt(self.password, salt=salt, n=16384, r=8, p=1, dklen=32)
            plaintext = AESGCM(key).decrypt(nonce, ct, b'PersonalHubSyncVault/v16')
            return json.loads(plaintext.decode('utf8'))
        except Exception:
            raise SyncError('保险库无法解密或数据被篡改；请检查密码，原文件不会被覆盖')


    @contextmanager
    def _process_lock(self):
        # Protect CAS revisions even when two bridge processes accidentally use one vault.
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lockpath = self.path.with_name(self.path.name + '.lock')
        if lockpath.is_symlink():
            raise SyncError('进程锁文件不能是符号链接')
        fd = os.open(str(lockpath), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        deadline = time.monotonic() + 5.0
        acquired = False
        try:
            while time.monotonic() < deadline:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        if os.fstat(fd).st_size == 0:
                            os.write(fd, b'0')
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (BlockingIOError, PermissionError, OSError):
                    time.sleep(0.025)
            if not acquired:
                raise SyncError('电脑保险库正在被另一进程写入，等待超时；已取消本次请求')
            yield
        finally:
            if acquired:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read(self):
        if self.path.is_symlink():
            raise SyncError('数据文件不允许为符号链接')
        if not self.path.exists():
            return {'format': 1, 'revision': 0, 'state': None, 'receipt': None}
        if not self.path.is_file() or self.path.stat().st_size > MAX_DATA_BYTES * 2 + 8192:
            raise SyncError('数据文件类型或大小异常')
        try:
            contents = self._decode(self.path.read_bytes())
        except OSError:
            raise SyncError('电脑同步数据文件无法读取，拒绝覆盖，请检查原文件')
        if (not isinstance(contents, dict) or contents.get('format') != 1 or
            type(contents.get('revision')) is not int or contents['revision'] < 0):
            raise SyncError('电脑同步记录格式损坏，拒绝覆盖')
        if contents.get('state') is not None:
            validate_main(contents['state'])
        return contents

    def snapshot(self):
        with self.lock, self._process_lock():
            value = self._read()
            return {'revision': value['revision'], 'state': copy.deepcopy(value.get('state'))}

    def _atomic(self, dest, content):
        temp = dest.with_name(dest.name + '.' + secrets.token_hex(8) + '.tmp')
        fd = os.open(str(temp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(content)
                out.flush()
                os.fsync(out.fileno())
            os.replace(str(temp), str(dest))
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

    def update(self, expected, state, request_id):
        if type(expected) is not int or expected < 0:
            raise SyncError('必须提供有效的预期版本号')
        if not isinstance(request_id, str) or not (8 <= len(request_id) <= 80) or not request_id.isascii() or not all(c.isalnum() or c in '-_' for c in request_id):
            raise SyncError('无效的请求 ID')
        raw = validate_main(state)
        fingerprint = hashlib.sha256(raw).hexdigest()
        with self.lock, self._process_lock():
            old = self._read()
            receipt = old.get('receipt') or {}
            if receipt.get('id') == request_id:
                if receipt.get('fingerprint') == fingerprint:
                    return {'revision': old['revision'], 'replayed': True}
                raise SyncConflict('同一请求 ID 对应不同数据，拒绝写入')
            if expected != old['revision']:
                raise SyncConflict('电脑端数据已由其他设备更新，请重新读取、合并后再提交')
            if old.get('state') is not None and digest(old['state']) == fingerprint:
                return {'revision': old['revision'], 'unchanged': True}
            next_doc = {'format': 1, 'revision': old['revision'] + 1, 'state': state,
                        'receipt': {'id': request_id, 'fingerprint': fingerprint}}
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.path.is_symlink():
                raise SyncError('数据文件不能是符号链接')
            # Preserve preceding server state before making a destructive overwrite.
            if old.get('state') is not None:
                backdir = self.path.parent / 'sync-history'
                if backdir.is_symlink():
                    raise SyncError('历史目录不能是符号链接')
                backdir.mkdir(parents=True, exist_ok=True, mode=0o700)
                previous = self._encode(old)
                self._atomic(backdir / ('revision-%010d.json' % old['revision']), previous)
            body = self._encode(next_doc)
            self._atomic(self.path, body)
            if old.get('state') is not None:
                backups = sorted((self.path.parent / 'sync-history').glob('revision-*.json'))
                for outdated in backups[:-8]:
                    if outdated.is_file() and not outdated.is_symlink():
                        outdated.unlink()
            return {'revision': next_doc['revision'], 'replayed': False}
