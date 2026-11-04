#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only, opt-in PC-side monitoring for Personal Hub 1.3.
No arbitrary paths, shell commands, browser credentials or background scanners.
All paths/repos must be explicitly configured in the PC's local JSON file.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import queue
import urllib.request
import urllib.error
from decimal import Decimal, InvalidOperation
from pathlib import Path

STORE_DIR = Path.home() / '.personal-hub-bridge'
CONFIG = STORE_DIR / 'monitor.json'
EVENTS = STORE_DIR / 'events.json'
SLUG = re.compile(r'^[a-zA-Z0-9_.-]{1,100}$')
READ_TIMEOUT = 5
CACHE_SECONDS = 15 * 60
MAX_EVENTS = 180


def safe_slug(s):
    return isinstance(s, str) and SLUG.fullmatch(s) is not None and s not in ('.', '..')


def validate_config(conf):
    if not isinstance(conf, dict):
        raise ValueError('配置应为 JSON 对象')
    repos, projects = conf.get('repos', []), conf.get('projects', [])
    if not isinstance(repos, list) or len(repos) > 8 or not isinstance(projects, list) or len(projects) > 8:
        raise ValueError('repos/projects 应为至多 8 条的数组')
    repo_out, project_out = [], []
    for item in repos:
        if not isinstance(item, str) or item.count('/') != 1:
            raise ValueError('GitHub 仓库必须写为 owner/repo')
        owner, repo = item.split('/')
        if not safe_slug(owner) or not safe_slug(repo):
            raise ValueError('GitHub 仓库名称含不允许的字符')
        if item not in repo_out:
            repo_out.append(item)
    for item in projects:
        if not isinstance(item, dict):
            raise ValueError('project 应为对象')
        name, path = item.get('name'), item.get('path')
        if (not isinstance(name, str) or not 1 <= len(name) <= 70 or
                any(ord(c) < 32 for c in name) or not isinstance(path, str) or
                len(path) > 1024 or not path.strip()):
            raise ValueError('本地项目名称或路径无效')
        project_out.append({'name': name, 'path': str(Path(path).expanduser())})
    return {'repos': repo_out, 'projects': project_out, 'codex': conf.get('codex') is True,
            'deepseek': conf.get('deepseek') is True}


def load_config(path=CONFIG):
    path = Path(path)
    if not path.is_file():
        return validate_config({}), '未配置：请在电脑创建 monitor.json'
    if path.is_symlink():
        return validate_config({}), '监控配置不能是符号链接'
    try:
        if path.stat().st_size > 32768:
            raise ValueError('配置文件过大')
        return validate_config(json.loads(path.read_text(encoding='utf-8'))), ''
    except (OSError, UnicodeError, ValueError) as exc:
        return validate_config({}), '配置无效：' + str(exc)[:90]


