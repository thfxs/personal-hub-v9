#!/usr/bin/env python3
"""Optional real Chromium integration: two isolated browser storage profiles, one LAN bridge."""
import os
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
from server import BridgeState, BridgeServer
from sync_store import SyncStore

EDIT = '''async (values) => {
 const db=await new Promise((ok,bad)=>{const r=indexedDB.open('personal_hub_v9',1);r.onsuccess=()=>ok(r.result);r.onerror=()=>bad(r.error)});
 try {await new Promise((ok,bad)=>{const tx=db.transaction('kv','readwrite');const store=tx.objectStore('kv');const r=store.get('main');r.onsuccess=()=>{const s=r.result.value; if(values.kind==='add'){s.tasks.push({id:values.id,title:values.title,status:'todo',createdAt:new Date().toISOString()});}else{const item=s.tasks.find(x=>x.id===values.id);if(!item){tx.abort();return;}item.title=values.title;}s.updatedAt=new Date().toISOString();store.put({key:'main',value:s});};r.onerror=()=>bad(r.error);tx.oncomplete=ok;tx.onerror=()=>bad(tx.error);tx.onabort=()=>bad(Error('aborted'));});}
 finally {db.close();}
}'''


def run():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('[SKIP] Playwright not available');return 0
    with tempfile.TemporaryDirectory() as tmp:
        st=BridgeState(injector=lambda s: {'mock':'yes'})
        server=BridgeServer(('127.0.0.1',0),st)
        server.sync_store=SyncStore(Path(tmp)/'sync.json')
        thr=threading.Thread(target=server.serve_forever,daemon=True);thr.start()
        base=f'http://127.0.0.1:{server.server_address[1]}'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
                a,b=browser.new_context(),browser.new_context()
                pa,pb=a.new_page(),b.new_page()
                for page in (pa,pb):
                    page.on('dialog',lambda dialog:dialog.accept())
                    page.goto(base+'/hub/',wait_until='load',timeout=12000)
                    page.wait_for_function("document.getElementById('storage-label').textContent !== '正在检查本地存储'",timeout=8000)
                    page.goto(base+'/hub/sync/index.html',wait_until='load',timeout=12000)
                    page.locator('#pin').fill(st.pin)
                    page.locator('#pairBtn').click()
                    page.wait_for_function("document.getElementById('connection').textContent.includes('已连接')",timeout=6000)
                def sync(page):
                    page.locator('#preview').click()
                    page.wait_for_function("document.getElementById('message').textContent.includes('预览完成')",timeout=12000)
                    choices=page.locator('select[data-choice]')
                    for i in range(choices.count()):choices.nth(i).select_option('local')
                    page.locator('#consent').check()
                    page.locator('#commit').click()
                    page.wait_for_function("document.getElementById('message').textContent.includes('同步成功')",timeout=15000)
                sync(pa);sync(pb)
                pa.evaluate(EDIT,{'kind':'add','id':'from-a','title':'在电脑上修改'})
                pb.evaluate(EDIT,{'kind':'add','id':'from-b','title':'在手机上修改'})
                sync(pa);sync(pb)
                snap=server.sync_store.snapshot()['state']
                assert {'from-a','from-b'}.issubset({x['id'] for x in snap['tasks']}),snap
                # Actual browser merge conflict when both devices edit same known record.
                sync(pa)  # fetch remote B's updated state
                pa.evaluate(EDIT,{'kind':'edit','id':'from-a','title':'设备A更改'})
                pb.evaluate(EDIT,{'kind':'edit','id':'from-a','title':'设备B更改'})
                sync(pa)
                pb.locator('#preview').click()
                pb.wait_for_function("document.querySelector('select[data-choice]') !== null",timeout=12000)
                assert pb.locator('select[data-choice="tasks:from-a"]').count()==1
                print('[PASS] Browser: two separate profiles paired, independent edits merged, concurrent edits blocked for manual choice')
                browser.close()
        finally:
            server.shutdown();server.server_close();thr.join()
    return 0


if __name__=='__main__':
    try:sys.exit(run())
    except Exception as exc:
        print('[BROWSER NOT PASSED]',type(exc).__name__,str(exc)[:500]);sys.exit(2)
