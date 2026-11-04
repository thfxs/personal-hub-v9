'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const path=require('node:path'),fs=require('node:fs'),vm=require('node:vm');
const modulePath=path.join(__dirname,'../web/sync/native-transport.js');
const Transport=require(modulePath);
test('reject public and unsafe addresses, port, fingerprint',()=>{
 let f='AA'.repeat(32);
 assert.equal(Transport.checkConfig('192.168.1.7','8765',f).ip,'192.168.1.7');
 assert.equal(Transport.checkConfig('172.20.4.5','8765',f).port,8765);
 assert.throws(()=>Transport.checkConfig('8.8.8.8','8765',f));
 assert.throws(()=>Transport.checkConfig('127.0.0.1','8765',f));
 assert.throws(()=>Transport.checkConfig('192.168.2.500','8765',f));
 assert.throws(()=>Transport.checkConfig('192.168.2.1','80',f));
 assert.throws(()=>Transport.checkConfig('192.168.2.1','8765','AABB'));
});
test('disabled on ordinary browser',async()=>{
 assert.equal(Transport.available(),false);
 await assert.rejects(Transport.request('GET','/api/status'),/Android APK|安卓 WebView/);
});
test('native only replies to matching request ids and never sends cookies',async()=>{
 const outbound=[];
 const window={document:{},navigator:{userAgent:'PersonalHubV9Shell/1.7'},
  PersonalHubNative:{onmessage:null,postMessage(s){outbound.push(JSON.parse(s));}}};
 const ctx={window,module:{exports:{}},setTimeout,clearTimeout};
 vm.runInNewContext(fs.readFileSync(modulePath,'utf8'),ctx);
 const T=ctx.module.exports;
 assert.equal(T.available(),true);
 const q=T.configure('192.168.10.6','8765','BB'.repeat(32),true);
 assert.equal(outbound.length,1);
 assert.equal(outbound[0].type,'bridge_config');
 window.PersonalHubNative.onmessage({data:JSON.stringify({id:'someone-else',ok:true})});
 window.PersonalHubNative.onmessage({data:JSON.stringify({id:outbound[0].id,ok:true,data:{}})});
 await q;
 const p=T.request('GET','/api/status');
 assert.equal(outbound[1].path,'/api/status');
 assert.equal(JSON.stringify(outbound).includes('Cookie'),false);
 window.PersonalHubNative.onmessage({data:JSON.stringify({id:outbound[1].id,ok:true,data:{status:200,body:{paired:true}}})});
 const r=await p;assert.equal(r.body.paired,true);
});
test('explicit fingerprint acknowledgement required',async()=>{
 await assert.rejects(Transport.configure('192.168.0.1','8765','AB'.repeat(32),false),/必须先/);
});