def read_json_https(url, token='', timeout=READ_TIMEOUT):
    if not url.startswith('https://api.github.com/') and url != 'https://api.deepseek.com/user/balance':
        raise ValueError('不允许访问未经批准的地址')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'PersonalHub-V9-Monitor/1.3'}
    if url.startswith('https://api.github.com/'):
        headers['X-GitHub-Api-Version'] = '2022-11-28'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(url, headers=headers)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            # Never forward Bearer secrets to redirect destinations.
            return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError('HTTP ' + str(response.status))
            content = response.read(512001)
            if len(content) > 512000:
                raise RuntimeError('上游响应过大')
            return json.loads(content.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        # Don't include upstream response bodies: may echo authentication details.
        if exc.code in (401, 403):
            raise RuntimeError('HTTP ' + str(exc.code) + '：无访问权限或额度限制')
        if exc.code == 404:
            raise RuntimeError('HTTP 404：仓库不存在或无权读取')
        raise RuntimeError('HTTP ' + str(exc.code))
    except urllib.error.URLError:
        raise RuntimeError('网络不可用或连接失败')


def github_status(full_name, getter=read_json_https):
    if not isinstance(full_name, str) or full_name.count('/') != 1 or not all(safe_slug(x) for x in full_name.split('/')):
        raise ValueError('仓库名称不合法')
    url = 'https://api.github.com/repos/{}/actions/runs?per_page=5'.format(full_name)
    data = getter(url, os.environ.get('GITHUB_TOKEN', ''))
    runs = data.get('workflow_runs', [])
    if not isinstance(runs, list):
        raise ValueError('GitHub 响应异常')
    out = []
    for item in runs[:5]:
        if not isinstance(item, dict):
            continue
        html_url = item.get('html_url', '')
        if not isinstance(html_url, str) or not html_url.startswith('https://github.com/' + full_name + '/actions/runs/'):
            html_url = ''
        out.append({'id': str(item.get('id', ''))[:30], 'name': str(item.get('name', 'Workflow'))[:100],
                    'status': str(item.get('status', 'unknown'))[:40],
                    'conclusion': str(item.get('conclusion') or '')[:40],
                    'updated_at': str(item.get('updated_at', ''))[:30],
                    'url': html_url})
    return {'repo': full_name, 'runs': out, 'state': 'ok'}


def git_status(item, runner=subprocess.run):
    path = Path(item['path']).expanduser()
    name = item['name']
    if not path.is_dir() or not (path / '.git').exists():
        return {'name': name, 'state': 'unavailable', 'reason': '未找到本地 Git 仓库'}
    def git(*args):
        try:
            r = runner(['git', '-C', str(path), *args], capture_output=True, text=True, timeout=3, check=False)
            if r.returncode:
                raise ValueError('git 命令未成功')
            return r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired, ValueError):
            raise ValueError('Git 状态不可读取')
    try:
        branch = git('rev-parse', '--abbrev-ref', 'HEAD')[:90]
        sha = git('rev-parse', '--verify', 'HEAD')[:40]
        # Includes untracked files; report only count, not personal filenames.
        changes = git('status', '--porcelain', '--untracked-files=normal').splitlines()
        return {'name': name, 'state': 'ok', 'branch': branch, 'sha': sha,
                'dirty': bool(changes), 'changed_files': min(len(changes), 9999)}
    except ValueError as exc:
        return {'name': name, 'state': 'unavailable', 'reason': str(exc)}


def extract_codex_limits(result):
    limits = result.get('rateLimits') if isinstance(result, dict) else None
    if not isinstance(limits, dict):
        raise ValueError('Codex 未提供额度信息')
    out = {'state': 'ok', 'limit_name': str(limits.get('limitName') or limits.get('limitId') or 'codex')[:65]}
    for key in ('primary', 'secondary'):
        window = limits.get(key)
        if not isinstance(window, dict):
            out[key] = None
            continue
        pct = window.get('usedPercent')
        if not isinstance(pct, (float, int)) or isinstance(pct, bool) or not 0 <= pct <= 100:
            out[key] = None
            continue
        reset = window.get('resetsAt')
        out[key] = {'used_percent': round(float(pct), 2), 'remaining_percent': round(100 - float(pct), 2),
                    'reset_at': int(reset) if isinstance(reset, (int, float)) and 0 < reset < 10**11 else None}
    if out['primary'] is None and out['secondary'] is None:
        raise ValueError('Codex 未提供可用额度窗口')
    return out


