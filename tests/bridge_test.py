#!/usr/bin/env python3
"""stdlib local HTTP end-to-end tests; never touch the actual keyboard."""
import contextlib
import http.cookiejar
import importlib.util
import io
import json
import pathlib
import sys
import threading
import unittest
import urllib.error
import urllib.request

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phbridge', BASE_DIR / 'bridge' / 'server.py')
bridge = importlib.util.module_from_spec(spec)
sys.modules['phbridge'] = bridge
spec.loader.exec_module(bridge)


class CoreTests(unittest.TestCase):
    def test_presets_have_only_normal_text(self):
        for value in bridge.PRESETS.values():
            self.assertEqual(value, bridge.safe_text(value))

    def test_empty_newline_and_long_text_rejected(self):
        for t in ['', '\n', 'hello\rworld', 'hi\tthere', 'x' * 181, '\0']:
            with self.subTest(t=repr(t)), self.assertRaises(ValueError):
                bridge.safe_text(t)

    def test_foreground_validation_requires_title_and_process(self):
        self.assertTrue(bridge.permitted_window((100, 'chrome.exe', 'ChatGPT - Chrome')))
        self.assertTrue(bridge.permitted_window((10, 'ChatGPT', 'ChatGPT')))
        self.assertFalse(bridge.permitted_window((100, 'chrome.exe', '网上银行 - Chrome')))
        self.assertFalse(bridge.permitted_window((100, 'powershell.exe', 'ChatGPT')))
        self.assertFalse(bridge.permitted_window((100, 'code.exe', 'README.md - Visual Studio Code')))

    def test_queue_default_arm_and_retry(self):
        sent = []
        st = bridge.BridgeState(injector=lambda t: sent.append(t) or {'process': 'TEST', 'window': 'ChatGPT'})
        r = st.dispatch('127.0.0.1', '继续')
        self.assertEqual(r['result'], 'queued')
        self.assertEqual(sent, [])
        st.arm()
        r2 = st.dispatch('127.0.0.1', '继续', r['id'])
        self.assertEqual(r2['result'], 'sent_unconfirmed')
        self.assertEqual(sent, ['继续'])
        self.assertFalse(st.queue_view())
        st.disarm()
        self.assertFalse(st.armed())

    def test_failed_foreground_enters_queue(self):
        def refuse(_):
            raise RuntimeError('不是 ChatGPT 窗口')
        st = bridge.BridgeState(injector=refuse)
        st.arm()
        r = st.dispatch('127.0.0.1', '继续')
        self.assertEqual(r['result'], 'queued')
        self.assertEqual(len(st.queue_view()), 1)

    def test_duplicate_taps_ignored(self):
        st = bridge.BridgeState()
        self.assertEqual(st.dispatch('127.0.0.1', '继续')['result'], 'queued')
        self.assertEqual(st.dispatch('127.0.0.1', '继续')['result'], 'duplicate_skipped')

    def test_lockout_after_failed_pins(self):
        st = bridge.BridgeState()
        wrong = '00000000' if st.pin != '00000000' else '99999999'
        for _ in range(5):
            _, error = st.pair('192.168.1.2', wrong)
            self.assertIn('错误', error)
        key, error = st.pair('192.168.1.2', st.pin)
        self.assertIsNone(key)
        self.assertIn('过多', error)
        other, error = st.pair('192.168.1.3', st.pin)
        self.assertIsNotNone(other)
        self.assertTrue(st.valid(other))

    def test_per_ip_rate_limit(self):
        st = bridge.BridgeState()
        for i in range(12):
            st.dispatch('192.168.1.50', '指令 {}'.format(i))
        with self.assertRaisesRegex(ValueError, '频繁'):
            st.dispatch('192.168.1.50', '第十三条')


class LocalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sent = []
        cls.state = bridge.BridgeState(injector=lambda t: cls.sent.append(t) or {'process': 'TEST', 'window': 'ChatGPT'})
        cls.server = bridge.BridgeServer(('127.0.0.1', 0), cls.state)
        cls.port = cls.server.server_address[1]
        cls.base = 'http://127.0.0.1:{}'.format(cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.cookies = http.cookiejar.CookieJar()
        cls.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cls.cookies))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def call(self, path, data=None, extra_headers=None, opener=None):
        req_headers = dict(extra_headers or {})
        if data is not None:
            req_headers.setdefault('Content-Type', 'application/json')
            req_headers.setdefault('X-Bridge-Request', '1')
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(self.base + path, data=data, headers=req_headers)
        try:
            resp = (opener or self.opener).open(req, timeout=4)
            return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read()

    def pair(self):
        status, headers, content = self.call('/api/pair', {'pin': self.state.pin})
        self.assertEqual(status, 200, content)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])

    def test_01_unauthenticated_status_does_not_leak(self):
        status, _, data = self.call('/api/status', opener=urllib.request.build_opener())
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(data)['paired'])
        self.assertNotIn(self.state.pin.encode(), data)

    def test_02_pair_and_credentials(self):
        self.pair()
        status, _, data = self.call('/api/status')
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)['paired'])

    def test_03_frontpage_and_csp(self):
        for path in ('/', '/pc', '/ui.js', '/ui.css'):
            status, headers, content = self.call(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(content)
            self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
            self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_04_cross_site_origin_rejected(self):
        self.pair()
        status, _, content = self.call('/api/dispatch', {'preset': 'continue'},
                                       {'Origin': 'https://evil.example'})
        self.assertEqual(status, 403, content)

    def test_05_no_custom_request_header_rejected(self):
        self.pair()
        status, _, _ = self.call('/api/dispatch', {'preset': 'continue'}, {'X-Bridge-Request': '0'})
        self.assertEqual(status, 403)

    def test_06_untrusted_host_rejected(self):
        self.pair()
        status, _, _ = self.call('/api/status', extra_headers={'Host': 'example.com'})
        self.assertEqual(status, 403)

    def test_07_unknown_preset_rejected(self):
        self.pair()
        status, _, _ = self.call('/api/dispatch', {'preset': 'rm -rf /'})
        self.assertEqual(status, 400)

    def test_08_queue_then_local_arm_and_retry(self):
        self.pair()
        self.call('/api/admin/disarm', {})
        status, _, payload = self.call('/api/dispatch', {'text': '下一步（测试用）'})
        self.assertEqual(status, 200)
        result = json.loads(payload)
        self.assertEqual(result['result'], 'queued')
        status, _, _ = self.call('/api/admin/arm', {})
        self.assertEqual(status, 200)
        status, _, payload = self.call('/api/queue/retry', {'id': result['id']})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)['result'], 'sent_unconfirmed')
        self.assertIn('下一步（测试用）', self.sent)
        self.call('/api/admin/disarm', {})

    def test_09_invalid_multiline_rejected(self):
        self.pair()
        status, _, payload = self.call('/api/dispatch', {'text': 'hello\nworld'})
        self.assertEqual(status, 400)
        self.assertIn('控制字符'.encode('utf-8'), payload)

    def test_10_excessive_payload_rejected(self):
        self.pair()
        status, _, _ = self.call('/api/dispatch', {'text': 'x' * 5000})
        self.assertEqual(status, 413)

    def test_11_server_not_file_browser(self):
        status, _, _ = self.call('/../../etc/passwd')
        self.assertEqual(status, 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
