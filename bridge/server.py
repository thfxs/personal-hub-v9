#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Personal Hub V9: LAN-only AI quick-command bridge (stdlib Python 3.9+).

Only sends text to an explicitly armed foreground AI chat window. It never runs
shell commands received over the network. Default behaviour is queue-only.
"""
import argparse
import ctypes
import http.cookies
import ipaddress
import json
import os
import platform
import secrets
import ssl
import stat
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
# Support normal script execution and importlib-based regression harnesses.
BRIDGE_DIR = Path(__file__).resolve().parent
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))
from monitor import Monitor, CONFIG as CONFIG_PATH
from sync_store import SyncStore, SyncError, SyncConflict

WEB = Path(__file__).resolve().parent / 'web'
PRESETS = {
    'continue': '继续。',
    'next': '好，继续下一步。',
    'check': '检查当前结果是否有遗漏或错误，并给出具体结论。',
    'fix': '请修复刚才发现的问题，完成后运行相关测试并报告结果。',
    'fullcode': '请直接提供修改后的完整可运行代码。',
    'summary': '总结当前进度、已完成事项、未解决问题和下一步。',
    'pause': '暂停当前任务，先汇报已经完成的工作与尚未完成的部分。',
}
ALLOWED_WINDOW_WORDS = ('chatgpt', 'codex', 'deepseek', 'claude', 'gemini', 'github copilot')
ALLOWED_PROCESS_WORDS = (
    'chrome', 'msedge', 'firefox', 'safari', 'chatgpt', 'codex',
    'code', 'wechatdevtools', 'arc', 'brave', 'opera', 'windows terminal',
)
MAX_QUEUE = 80
MAX_TEXT = 180
QUEUE_TTL = 30 * 60
REQUEST_TTL = 30 * 60
ACTIVITY_FILE = Path.home() / '.personal-hub-bridge' / 'activities.jsonl'
LOCK_SECONDS = 600
ARM_SECONDS = 600


def local_ip_candidates():
    candidates = set()
    try:
        for family, _, _, _, sockaddr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if family == socket.AF_INET:
                candidates.add(sockaddr[0])
    except OSError:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('192.0.2.1', 9))  # route selection only; no packet sent
        candidates.add(sock.getsockname()[0])
        sock.close()
    except OSError:
        pass
    return sorted(x for x in candidates if x != '127.0.0.1' and ipaddress.ip_address(x).is_private)


def is_local_client(ip):
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def is_lan_client(ip):
    try:
        v = ipaddress.ip_address(ip)
        return v.is_private or v.is_loopback
    except ValueError:
        return False


def safe_text(value):
    if not isinstance(value, str) or not (1 <= len(value) <= MAX_TEXT):
        raise ValueError('指令必须是 1～180 字的单行文本')
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError('指令不得包含换行、制表符等控制字符')
    return value


def active_window_win():
    from ctypes import wintypes
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError('找不到前台窗口')
    buf = ctypes.create_unicode_buffer(1024)
    u.GetWindowTextW(hwnd, buf, len(buf))
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    p = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
    proc = ''
    if p:
        try:
            b = ctypes.create_unicode_buffer(1024)
            length = wintypes.DWORD(len(b))
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(p, 0, b, ctypes.byref(length)):
                proc = os.path.basename(b.value)
        finally:
            ctypes.windll.kernel32.CloseHandle(p)
    return (hwnd, proc, buf.value)


def active_window_mac():
    script = '''tell application "System Events"
set p to first application process whose frontmost is true
set pn to name of p
set wt to ""
try
set wt to name of front window of p
end try
return pn & linefeed & wt
end tell'''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=6)
    if result.returncode:
        raise RuntimeError('无法读取前台应用；请检查 macOS 辅助功能授权')
    parts = result.stdout.strip().split('\n', 1)
    return ('mac-window', parts[0], parts[1] if len(parts) > 1 else '')


def active_window_linux():
    if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland':
        raise RuntimeError('Wayland 会话不支持自动输入；已安全转入待发队列')
    if not shutil.which('xdotool') or not shutil.which('xclip'):
        raise RuntimeError('Linux X11 自动输入需要 xdotool 和 xclip；已转入待发队列')
    p = subprocess.run(['xdotool', 'getactivewindow'], capture_output=True, text=True, timeout=3, check=True)
    handle = p.stdout.strip()
    p2 = subprocess.run(['xdotool', 'getwindowname', handle], capture_output=True, text=True, timeout=3, check=True)
    p3 = subprocess.run(['xdotool', 'getwindowpid', handle], capture_output=True, text=True, timeout=3)
    proc = ''
    if p3.returncode == 0:
        try:
            proc = Path('/proc/' + p3.stdout.strip() + '/comm').read_text().strip()
        except OSError:
            pass
    return (handle, proc, p2.stdout.strip())


def current_window():
    system = platform.system()
    if system == 'Windows':
        return active_window_win()
    if system == 'Darwin':
        return active_window_mac()
    if system == 'Linux':
        return active_window_linux()
    raise RuntimeError('当前操作系统不支持自动输入；已转入待发队列')


def permitted_window(window):
    _handle, proc, title = window
    p, t = proc.casefold(), title.casefold()
    if not any(word in p for word in ALLOWED_PROCESS_WORDS):
        return False
    # Requiring a matched window TITLE prevents typing in an unrelated browser tab.
    return any(word in t for word in ALLOWED_WINDOW_WORDS)


def send_windows(text):
    """Send only Unicode keystrokes + Return, never execute OS commands."""
    from ctypes import wintypes
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                    ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
                    ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]
    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]
    class INPUTUNION(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]
    class INPUT(ctypes.Structure):
        _fields_ = [('type', wintypes.DWORD), ('info', INPUTUNION)]
    def make(vk, scan, flags):
        item = INPUT()
        item.type = 1
        item.info.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        return item
    inputs = []
    raw = text.encode('utf-16-le')
    for i in range(0, len(raw), 2):
        char = int.from_bytes(raw[i:i+2], 'little')
        inputs.extend([make(0, char, 0x0004), make(0, char, 0x0006)])
    inputs.extend([make(0x0D, 0, 0), make(0x0D, 0, 0x0002)])
    arr = (INPUT * len(inputs))(*inputs)
    u = ctypes.windll.user32
    u.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    u.SendInput.restype = wintypes.UINT
    count = u.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
    if count != len(inputs):
        raise RuntimeError('系统未接受全部按键输入，请核对目标窗口是否收到部分文本')


def send_mac(text):
    subprocess.run(['pbcopy'], input=text, text=True, timeout=3, check=True)
    script = '''tell application "System Events"
keystroke "v" using {command down}
delay 0.08
key code 36
end tell'''
    p = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=8)
    if p.returncode:
        raise RuntimeError('macOS 粘贴失败；请检查辅助功能权限。剪贴板可能已被更改')


def send_linux(text, window):
    subprocess.run(['xclip', '-selection', 'clipboard'], input=text, text=True, timeout=4, check=True)
    # Check the focused window *again* after clipboard operations, before sending.
    if current_window()[0] != window[0]:
        raise RuntimeError('前台窗口已变化，未发送按键')
    subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+v'], timeout=3, check=True)
    time.sleep(.08)
    subprocess.run(['xdotool', 'key', '--clearmodifiers', 'Return'], timeout=3, check=True)


def send_to_foreground(text):
    window = current_window()
    if not permitted_window(window):
        raise RuntimeError('当前前台窗口不是允许的 AI 对话窗口；已转入待发队列')
    system = platform.system()
    if system == 'Windows':
        if current_window()[0] != window[0]:
            raise RuntimeError('窗口已变化，指令未发送')
        send_windows(text)
    elif system == 'Darwin':
        # On macOS, pasting temporarily changes the system clipboard.
        subprocess.run(['pbcopy'], input=text, text=True, timeout=3, check=True)
        if current_window()[1:] != window[1:]:
            raise RuntimeError('窗口已变化，指令未发送（剪贴板可能已变化）')
        script = 'tell application "System Events" to keystroke "v" using {command down}\ndelay 0.08\ntell application "System Events" to key code 36'
        p = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=8)
        if p.returncode:
            raise RuntimeError('macOS 自动输入被拒绝，请检查辅助功能权限')
    elif system == 'Linux':
        send_linux(text, window)
    else:
        raise RuntimeError('不支持当前操作系统')
    return {'process': window[1], 'window': window[2][:100]}


class BridgeState:
    def __init__(self, injector=None, activity_file=None):
        self.lock = threading.RLock()
        self.pin = '{:08d}'.format(secrets.randbelow(90000000) + 10000000)
        self.sessions = {}
        self.fails = {}
        self.requests = {}
        self.queue = []
        self.armed_until = 0.0
        self.injector = injector or send_to_foreground
        self.audit = deque(maxlen=20)
        self.last_seen = {}
        self.request_results = {}
        self.completed_retries = {}
        self.activity_file = Path(activity_file) if activity_file else ACTIVITY_FILE

    def _now(self):
        return time.monotonic()

    def pair(self, ip, pin):
        with self.lock:
            now = self._now()
            attempts = [t for t in self.fails.get(ip, []) if now-t < LOCK_SECONDS]
            if len(attempts) >= 5:
                return None, '配对尝试过多，请等待十分钟或重启桥接器'
            if not isinstance(pin, str) or not secrets.compare_digest(pin, self.pin):
                attempts.append(now)
                self.fails[ip] = attempts
                return None, '配对码错误'
            self.fails.pop(ip, None)
            key = secrets.token_urlsafe(32)
            self.sessions[key] = now + 10 * 3600
            return key, None

    def valid(self, key):
        with self.lock:
            now = self._now()
            return bool(key and self.sessions.get(key, 0) > now)

    def arm(self, minutes=10):
        with self.lock:
            self.armed_until = self._now() + min(minutes * 60, ARM_SECONDS)

    def disarm(self):
        with self.lock:
            self.armed_until = 0

    def armed(self):
        return self.armed_until > self._now()

    def public_status(self, local):
        with self.lock:
            self._prune_queue()
            return {'armed': self.armed(), 'armed_seconds': max(0, int(self.armed_until-self._now())),
                    'queued': len(self.queue), 'is_pc': bool(local), 'platform': platform.system(),
                    'mode': '仅发送文字；不执行终端命令', 'audit': list(self.audit)[-5:]}

    def _rate_limit(self, ip):
        now = self._now()
        recent = [t for t in self.requests.get(ip, []) if now-t < 60]
        if len(recent) >= 12:
            raise ValueError('操作过于频繁，请稍后重试')
        recent.append(now)
        self.requests[ip] = recent

    def _prune_queue(self):
        now = self._now()
        count = len(self.queue)
        self.queue = [q for q in self.queue if now-q['_created_mono'] < QUEUE_TTL]
        if count != len(self.queue):
            self.audit.append({'result': 'expired', 'count': count-len(self.queue), 'at': int(time.time())})
        self.request_results = {k: v for k, v in self.request_results.items() if now-v[2] < REQUEST_TTL}
        self.completed_retries = {k: v for k, v in self.completed_retries.items() if now-v[1] < REQUEST_TTL}

    def read_activities(self):
        """Only read an explicitly emitted local bounded JSONL file; no process scans."""
        p = self.activity_file
        try:
            if p.is_symlink() or not p.is_file():
                return []
            size = p.stat().st_size
            with p.open('rb') as f:
                offset = max(0, size - 131072)
                f.seek(offset)
                raw = f.read(131072)
            if offset:
                raw = raw.split(b'\n', 1)[-1]
            lines = raw.splitlines()[-40:]
        except (OSError, ValueError):
            return []
        result = []
        for line in lines:
            try:
                e = json.loads(line)
                if not isinstance(e, dict):
                    continue
                if not isinstance(e.get('time'), int) or e['time'] < 0:
                    continue
                if not isinstance(e.get('id'), str) or len(e['id']) > 40:
                    continue
                task, state, detail = validate_activity(e)
                result.append({'id': e['id'], 'time': e['time'], 'task': task,
                               'state': state, 'detail': detail})
            except (ValueError, TypeError, UnicodeError):
                continue
        return result[-12:][::-1]

    def _queue(self, item, error=''):
        if len(self.queue) >= MAX_QUEUE:
            self.queue.pop(0)
        item['state'] = '待发'
        item['note'] = error[:140]
        item['expires'] = item['created'] + QUEUE_TTL
        self.queue.append(item)
        self.audit.append({'result': 'queued', 'at': int(time.time())})
        return {'ok': True, 'result': 'queued', 'reason': error, 'id': item['id']}

    def dispatch(self, ip, text, old_id=None, request_id=None):
        safe_text(text)
        with self.lock:
            self._prune_queue()
            now = self._now()
            if request_id is not None:
                if not isinstance(request_id, str) or not (8 <= len(request_id) <= 64) or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.' for ch in request_id):
                    raise ValueError('请求 ID 格式无效')
                previous = self.request_results.get((ip, request_id))
                if previous:
                    if previous[0] != text:
                        raise ValueError('请求 ID 已用于另一条不同指令')
                    return dict(previous[1])
            if old_id and old_id in self.completed_retries:
                return dict(self.completed_retries[old_id][0])
            self._rate_limit(ip)
            if old_id is None:
                prev = self.last_seen.get(ip)
                if prev and prev[0] == text and now-prev[1] < 1.5:
                    result = {'ok': True, 'result': 'duplicate_skipped'}
                    if request_id:
                        self.request_results[(ip, request_id)] = (text, result, now)
                    return result
                self.last_seen[ip] = (text, now)
                item = {'id': secrets.token_hex(8), 'text': text, 'created': int(time.time()), 'state': '待发', '_created_mono': now}
            else:
                item = next((entry for entry in self.queue if entry['id'] == old_id), None)
                if not item or item['text'] != text:
                    raise ValueError('待发指令已不存在')
            if not self.armed():
                if old_id:
                    result = {'ok': True, 'result': 'queued', 'reason': '电脑端尚未授权自动发送'}
                else:
                    result = self._queue(item, '电脑端尚未授权自动发送')
                if request_id:
                    self.request_results[(ip, request_id)] = (text, result, now)
                return result
            try:
                window = self.injector(text)
            except Exception as exc:
                message = str(exc)[:160]
                if old_id:
                    item['note'] = message
                    result = {'ok': True, 'result': 'queued', 'reason': message}
                else:
                    result = self._queue(item, message)
                if request_id:
                    self.request_results[(ip, request_id)] = (text, result, now)
                return result
            if old_id:
                self.queue = [q for q in self.queue if q['id'] != old_id]
            self.audit.append({'result': 'sent_unconfirmed', 'at': int(time.time())})
            result = {'ok': True, 'result': 'sent_unconfirmed', 'window': window}
            if request_id:
                self.request_results[(ip, request_id)] = (text, result, now)
            if old_id:
                self.completed_retries[old_id] = (result, now)
            return result

    def queue_view(self):
        with self.lock:
            self._prune_queue()
            return [{k:v for k,v in item.items() if not k.startswith('_')}
                    for item in self.queue[-MAX_QUEUE:]]


def validate_activity(event):
    task, state, detail = event.get('task'), event.get('state'), event.get('detail', '')
    if not isinstance(task, str) or not 1 <= len(task) <= 90 or any(ord(c) < 32 for c in task):
        raise ValueError('无效任务名')
    if state not in ('started', 'done', 'failed', 'attention', 'info'):
        raise ValueError('无效状态')
    if not isinstance(detail, str) or len(detail) > 200 or any(ord(c) < 32 for c in detail):
        raise ValueError('无效说明')
    return task, state, detail


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self, server_address, state, handler=None, tls=False, encrypted_vault=False,
                 allow_insecure_lan=False, sync_store=None):
        self.state = state
        self.monitor = Monitor()
        self.sync_store = sync_store if sync_store is not None else SyncStore()
        self.tls_enabled = bool(tls)
        self.vault_encrypted = bool(encrypted_vault or getattr(self.sync_store, 'encrypted', False))
        self.allow_insecure_lan = bool(allow_insecure_lan)
        super().__init__(server_address, handler or Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = 'PersonalHubBridge/1.6'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        # No messages, tokens, PINs or personal data printed to HTTP log.
        pass

    def _headers(self, content_type, length, status=200, cookie=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()

    def _json(self, value, status=200, cookie=None):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self._headers('application/json; charset=utf-8', len(body), status, cookie)
        self.wfile.write(body)

    def _error(self, status, message):
        self._json({'ok': False, 'error': message}, status)

    def _host_ok(self):
        host = self.headers.get('Host', '').strip().lower()
        if not host or '@' in host or '/' in host or ',' in host:
            return False
        try:
            if host.startswith('['):
                h = host.split(']')[0][1:]
            else:
                h = host.rsplit(':', 1)[0] if host.count(':') == 1 else host
            if h == 'localhost':
                return True
            address = ipaddress.ip_address(h)
            return address.is_private or address.is_loopback
        except ValueError:
            return False

    def _origin_ok(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True
        try:
            u = urlsplit(origin)
            return (u.scheme == ('https' if self.server.tls_enabled else 'http') and u.netloc.lower() == self.headers.get('Host', '').lower()
                    and u.path in ('', '/') and not u.query and not u.fragment)
        except ValueError:
            return False

    def _preflight(self):
        if not is_lan_client(self.client_address[0]):
            self._error(403, '仅允许局域网访问')
            return False
        if not self._host_ok():
            self._error(403, 'Host 不受信任')
            return False
        return True

    def _remote_transport_ok(self):
        # The mobile client IP is trustworthy only as a LAN-vs-loopback discriminator.
        # Never mistake an HTTP LAN connection for confidential TLS transport.
        return (is_local_client(self.client_address[0]) or self.server.tls_enabled
                or self.server.allow_insecure_lan)

    def _sync_transport_ok(self):
        # Only local loopback testing can retain the old plaintext sync contract.
        # Remote sync always requires BOTH verified TLS transport and encrypted PC vault.
        return (is_local_client(self.client_address[0]) or
                (self.server.tls_enabled and self.server.vault_encrypted))

    def _cookie_session(self):
        try:
            cookies = http.cookies.SimpleCookie(self.headers.get('Cookie', ''))
            key = cookies.get('phb_session')
            return key.value if key else ''
        except http.cookies.CookieError:
            return ''

    def _auth(self):
        return self.server.state.valid(self._cookie_session())

    def do_GET(self):
        if not self._preflight():
            return
        path = urlsplit(self.path).path
        if not self._remote_transport_ok():
            self._error(426, '手机端网页与接口均要求 HTTPS；仅本机 localhost 可在 HTTP 使用')
            return
        # A single-origin copy of the PWA, independent browser storage on each device.
        # Only files from the packaged public web/ directory are served here.
        if path == '/hub':
            self.send_response(302)
            self.send_header('Location', '/hub/')
            self.send_header('Content-Length', '0')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        if path.startswith('/hub/'):
            from urllib.parse import unquote
            rel = unquote(path[len('/hub/'):]) or 'index.html'
            parts = rel.split('/')
            allowed = ('.html', '.css', '.js', '.png', '.svg', '.webmanifest')
            if not parts or any(x in ('', '.', '..') or x.startswith('.') or '\\' in x for x in parts):
                self._error(404, '文件不存在')
                return
            public = BRIDGE_DIR.parent / 'web'
            file = public.joinpath(*parts)
            if file.suffix not in allowed or not file.is_file() or file.is_symlink() or not file.resolve().is_relative_to(public.resolve()):
                self._error(404, '文件不存在')
                return
            content = file.read_bytes()
            mime = {'.html':'text/html', '.css':'text/css', '.js':'application/javascript',
                    '.png':'image/png', '.svg':'image/svg+xml',
                    '.webmanifest':'application/manifest+json'}[file.suffix]
            self._headers(mime + ('; charset=utf-8' if file.suffix not in ('.png',) else ''), len(content))
            self.wfile.write(content)
            return
        static = {'/': ('index.html', 'text/html'), '/pc': ('pc.html', 'text/html'),
                  '/ui.js': ('ui.js', 'application/javascript'), '/ui.css': ('ui.css', 'text/css'),
                  '/monitor': ('monitor.html', 'text/html'),
                  '/monitor.js': ('monitor.js', 'application/javascript'),
                  '/monitor.css': ('monitor.css', 'text/css')}
        if path in static:
            name, mime = static[path]
            if path == '/pc' and not is_local_client(self.client_address[0]):
                self._error(403, '电脑授权页只能在电脑本机打开')
                return
            content = (WEB / name).read_bytes()
            self._headers(mime + '; charset=utf-8', len(content))
            self.wfile.write(content)
            return
        if path == '/api/status':
            if not self._auth():
                self._json({'ok': False, 'paired': False})
            else:
                self._json({'ok': True, 'paired': True, **self.server.state.public_status(is_local_client(self.client_address[0]))})
            return
        if path == '/api/sync':
            if not self._sync_transport_ok():
                self._error(426, '远程同步要求 HTTPS 和电脑加密保险库')
            elif not self._auth():
                self._error(401, '请先配对')
            else:
                try:
                    self._json({'ok': True, **self.server.sync_store.snapshot()})
                except SyncError as exc:
                    self._error(503, str(exc))
            return
        if path == '/api/monitor':
            if not self._auth():
                self._error(401, '请先配对')
            else:
                self._json({'ok': True, 'data': self.server.monitor.snapshot(
                    self.server.state.read_activities())})
            return
        if path == '/api/events':
            if not self._auth():
                self._error(401, '请先配对')
            else:
                self._json({'ok': True, 'items': self.server.monitor.events.view()})
            return
        if path == '/api/activity':
            if not self._auth():
                self._error(401, '请先配对')
            else:
                self._json({'ok': True, 'items': self.server.state.read_activities()})
            return
        if path == '/api/queue':
            if not self._auth():
                self._error(401, '请先配对')
            else:
                self._json({'ok': True, 'items': self.server.state.queue_view()})
            return
        self._error(404, '页面不存在')

    def do_POST(self):
        if not self._preflight():
            self.close_connection = True
            return
        if not self._remote_transport_ok():
            self.close_connection = True
            self._error(426, '手机端指令要求 HTTPS；HTTP 仅允许本机 localhost')
            return
        if not self._origin_ok():
            self.close_connection = True
            self._error(403, '跨站来源不允许')
            return
        if self.headers.get('X-Bridge-Request') != '1':
            self.close_connection = True
            self._error(403, '缺少同源请求标记')
            return
        try:
            n = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            n = -1
        if not (0 <= n <= (1_500_000 if urlsplit(self.path).path == '/api/sync' else 4096)):
            self.close_connection = True
            self._error(413, '请求长度超限')
            return
        try:
            body = json.loads(self.rfile.read(n).decode('utf-8'))
            if not isinstance(body, dict):
                raise ValueError('请求必须是 JSON 对象')
        except (ValueError, UnicodeError, RecursionError) as exc:
            self._error(400, 'JSON 无效：' + str(exc)[:100])
            return
        path = urlsplit(self.path).path
        ip = self.client_address[0]
        if path == '/api/pair':
            key, err = self.server.state.pair(ip, body.get('pin'))
            if err:
                self._error(429 if err.startswith('配对尝试过多') else 401, err)
                return
            self._json({'ok': True, 'paired': True}, cookie='phb_session=' + key + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=36000' + ('; Secure' if self.server.tls_enabled else ''))
            return
        if not self._auth():
            self._error(401, '请先配对')
            return
        if path.startswith('/api/admin/'):
            if not is_local_client(ip):
                self._error(403, '仅电脑本机可以授权或解除授权')
                return
            if path == '/api/admin/arm':
                self.server.state.arm()
                self._json({'ok': True, **self.server.state.public_status(True)})
            elif path == '/api/admin/disarm':
                self.server.state.disarm()
                self._json({'ok': True, **self.server.state.public_status(True)})
            elif path == '/api/admin/clear-queue':
                with self.server.state.lock:
                    self.server.state.queue.clear()
                self._json({'ok': True})
            else:
                self._error(404, '操作不存在')
            return
        if path == '/api/sync':
            if not self._sync_transport_ok():
                self._error(426, '远程同步必须启用 HTTPS 和电脑加密保险库')
                return
            try:
                result = self.server.sync_store.update(body.get('revision'), body.get('state'), body.get('request_id'))
                self._json({'ok': True, **result})
            except SyncConflict as exc:
                self._error(409, str(exc))
            except SyncError as exc:
                self._error(400, str(exc))
            except OSError:
                self._error(503, '电脑磁盘写入失败，请核对目录权限和磁盘空间')
            return
        if path == '/api/events/read':
            try:
                self.server.monitor.events.mark(body.get('ids'))
                self._json({'ok': True})
            except ValueError as exc:
                self._error(400, str(exc))
            return
        if path == '/api/dispatch':
            preset = body.get('preset')
            if preset is not None:
                if not isinstance(preset, str) or preset not in PRESETS:
                    self._error(400, '快捷指令不存在')
                    return
                txt = PRESETS[preset]
            else:
                txt = body.get('text')
            try:
                result = self.server.state.dispatch(ip, txt, request_id=body.get('request_id'))
                self._json(result)
            except ValueError as exc:
                self._error(400, str(exc))
            return
        if path == '/api/queue/retry':
            item_id = body.get('id')
            if not isinstance(item_id, str):
                self._error(400, '缺少指令 ID')
                return
            with self.server.state.lock:
                self.server.state._prune_queue()
                item = next((x for x in self.server.state.queue if x['id'] == item_id), None)
                cached = self.server.state.completed_retries.get(item_id)
            if not item and cached:
                self._json(cached[0])
                return
            if not item:
                self._error(404, '指令不存在或已过期，请勿盲目重复操作')
                return
            try:
                self._json(self.server.state.dispatch(ip, item['text'], item_id))
            except ValueError as exc:
                self._error(400, str(exc))
            return
        self._error(404, '操作不存在')


def read_secret_file(path):
    p = Path(path).expanduser()
    if p.is_symlink() or not p.is_file():
        raise SyncError('密码文件不能是链接且必须为普通文件')
    if os.name != 'nt' and (stat.S_IMODE(p.stat().st_mode) & 0o077):
        raise SyncError('密码文件须仅本人可读：请执行 chmod 600 <密码文件>')
    secret = p.read_bytes().rstrip(b'\r\n')
    if len(secret) < 16 or len(secret) > 1024:
        raise SyncError('密码文件内容必须为 16～1024 字节')
    return secret


def main(argv=None):
    p = argparse.ArgumentParser(description='Personal Hub 1.6 电脑桥 · TLS + 加密保险库保护')
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--bind', default='0.0.0.0', help='默认监听局域网；可用 127.0.0.1 限本机')
    p.add_argument('--tls-cert', help='电脑端 HTTPS 服务器证书 PEM（含本机 IP 的 SAN）')
    p.add_argument('--tls-key', help='电脑端 HTTPS 私钥 PEM（不能放入 Git）')
    p.add_argument('--vault-passphrase-file', help='电脑加密同步保险库密码文件（推荐 chmod 600）')
    p.add_argument('--vault-path', help='自定义同步保险库文件位置')
    p.add_argument('--allow-insecure-lan', action='store_true',
                   help='仅用于旧版非敏感指令调试；绝不允许远程明文同步')
    opts = p.parse_args(argv)
    if not (1024 <= opts.port <= 65535):
        p.error('端口必须为 1024～65535')
    if bool(opts.tls_cert) != bool(opts.tls_key):
        p.error('--tls-cert 和 --tls-key 必须同时提供')
    try:
        password = read_secret_file(opts.vault_passphrase_file) if opts.vault_passphrase_file else None
        vault = SyncStore(opts.vault_path, password=password)
        # Verify a pre-existing vault before starting the service, including wrong password.
        vault.snapshot()
    except (SyncError, OSError) as exc:
        p.error('同步保险库预检查失败：' + str(exc))
    state = BridgeState()
    server = None
    try:
        server = BridgeServer((opts.bind, opts.port), state, tls=bool(opts.tls_cert),
                              allow_insecure_lan=opts.allow_insecure_lan, sync_store=vault)
        if opts.tls_cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(opts.tls_cert, opts.tls_key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
    except (OSError, ssl.SSLError, ValueError) as exc:
        if server:
            server.server_close()
        print('启动失败：', exc, file=sys.stderr)
        return 1
    scheme = 'https' if server.tls_enabled else 'http'
    print('=' * 58)
    print('Personal Hub 1.6 · 电脑快捷指令桥 + 安全同步门禁')
    print('电脑授权页： {}://127.0.0.1:{}/pc'.format(scheme, opts.port))
    for ip in local_ip_candidates():
        print('V9 访问地址：{}://{}:{}/hub/'.format(scheme, ip, opts.port))
    print('本次启动配对码：', state.pin)
    print('指令默认待发；前台自动输入只能在电脑本机显式授权，最多 10 分钟')
    print('移动端 HTTPS：{}；电脑保险库 AES-GCM：{}'.format('开启' if server.tls_enabled else '关闭',
                                                      '开启' if vault.encrypted else '关闭'))
    if not server.tls_enabled:
        print('保护门禁：外部手机 HTTP 请求默认拒绝；本机 127.0.0.1 仍可离线调试。')
    if not vault.encrypted:
        print('保护门禁：手机远程同步拒绝，直至电脑端启用加密保险库。')
    if opts.allow_insecure_lan:
        print('警告：已显式允许外部手机 HTTP 指令接口；配对码及指令可被局域网旁观者截获；不允许远程同步。')
    print('仅用家庭可信网络，禁止路由器端口映射；TLS 自签名证书必须在客户端事先验证信任。')
    print('同步数据位置：', vault.path)
    print('监控配置：', CONFIG_PATH)
    print('=' * 58)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        print('\n正在关闭')
    finally:
        state.disarm()
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