def codex_status(timeout=7):
    if not shutil.which('codex'):
        return {'state': 'unavailable', 'reason': '本机未找到 codex CLI'}
    proc = None
    try:
        proc = subprocess.Popen(['codex', 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, bufsize=1)
        incoming = queue.Queue(maxsize=100)
        def reader():
            for line in proc.stdout:
                try:
                    incoming.put_nowait(json.loads(line))
                except (ValueError, queue.Full):
                    pass
        threading.Thread(target=reader, daemon=True).start()
        def send(data):
            proc.stdin.write(json.dumps(data, ensure_ascii=False) + '\n')
            proc.stdin.flush()
        until = time.monotonic() + timeout
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'personal_hub', 'version': '1.3.0'}}})
        while time.monotonic() < until:
            try:
                response = incoming.get(timeout=min(0.5, max(0.01, until - time.monotonic())))
            except queue.Empty:
                continue
            if response.get('id') == 1:
                if 'error' in response:
                    raise RuntimeError('Codex 初始化失败')
                break
        else:
            raise RuntimeError('Codex 初始化超时')
        send({'method': 'initialized'})
        send({'id': 2, 'method': 'account/rateLimits/read'})
        while time.monotonic() < until:
            try:
                response = incoming.get(timeout=min(0.5, max(0.01, until - time.monotonic())))
            except queue.Empty:
                continue
            if response.get('id') == 2:
                if 'error' in response:
                    raise RuntimeError('Codex 额度接口拒绝请求')
                return extract_codex_limits(response.get('result'))
        raise RuntimeError('Codex 额度读取超时')
    except (OSError, ValueError, RuntimeError) as exc:
        return {'state': 'unavailable', 'reason': str(exc)[:100]}
    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                proc.kill()
                try:
                    proc.wait(timeout=1)
                except (OSError, subprocess.TimeoutExpired):
                    pass


def deepseek_status(getter=read_json_https):
    key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if not key:
        return {'state': 'unavailable', 'reason': '未在电脑环境中设置 DEEPSEEK_API_KEY'}
    try:
        obj = getter('https://api.deepseek.com/user/balance', key)
        rows = []
        for item in obj.get('balance_infos', [])[:4]:
            currency = item.get('currency')
            if currency not in ('CNY', 'USD'):
                continue
            raw = str(item.get('total_balance', ''))
            amount = Decimal(raw)
            if not amount.is_finite() or amount < 0:
                continue
            rows.append({'currency': currency, 'balance': format(amount, 'f')})
        if not rows:
            raise ValueError('余额数据缺失')
        return {'state': 'ok', 'available': obj.get('is_available') is True, 'balances': rows}
    except (ValueError, InvalidOperation, RuntimeError) as exc:
        return {'state': 'unavailable', 'reason': str(exc)[:90]}


