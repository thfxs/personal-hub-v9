#!/usr/bin/env python3
"""1.1 idempotency, TTL and local event security, including real HTTP calls."""
import http.cookiejar
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj

bridge = load('bridge11', ROOT/'bridge'/'server.py')
activity = load('activity11', ROOT/'bridge'/'activity.py')

class ReliabilityTests(unittest.TestCase):
    def test_queue_expiration_does_not_replay_stale_continue(self):
        st = bridge.BridgeState()
        queued = st.dispatch('127.0.0.1', '继续')
        st.queue[0]['_created_mono'] -= bridge.QUEUE_TTL+1
        self.assertEqual(st.queue_view(), [])
        st.arm()
        with self.assertRaisesRegex(ValueError, '不存在'):
            st.dispatch('127.0.0.1', '继续', queued['id'])

    def test_status_prunes_old_queue(self):
        st = bridge.BridgeState()
        st.dispatch('127.0.0.1', '继续')
        st.queue[0]['_created_mono'] -= bridge.QUEUE_TTL+1
        self.assertEqual(st.public_status(False)['queued'], 0)
        self.assertIn('expired', [a['result'] for a in st.audit])

    def test_request_id_returns_original_response_never_retypes(self):
        sent = []
        st = bridge.BridgeState(injector=lambda t: sent.append(t) or {'window':'ChatGPT', 'process':'TEST'})
        st.arm()
        first = st.dispatch('127.0.0.1', '下一步', request_id='unique-req-0001')
        second = st.dispatch('127.0.0.1', '下一步', request_id='unique-req-0001')
        self.assertEqual(first, second)
        self.assertEqual(first['result'], 'sent_unconfirmed')
        self.assertEqual(sent, ['下一步'])

    def test_request_id_cannot_reuse_for_other_text(self):
        st = bridge.BridgeState()
        st.dispatch('127.0.0.1', '继续', request_id='request-12345')
        with self.assertRaisesRegex(ValueError, '不同指令'):
            st.dispatch('127.0.0.1', '删除数据', request_id='request-12345')

    def test_replay_of_retry_does_not_send_twice(self):
        sent = []
        st = bridge.BridgeState(injector=lambda t: sent.append(t) or {'window':'ChatGPT', 'process':'TEST'})
        item = st.dispatch('127.0.0.1', '继续')
        st.arm()
        one = st.dispatch('127.0.0.1','继续',old_id=item['id'])
        two = st.dispatch('127.0.0.1','继续',old_id=item['id'])
        self.assertEqual(one, two)
        self.assertEqual(sent, ['继续'])

    def test_activity_validation_limits(self):
        for invalid in ('', 'x'*91, 'x\ny'):
            with self.assertRaises(ValueError):
                activity.validate(invalid, 'done')
        with self.assertRaises(ValueError):
            activity.validate('正常', 'imagined')

    def test_activity_manual_and_run_success_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            p = pathlib.Path(temp)/'log.jsonl'
            activity.append_event('人工标记','done',path=p)
            self.assertEqual(activity.main(['run','--task','脚本成功','--events-file',str(p),'--',sys.executable,'-c','pass']), 0)
            self.assertEqual(activity.main(['run','--task','脚本失败','--events-file',str(p),'--',sys.executable,'-c','import sys;sys.exit(9)']), 9)
            st = bridge.BridgeState(activity_file=p)
            events=st.read_activities()
            self.assertEqual(events[0]['state'],'failed')
            self.assertEqual(events[0]['task'],'脚本失败')
            self.assertIn('done',[e['state'] for e in events])
            self.assertNotIn('password',json.dumps(events))

    def test_activity_corruption_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            p=pathlib.Path(temp)/'events.jsonl'
            p.write_text('invalid\n'+json.dumps({'task':'hack','state':'imagined','id':'0','time':1})+'\n',encoding='utf8')
            st=bridge.BridgeState(activity_file=p)
            self.assertEqual(st.read_activities(),[])

    @unittest.skipUnless(hasattr(pathlib.Path, 'symlink_to'), 'symlinks unsupported')
    def test_activity_symlink_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            real=pathlib.Path(temp)/'real.jsonl'
            real.write_text('do not modify')
            link=pathlib.Path(temp)/'link.jsonl'
            try: link.symlink_to(real)
            except (OSError, NotImplementedError): self.skipTest('symlinks unavailable')
            with self.assertRaises(ValueError):
                activity.append_event('Task','done',path=link)
            self.assertEqual(bridge.BridgeState(activity_file=link).read_activities(), [])
            self.assertEqual(real.read_text(),'do not modify')

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        event_path = pathlib.Path(self.tmp.name)/'events.jsonl'
        activity.append_event('任务A', 'done', '退出码 0', event_path)
        self.sent = []
        self.st=bridge.BridgeState(injector=lambda t:self.sent.append(t) or {'window':'AI','process':'TEST'},activity_file=event_path)
        self.server=bridge.BridgeServer(('127.0.0.1',0),self.st)
        self.base='http://127.0.0.1:{}'.format(self.server.server_address[1])
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        jar=http.cookiejar.CookieJar()
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def call(self, path, data=None, auth=True):
        headers={}
        if data is not None:
            data=json.dumps(data).encode('utf-8')
            headers.update({'Content-Type':'application/json','X-Bridge-Request':'1'})
        req=urllib.request.Request(self.base+path,data=data,headers=headers)
        opener=self.client if auth else urllib.request.build_opener()
        try:
            response=opener.open(req,timeout=4)
            return response.status,json.loads(response.read())
        except urllib.error.HTTPError as e:
            return e.code,json.loads(e.read())

    def test_activity_endpoint_requires_pairing(self):
        code,_=self.call('/api/activity',auth=False)
        self.assertEqual(code,401)
        code,_=self.call('/api/pair',{'pin':self.st.pin})
        self.assertEqual(code,200)
        code,data=self.call('/api/activity')
        self.assertEqual(code,200)
        self.assertEqual(data['items'][0]['task'],'任务A')

    def test_duplicate_http_request_is_idempotent(self):
        self.call('/api/pair',{'pin':self.st.pin})
        self.call('/api/admin/arm',{})
        data={'preset':'continue','request_id':'mobile-command-0000001'}
        code,a=self.call('/api/dispatch',data)
        code,b=self.call('/api/dispatch',data)
        self.assertEqual(a,b)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(a['result'],'sent_unconfirmed')

if __name__=='__main__':
    unittest.main(verbosity=2)
