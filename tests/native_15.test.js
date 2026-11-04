'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const nativePath=path.join(__dirname,'..','web','native-file.js');
const swipe=require('../web/swipe-nav.js');
function makeFiles(){
 const sent=[];const w={document:{},navigator:{userAgent:'Fake PersonalHubV9Shell/1.5'},PersonalHubNative:{postMessage(s){sent.push(JSON.parse(s));}}};
 global.window=w;delete require.cache[require.resolve(nativePath)];const files=require(nativePath);return {files,sent,w};
}
test('Web browser without native object correctly reports unavailable',()=>{const x=makeFiles();delete x.w.PersonalHubNative;assert.equal(x.files.isNative(),false);assert.equal(x.files.isShell(),true);delete global.window;});
test('reject JSON export with non-json name',async()=>{const x=makeFiles();await assert.rejects(x.files.saveJson('bad.txt','{}'));assert.equal(x.sent.length,0);delete global.window;});
test('reject malformed JSON before native picker is ever called',async()=>{const x=makeFiles();await assert.rejects(x.files.saveJson('backup.json','not json'));assert.equal(x.sent.length,0);delete global.window;});
test('native only resolves once file chooser reports success',async()=>{const x=makeFiles();let done=false;const p=x.files.saveJson('backup.json','{"ok":true}').then(()=>done=true);assert.equal(x.sent.length,1);assert.equal(x.sent[0].type,'save_json');assert.equal(done,false);x.w.PersonalHubNative.onmessage({data:JSON.stringify({id:x.sent[0].id,ok:true,message:'saved'})});await p;assert.equal(done,true);delete global.window;});
test('native cancellation rejects, does not show a fake saved status',async()=>{const x=makeFiles();const p=x.files.saveJson('backup.json','{}');x.w.PersonalHubNative.onmessage({data:JSON.stringify({id:x.sent[0].id,ok:false,message:'取消'})});await assert.rejects(p,/取消/);delete global.window;});
test('native messages cannot be resolved by an unknown reply id',async()=>{const x=makeFiles();const p=x.files.saveJson('backup.json','{}');x.w.PersonalHubNative.onmessage({data:JSON.stringify({id:'not-a-pending-id',ok:true})});x.w.PersonalHubNative.onmessage({data:JSON.stringify({id:x.sent[0].id,ok:true})});await p;delete global.window;});
test('native UI request persists only boolean device preferences',async()=>{const x=makeFiles();const p=x.files.devicePreferences(true,false);assert.equal(x.sent[0].type,'device_preferences');assert.equal(x.sent[0].immersive,true);assert.equal(x.sent[0].awake,false);x.w.PersonalHubNative.onmessage({data:JSON.stringify({id:x.sent[0].id,ok:true,data:{immersive:true,awake:false}})});assert.deepEqual(await p,{immersive:true,awake:false});delete global.window;});
test('landscape swipe follows existing nav order and stops at ends',()=>{assert.equal(swipe.targetPage('overview',-1),'tasks');assert.equal(swipe.targetPage('tasks',100),'overview');assert.equal(swipe.targetPage('settings',-1),null);assert.equal(swipe.targetPage('overview',1),null);});
test('swipe ignores editors, buttons, modal controls',()=>{assert.equal(swipe.shouldIgnore({closest:()=>({})}),true);assert.equal(swipe.shouldIgnore({closest:()=>null}),false);});