class EventStore:
    def __init__(self, path=EVENTS):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.events = []
        self.commits = {}
        try:
            if self.path.is_file() and not self.path.is_symlink() and self.path.stat().st_size <= 262144:
                raw = json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(raw, dict):
                    self.events = [e for e in raw.get('events', []) if isinstance(e, dict) and isinstance(e.get('id'), str)][:MAX_EVENTS]
                    self.commits = raw.get('commits', {}) if isinstance(raw.get('commits'), dict) else {}
        except (ValueError, OSError, UnicodeError):
            pass

    def _persist(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        file = self.path.with_suffix('.tmp')
        text = json.dumps({'events': self.events[-MAX_EVENTS:], 'commits': self.commits}, ensure_ascii=False)
        with file.open('w', encoding='utf-8') as f:
            f.write(text)
        try:
            os.chmod(file, 0o600)
        except OSError:
            pass
        os.replace(file, self.path)

    def observe(self, event):
        ident = event['id']
        with self.lock:
            if any(x.get('id') == ident for x in self.events):
                return False
            safe = {k:event[k] for k in ('id','level','title','detail','source')}
            safe.update(time=int(time.time()), read=False)
            self.events.append(safe)
            self.events = self.events[-MAX_EVENTS:]
            self._persist()
            return True

    def mark(self, ids):
        if not isinstance(ids, list) or len(ids) > MAX_EVENTS or any(not isinstance(x, str) or len(x)>200 for x in ids):
            raise ValueError('事件 ID 列表无效')
        with self.lock:
            keys = set(ids)
            for event in self.events:
                if event['id'] in keys:
                    event['read'] = True
            self._persist()

    def view(self):
        with self.lock:
            return [dict(e) for e in reversed(self.events)]

    def observe_snapshot(self, snapshot):
        for repo in snapshot.get('github', []):
            if repo.get('state') != 'ok':
                continue
            for run in repo.get('runs', []):
                if run.get('status') == 'completed' and run.get('conclusion') in ('failure', 'timed_out', 'action_required'):
                    self.observe({'id':'github:'+repo['repo']+':'+run['id']+':'+run['conclusion'],
                                  'level':'red','title':'GitHub Actions 构建异常',
                                  'detail':repo['repo']+' · '+run['name']+' · '+run['conclusion'], 'source':'github'})
        limits = snapshot.get('codex', {})
        if limits.get('state') == 'ok':
            for key in ('primary', 'secondary'):
                part = limits.get(key)
                if part and part['remaining_percent'] <= 10:
                    reset = str(part.get('reset_at') or 'unknown')
                    self.observe({'id':'codex:'+key+':'+reset, 'level':'yellow',
                                  'title':'Codex 剩余额度不足 10%',
                                  'detail':'{} 窗口剩余 {}%'.format(key, part['remaining_percent']), 'source':'codex'})
        balance = snapshot.get('deepseek', {})
        if balance.get('state') == 'ok':
            for row in balance.get('balances', []):
                limit = Decimal('5') if row['currency'] == 'CNY' else Decimal('1')
                if Decimal(row['balance']) <= limit:
                    # Day-keyed threshold deduplicates periodic polling; a later day alerts again if still low.
                    day = time.strftime('%Y-%m-%d')
                    self.observe({'id':'deepseek:'+row['currency']+':'+day, 'level':'yellow',
                                  'title':'DeepSeek API 余额较低',
                                  'detail':row['currency']+' '+row['balance']+'（默认提示阈值）', 'source':'deepseek'})
        for project in snapshot.get('projects', []):
            if project.get('state') != 'ok':
                continue
            key = project['name']
            sha = project.get('sha', '')
            with self.lock:
                old = self.commits.get(key)
                if old and old != sha:
                    self.observe({'id':'git:'+key+':'+sha,'level':'green',
                                  'title':'本地项目出现新提交','detail':key+' · '+sha[:8], 'source':'git'})
                if old != sha:
                    self.commits[key] = sha
                    self._persist()
        for activity in snapshot.get('activities', []):
            state = activity.get('state')
            if state in ('failed', 'attention', 'done'):
                self.observe({'id':'activity:'+activity['id']+':'+state,
                              'level':'red' if state=='failed' else ('yellow' if state=='attention' else 'green'),
                              'title':'任务'+{'failed':'执行失败','attention':'待处理','done':'已完成'}[state],
                              'detail':activity['task']+' · '+activity.get('detail',''), 'source':'activity'})


class Monitor:
    def __init__(self, config_file=CONFIG, event_file=EVENTS, clock=time.monotonic):
        self.config_file = Path(config_file)
        self.events = EventStore(event_file)
        self.clock = clock
        self.lock = threading.RLock()
        self.cached = None
        self.cache_time = 0

    def snapshot(self, activities=None, refresh=False):
        with self.lock:
            now = self.clock()
            if self.cached is not None and now-self.cache_time < CACHE_SECONDS and not refresh:
                cached = dict(self.cached)
                cached['activities'] = activities or []
                self.events.observe_snapshot(cached)
                return cached
            conf, error = load_config(self.config_file)
            response = {'checked_at': int(time.time()), 'config_note': error, 'github': [], 'projects': [],
                        'codex': {'state': 'disabled'}, 'deepseek': {'state': 'disabled'},
                        'activities': activities or [], 'poll_interval_seconds': CACHE_SECONDS}
            for repo in conf['repos']:
                try:
                    response['github'].append(github_status(repo))
                except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
                    response['github'].append({'repo': repo, 'runs': [], 'state':'unavailable', 'reason': str(exc)[:100]})
            for project in conf['projects']:
                response['projects'].append(git_status(project))
            if conf['codex']:
                response['codex'] = codex_status()
            if conf['deepseek']:
                response['deepseek'] = deepseek_status()
            self.cached, self.cache_time = response, now
            self.events.observe_snapshot(response)
            return dict(response)
