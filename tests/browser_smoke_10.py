#!/usr/bin/env python3
"""Actual Chromium UI smoke test. No physical V9 or keyboard automation."""
import http.server
import importlib.util
import pathlib
import socketserver
import sys
import threading
from functools import partial

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('personal_bridge', ROOT / 'bridge' / 'server.py')
bridge = importlib.util.module_from_spec(spec)
sys.modules['personal_bridge'] = bridge
spec.loader.exec_module(bridge)


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('NOT RUN: playwright not installed')
        return 3
    sent = []
    st = bridge.BridgeState(injector=lambda t: sent.append(t) or {'process': 'Chrome', 'window': 'ChatGPT'})
    server = bridge.BridgeServer(('127.0.0.1', 0), st)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    diag_handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / 'diag'))
    diag_server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), diag_handler)
    diag_server_thread = threading.Thread(target=diag_server.serve_forever, daemon=True)
    diag_server_thread.start()
    checks = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path='/usr/bin/chromium',
                                        args=['--no-sandbox', '--disable-dev-shm-usage'])
            context = browser.new_context(viewport={'width': 412, 'height': 915}, locale='zh-CN')
            page = context.new_page()
            root = 'http://127.0.0.1:{}'.format(server.server_port)
            page.goto(root, wait_until='load', timeout=15000)
            page.locator('#pair').wait_for(state='visible')
            page.locator('#pin').fill(st.pin)
            page.locator('#pairButton').click()
            page.locator('#connected').wait_for(state='visible')
            checks.append('手机端配对、快捷键页面：PASS')
            page.get_by_role('button', name='继续', exact=True).click()
            page.locator('.queue-item').first.wait_for()
            checks.append('未授权时进入待发队列：PASS')
            pc = context.new_page()
            pc.goto(root + '/pc', wait_until='load', timeout=15000)
            pc.locator('#connected').wait_for(state='visible')
            pc.locator('#arm').click()
            pc.locator('#status').filter(has_text='已授权').wait_for(timeout=5000)
            page.get_by_role('button', name='重试发送', exact=True).first.click()
            page.locator('#message').filter(has_text='已尝试注入').wait_for(timeout=5000)
            assert sent == ['继续。'], sent
            checks.append('电脑授权后手机重发/模拟 AI 接收：PASS')
            pc.locator('#disarm').click()
            pc.locator('#status').filter(has_text='待发模式').wait_for(timeout=5000)
            checks.append('电脑取消授权：PASS')
            diag = context.new_page()
            diag.goto('http://127.0.0.1:{}/v9-check.html'.format(diag_server.server_port), wait_until='load', timeout=15000)
            diag.locator('#write').click()
            diag.locator('#writeResult').filter(has_text='已写入').wait_for(timeout=5000)
            diag.reload(wait_until='load')
            diag.locator('#read').click()
            diag.locator('#readResult').filter(has_text='存在').wait_for(timeout=5000)
            checks.append('诊断页 IndexedDB/localStorage 写入→刷新→读取：PASS')
            browser.close()
    except Exception as e:
        print('浏览器烟雾测试未通过：', str(e)[:1000])
        for c in checks:
            print(c)
        return 1
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
        diag_server.shutdown(); diag_server.server_close(); diag_server_thread.join(timeout=2)
    for c in checks:
        print(c)
    print('PASS: 真实 Chromium UI 烟雾测试全部通过（不代表 V9 真机已通过）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
