#!/usr/bin/env python3
import importlib.util
import http.cookiejar
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))
from monitor import (validate_config, load_config, github_status, extract_codex_limits,
                     deepseek_status, git_status, EventStore, Monitor, read_json_https)
from server import BridgeState, BridgeServer

class MonitorUnitTests(unittest.TestCase):
    def test_config_validation_blocks_traversal_and_urls(self):
        for repo in ('bob/repo/extra', 'https://github.com/bob/repo', '../repo', 'bob/repo?x=1'):
            with self.subTest(repo=repo), self.assertRaises(ValueError):
                validate_config({'repos':[repo]})
        with self.assertRaises(ValueError):
            validate_config({'repos':['bob/repo']*9})
        self.assertEqual(validate_config({'repos':['bob/repo','bob/repo']})['repos'], ['bob/repo'])

    def test_config_missing_is_explicitly_unconfigured(self):
        with tempfile.TemporaryDirectory() as d:
            data, msg = load_config(pathlib.Path(d) / 'none.json')
            self.assertFalse(data['repos'])
            self.assertIn('未配置', msg)

    def test_github_allowlist_blocks_arbitrary_targets(self):
        with self.assertRaisesRegex(ValueError, '不允许'):
            read_json_https('https://evil.example/api')

    def test_github_parsing_and_invalid_url_removed(self):
        def fetch(url, token=''):
            self.assertEqual(url, 'https://api.github.com/repos/acme/example/actions/runs?per_page=5')
            return {'workflow_runs':[{'id':47,'name':'build','status':'completed','conclusion':'failure',
                                      'updated_at':'2026-11-04T11:00:00Z','html_url':'http://bad.example/' }]}
        run = github_status('acme/example', fetch)['runs'][0]
        self.assertEqual(run['conclusion'],'failure')
        self.assertEqual(run['url'],'')

    def test_codex_window_parsing_and_missing_are_distinct(self):
        info = extract_codex_limits({'rateLimits': {'limitId':'codex','primary':{'usedPercent':95,'resetsAt':1810000000}, 'secondary':None}})
        self.assertEqual(info['primary']['remaining_percent'],5)
        self.assertIsNone(info['secondary'])
        with self.assertRaises(ValueError):
            extract_codex_limits({'rateLimits':{}})

    def test_deepseek_decimal_balances_never_echo_key(self):
        def fake(url, token):
            self.assertEqual(token, 'SUPER_PRIVATE_SECRET')
            return {'is_available':True,'balance_infos':[{'currency':'CNY','total_balance':'4.28'}]}
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY':'SUPER_PRIVATE_SECRET'}):
            result = deepseek_status(fake)
        self.assertEqual(result['balances'][0]['balance'],'4.28')
        self.assertNotIn('SUPER_PRIVATE_SECRET',json.dumps(result))

    def test_git_status_read_only(self):
        if not shutil.which('git'):
            self.skipTest('git not installed')
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(['git','init','-q',d],check=True)
            p=pathlib.Path(d)
            (p/'README.txt').write_text('1')
            subprocess.run(['git','-C',d,'add','.'],check=True)
            subprocess.run(['git','-C',d,'-c','user.name=Test','-c','user.email=test@example.com','commit','-qm','first'],check=True)
            r = git_status({'name':'Demo','path':d})
            self.assertEqual(r['state'],'ok')
            self.assertEqual(r['changed_files'],0)
            (p/'other.txt').write_text('2')
            r = git_status({'name':'Demo','path':d})
            self.assertTrue(r['dirty'])
            self.assertEqual(r['changed_files'],1)
            self.assertNotIn('other.txt', json.dumps(r))

    def test_event_dedupe_read_persist(self):
        with tempfile.TemporaryDirectory() as d:
            f=pathlib.Path(d)/'events.json'
            events=EventStore(f)
            e={'id':'a','level':'red','title':'失败','detail':'测试','source':'test'}
            self.assertTrue(events.observe(e))
            self.assertFalse(events.observe(e))
            self.assertEqual(len(events.view()),1)
            events.mark(['a'])
            self.assertTrue(EventStore(f).view()[0]['read'])

    def test_snapshot_events_are_not_generated_from_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            events=EventStore(pathlib.Path(d)/'events.json')
            snap={'github':[{'repo':'x/y','state':'unavailable','runs':[]}],
                  'codex':{'state':'unavailable'},'deepseek':{'state':'unavailable'},
                  'projects':[],'activities':[]}
            events.observe_snapshot(snap)
            self.assertEqual(events.view(),[])

    def test_github_failed_run_and_codex_low_quota_events(self):
        with tempfile.TemporaryDirectory() as d:
            events=EventStore(pathlib.Path(d)/'events.json')
            snap={'github':[{'repo':'x/y','state':'ok','runs':[{'id':'22','name':'Build','status':'completed','conclusion':'failure'}]}],
                  'codex':{'state':'ok','primary':{'remaining_percent':9,'reset_at':1810000000},'secondary':None},
                  'deepseek':{'state':'disabled'},'projects':[],'activities':[]}
            events.observe_snapshot(snap)
            events.observe_snapshot(snap)
            self.assertEqual(len(events.view()),2)

    def test_first_commit_is_baseline_second_is_event(self):
        with tempfile.TemporaryDirectory() as d:
            events=EventStore(pathlib.Path(d)/'events.json')
            one={'github':[],'codex':{},'deepseek':{},'projects':[{'name':'a','state':'ok','sha':'a'*40}],'activities':[]}
            events.observe_snapshot(one)
            self.assertFalse(events.view())
            one['projects'][0]['sha']='b'*40
            events.observe_snapshot(one)
            self.assertEqual(events.view()[0]['title'],'本地项目出现新提交')

    def test_monitor_15_minute_cache(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=pathlib.Path(d)/'monitor.json'
            cfg.write_text(json.dumps({'repos':['example/repo']}))
            m=Monitor(cfg,pathlib.Path(d)/'events.json',clock=lambda:100.0)
            with patch('monitor.github_status',return_value={'repo':'example/repo','state':'ok','runs':[]}) as fetch:
                m.snapshot([])
                m.snapshot([])
                self.assertEqual(fetch.call_count,1)

class HttpMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        cfg=pathlib.Path(self.tmp.name)/'config.json'
        cfg.write_text(json.dumps({}))
        self.server=BridgeServer(('127.0.0.1',0),BridgeState())
        self.server.monitor=Monitor(cfg,pathlib.Path(self.tmp.name)/'events.json')
        self.t=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.t.start()
        self.base='http://127.0.0.1:'+str(self.server.server_address[1])
        jar=http.cookiejar.CookieJar()
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.t.join(timeout=2);self.tmp.cleanup()

    def request(self,uri,obj=None):
        body=None if obj is None else json.dumps(obj).encode()
        headers={} if obj is None else {'X-Bridge-Request':'1','Content-Type':'application/json'}
        r=urllib.request.Request(self.base+uri,headers=headers,data=body)
        return self.client.open(r,timeout=5)

    def pair(self):
        with self.request('/api/pair',{'pin':self.server.state.pin}) as r:
            self.assertTrue(json.load(r)['paired'])

    def test_monitor_requires_session_and_exposes_no_unconfigured_secrets(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/api/monitor')
        self.assertEqual(e.exception.code,401)
        self.pair()
        with self.request('/api/monitor') as r:
            data=json.load(r)['data']
        self.assertFalse(data['github'])
        self.assertEqual(data['codex']['state'],'disabled')
        self.assertNotIn('session',json.dumps(data).lower())

    def test_monitor_html_and_event_mark_endpoint(self):
        with self.request('/monitor') as r:
            self.assertIn(b'PERSONAL HUB',r.read())
        self.pair()
        self.server.monitor.events.observe({'id':'x','level':'red','title':'测试','detail':'测试','source':'unit'})
        with self.request('/api/events') as r:
            self.assertFalse(json.load(r)['items'][0]['read'])
        with self.request('/api/events/read',{'ids':['x']}) as r:
            self.assertTrue(json.load(r)['ok'])
        with self.request('/api/events') as r:
            self.assertTrue(json.load(r)['items'][0]['read'])

if __name__ == '__main__':
    unittest.main()
