/* Personal Hub 0.9: additive, offline data guard. No external calls, no app DB migration. */
(function(root,factory){
  var api=factory();
  if(typeof module==='object' && module.exports)module.exports=api;
  if(root)root.PersonalHubGuard=api;
})(typeof window!=='undefined'?window:typeof globalThis!=='undefined'?globalThis:null,function(){
'use strict';
var APP_DB='personal_hub_v9', GUARD_DB='personal_hub_guard_v09';
var BACKUP_KIND='personal-hub-guard-backup', SNAP_KIND='personal-hub-guard-snapshot';
var MAX_FILE=15*1024*1024, MAX_SNAPSHOTS=12, RETENTION_MS=30*60*1000;
function fail(msg){throw new Error(msg);}
function crc32(s){
 var n=0xffffffff;
 for(var i=0;i<s.length;i++){
  var c=s.charCodeAt(i);
  /* checksum the UTF-8 bytes, not UTF-16 code units */
  if(c>=0xd800&&c<=0xdbff && i+1<s.length){var x=s.charCodeAt(++i);c=0x10000+((c-0xd800)<<10)+(x-0xdc00);}
  var a=c<0x80?[c]:c<0x800?[0xc0|(c>>6),0x80|(c&63)]:c<0x10000?[0xe0|(c>>12),0x80|((c>>6)&63),0x80|(c&63)]:[0xf0|(c>>18),0x80|((c>>12)&63),0x80|((c>>6)&63),0x80|(c&63)];
  for(var j=0;j<a.length;j++){n^=a[j];for(var k=0;k<8;k++)n=(n>>>1)^((n&1)?0xedb88320:0);}
 }
 return ('00000000'+((n^0xffffffff)>>>0).toString(16)).slice(-8);
}
function isPlain(v){if(!v||typeof v!=='object')return false;var p=Object.getPrototypeOf(v);return p===Object.prototype||p===null;}
function safeJSON(v,depth,seen){
 depth=depth||0;seen=seen||[];if(depth>60)fail('存在过深的数据嵌套，已停止备份');
 if(v===null||typeof v==='string'||typeof v==='boolean')return;
 if(typeof v==='number'){if(!isFinite(v))fail('记录包含非有限数字，已停止备份');return;}
 if(typeof v==='undefined'||typeof v==='bigint'||typeof v==='function'||typeof v==='symbol')fail('记录包含无法安全转成 JSON 的数据');
 if(!Array.isArray(v)&&!isPlain(v))fail('记录包含非 JSON 类型，不能无损备份');
 if(seen.indexOf(v)!==-1)fail('记录包含循环引用，不能无损备份');
 seen.push(v);
 if(Array.isArray(v)){for(var i=0;i<v.length;i++){if(!Object.prototype.hasOwnProperty.call(v,i))fail('记录数组包含空洞，不能无损备份');safeJSON(v[i],depth+1,seen);}}
 else Object.keys(v).forEach(function(k){safeJSON(v[k],depth+1,seen);});
 seen.pop();
}
function req(request){return new Promise(function(resolve,reject){request.onsuccess=function(){resolve(request.result);};request.onerror=function(){reject(request.error||new Error('IndexedDB 请求失败'));};});}
function txnDone(tx){return new Promise(function(resolve,reject){tx.oncomplete=function(){resolve();};tx.onabort=tx.onerror=function(){reject(tx.error||new Error('存储事务失败'));};});}
function openDB(name,version,onUpgrade,requireExisting){return new Promise(function(resolve,reject){
 if(typeof indexedDB==='undefined'){reject(new Error('当前浏览器不支持 IndexedDB'));return;}
 var r=version?indexedDB.open(name,version):indexedDB.open(name);
 var missing=false;
 r.onupgradeneeded=function(){if(requireExisting){missing=true;r.transaction.abort();return;}if(onUpgrade)onUpgrade(r.result,r.transaction);};
 r.onsuccess=function(){resolve(r.result);};r.onerror=function(){reject(missing?new Error('应用数据库尚不存在，已取消新建以保护旧版迁移'):r.error||new Error('无法打开数据库 '+name));};
 r.onblocked=function(){reject(new Error('数据库被另一页面占用，请先关闭其他 Personal Hub 页面'));};
 });}
function openGuard(){return openDB(GUARD_DB,1,function(db){
 if(!db.objectStoreNames.contains('snapshots'))db.createObjectStore('snapshots',{keyPath:'id'});
 if(!db.objectStoreNames.contains('meta'))db.createObjectStore('meta',{keyPath:'key'});
});}
async function metaGet(k){var db=await openGuard();try{var t=db.transaction('meta','readonly');var p=req(t.objectStore('meta').get(k));var out=await p;return out?out.value:null;}finally{db.close();}}
async function metaPut(k,value){var db=await openGuard();try{var t=db.transaction('meta','readwrite');var done=txnDone(t);t.objectStore('meta').put({key:k,value:value});await done;}finally{db.close();}}
function enumerateStore(store){return new Promise(function(resolve,reject){
 var rows=[],r=store.openCursor();r.onsuccess=function(){var c=r.result;if(!c){resolve(rows);return;}
 try{safeJSON(c.key);safeJSON(c.value);rows.push({key:c.key,value:c.value});c.continue();}catch(e){reject(e);}};
 r.onerror=function(){reject(r.error||new Error('读取记录失败'));};
});}
async function readApp(){
 var db=await openDB(APP_DB,null,null,true);var stores=[];
 try{
  var names=Array.prototype.slice.call(db.objectStoreNames);
  if(names.length){var t=db.transaction(names,'readonly'),jobs=names.map(function(name){var s=t.objectStore(name);return enumerateStore(s).then(function(rows){return{name:name,keyPath:s.keyPath,autoIncrement:s.autoIncrement,rows:rows};});});stores=await Promise.all(jobs);}
 }finally{db.close();}
 var ls=null;
 try{ls=localStorage.getItem(APP_DB);}catch(e){/* Storage might be disabled, IndexedDB still works */}
 if(!stores.some(function(s){return s.rows.length;}) && !ls)fail('未检测到 Personal Hub 已保存的数据；不会为一个空数据库制作虚假备份');
 var result={dbName:APP_DB,stores:stores,localStorageValue:ls};safeJSON(result);return result;
}
function wrapSnapshot(payload,reason){
 if(!payload||payload.dbName!==APP_DB||!Array.isArray(payload.stores))fail('不是当前 Personal Hub 数据结构');
 safeJSON(payload);
 var raw=JSON.stringify(payload);
 if(raw.length>MAX_FILE)fail('数据超过 15MB 的保护上限');
 return{kind:SNAP_KIND,id:new Date().toISOString()+'-'+Math.random().toString(36).slice(2,9),at:new Date().toISOString(),reason:reason||'manual',crc32:crc32(raw),payload:JSON.parse(raw)};
}
function validateSnapshot(snapshot){
 if(!snapshot||snapshot.kind!==SNAP_KIND||!snapshot.payload||typeof snapshot.at!=='string'||typeof snapshot.id!=='string'||typeof snapshot.crc32!=='string')fail('不是有效的 Personal Hub 保护快照');
 if(snapshot.payload.dbName!==APP_DB||!Array.isArray(snapshot.payload.stores))fail('数据库标识不匹配');
 if(snapshot.payload.localStorageValue!==null&&typeof snapshot.payload.localStorageValue!=='string')fail('localStorage 数据异常');
 if(snapshot.payload.stores.length>32)fail('数据表数量异常');
 var names=Object.create(null);snapshot.payload.stores.forEach(function(s){
  if(!s||typeof s.name!=='string'||!s.name||names[s.name]||!Array.isArray(s.rows)||s.rows.length>200000)fail('快照数据表格式错误');names[s.name]=true;
  s.rows.forEach(function(r){if(!r||!Object.prototype.hasOwnProperty.call(r,'key')||!Object.prototype.hasOwnProperty.call(r,'value'))fail('快照记录格式错误');});
 });
 safeJSON(snapshot.payload);
 if(crc32(JSON.stringify(snapshot.payload))!==snapshot.crc32)fail('数据校验失败：备份文件可能已损坏');
 return snapshot;
}
async function listSnapshots(){var db=await openGuard();try{var t=db.transaction('snapshots','readonly');var arr=await enumerateStore(t.objectStore('snapshots'));return arr.map(function(x){return x.value;}).sort(function(a,b){return b.at.localeCompare(a.at);});}finally{db.close();}}
async function saveSnapshot(snapshot){validateSnapshot(snapshot);var db=await openGuard();try{
 var t=db.transaction('snapshots','readwrite');var done=txnDone(t);t.objectStore('snapshots').put(snapshot);await done;
 var all=await listSnapshots();var old=all.slice(MAX_SNAPSHOTS);
 if(old.length){var t2=db.transaction('snapshots','readwrite'),done2=txnDone(t2);old.forEach(function(s){t2.objectStore('snapshots').delete(s.id);});await done2;}
 return snapshot;
}finally{db.close();}}
async function makeSnapshot(reason){var snapshot=wrapSnapshot(await readApp(),reason);return saveSnapshot(snapshot);}
async function autoSnapshot(){
 var last=await metaGet('lastAuto');if(last&&Date.now()-Date.parse(last.at)<RETENTION_MS)return{status:'skipped-recent'};
 var payload;try{payload=await readApp();}catch(e){return{status:'skipped-empty',detail:e.message};}
 var crc=crc32(JSON.stringify(payload));
 if(last&&last.crc32===crc){await metaPut('lastAuto',{at:new Date().toISOString(),crc32:crc});return{status:'skipped-unchanged'};}
 var snapshot=await saveSnapshot(wrapSnapshot(payload,'auto'));
 await metaPut('lastAuto',{at:snapshot.at,crc32:crc});return{status:'saved',id:snapshot.id};
}
async function latest(){var arr=await listSnapshots();return arr.length?arr[0]:null;}
async function restoreSnapshot(snapshot){
 validateSnapshot(snapshot);
 /* Take a recoverable snapshot of the pre-restore data. Never replace the app before this succeeds. */
 var before=await makeSnapshot('before-restore');var payload=snapshot.payload;
 var db=await openDB(APP_DB,null,null,true);
 try{
  var names=payload.stores.map(function(s){return s.name;});
  for(var i=0;i<names.length;i++)if(!db.objectStoreNames.contains(names[i]))fail('当前应用缺少数据表 '+names[i]+'；拒绝执行会丢数据的跨版本恢复');
  if(names.length){
   /* One transaction for all included stores. Store schemas/keyPaths must match. */
   var tx=db.transaction(names,'readwrite');var done=txnDone(tx);
   for(var j=0;j<payload.stores.length;j++){
    var src=payload.stores[j],store=tx.objectStore(src.name);
    if(JSON.stringify(store.keyPath)!==JSON.stringify(src.keyPath)||store.autoIncrement!==src.autoIncrement){tx.abort();fail('数据表 '+src.name+' 的结构已经变化，拒绝跨版本覆盖');}
    store.clear();
    src.rows.forEach(function(r){if(store.keyPath===null)store.put(r.value,r.key);else store.put(r.value);});
   }
   await done;
  }
  if(payload.localStorageValue!==null){try{localStorage.setItem(APP_DB,payload.localStorageValue);}catch(e){fail('主数据库已恢复，但 localStorage 写入失败。恢复前状态保留在快照 '+before.id+'；请不要继续修改数据');}}
 }finally{db.close();}
 var after=await readApp();
 payload.stores.forEach(function(original){
  var present=after.stores.filter(function(x){return x.name===original.name;})[0];
  if(!present||JSON.stringify(present.rows)!==JSON.stringify(original.rows))fail('恢复后的 '+original.name+' 记录未通过逐条核对；恢复前快照为 '+before.id);
 });
 if(payload.localStorageValue!==null&&after.localStorageValue!==payload.localStorageValue)fail('localStorage 恢复校验失败；恢复前快照为 '+before.id);
 return{beforeId:before.id,verified:true};
}
function b64(buf){var a=new Uint8Array(buf),s='';for(var i=0;i<a.length;i++)s+=String.fromCharCode(a[i]);return btoa(s);}
function unb64(s){var z=atob(s),a=new Uint8Array(z.length);for(var i=0;i<z.length;i++)a[i]=z.charCodeAt(i);return a;}
function cryptoReady(){return typeof crypto!=='undefined'&&crypto.subtle&&crypto.getRandomValues&&typeof TextEncoder!=='undefined'&&typeof TextDecoder!=='undefined';}
async function encrypt(json,pass){
 if(!cryptoReady())fail('此设备浏览器未提供安全加密接口；请使用明文导出并妥善保存，或换可信电脑加密');
 if(typeof pass!=='string'||pass.length<12)fail('加密密码至少 12 个字符');
 var salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12)),te=new TextEncoder();
 var base=await crypto.subtle.importKey('raw',te.encode(pass),'PBKDF2',false,['deriveKey']);
 var key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:salt,iterations:210000,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['encrypt']);
 var ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv:iv},key,te.encode(json));
 return JSON.stringify({kind:BACKUP_KIND,format:2,cipher:'AES-256-GCM',kdf:'PBKDF2-SHA256',iterations:210000,salt:b64(salt),iv:b64(iv),data:b64(ciphertext)});
}
async function decrypt(envelope,pass){
 if(!cryptoReady())fail('当前浏览器不支持解密；请使用支持 Web Crypto 的浏览器');
 if(envelope.cipher!=='AES-256-GCM'||envelope.kdf!=='PBKDF2-SHA256'||envelope.iterations!==210000)fail('不支持的加密算法或迭代次数');
 if(typeof envelope.salt!=='string'||typeof envelope.iv!=='string'||typeof envelope.data!=='string')fail('加密文件字段缺失');
 var salt=unb64(envelope.salt),iv=unb64(envelope.iv),data=unb64(envelope.data);
 if(salt.length!==16||iv.length!==12||data.length>MAX_FILE)fail('加密文件大小或参数异常');
 var te=new TextEncoder(),base=await crypto.subtle.importKey('raw',te.encode(pass),'PBKDF2',false,['deriveKey']);
 var key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:salt,iterations:210000,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['decrypt']);
 try{return new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:iv},key,data));}catch(e){fail('无法解密：密码不正确，或备份文件已损坏');}
}
async function exportSnapshot(snapshot,pass){
 validateSnapshot(snapshot);var json=JSON.stringify({kind:BACKUP_KIND,format:1,snapshot:snapshot});
 return pass?encrypt(json,pass):json;
}
async function importSnapshot(json,pass){
 if(typeof json!=='string'||json.length>MAX_FILE)fail('备份文件不是有效文本，或超过 15MB');
 var envelope=JSON.parse(json);
 if(!envelope||envelope.kind!==BACKUP_KIND)fail('不是 Personal Hub 0.9 数据保护文件');
 if(envelope.format===2)envelope=JSON.parse(await decrypt(envelope,pass||''));
 if(envelope.format!==1||!envelope.snapshot)fail('不支持的备份版本');
 return validateSnapshot(envelope.snapshot);
}
async function exportConfirmed(){return metaPut('externalExportConfirmedAt',new Date().toISOString());}
async function backupStatus(){
 var last=await metaGet('externalExportConfirmedAt'),age=last?Date.now()-Date.parse(last):Infinity;
 return{lastConfirmedAt:last||null,reminder:age>7*24*3600*1000,localSnapshots:(await listSnapshots()).length};
}
return{APP_DB:APP_DB,GUARD_DB:GUARD_DB,crc32:crc32,safeJSON:safeJSON,wrapSnapshot:wrapSnapshot,validateSnapshot:validateSnapshot,readApp:readApp,makeSnapshot:makeSnapshot,autoSnapshot:autoSnapshot,listSnapshots:listSnapshots,latest:latest,restoreSnapshot:restoreSnapshot,exportSnapshot:exportSnapshot,importSnapshot:importSnapshot,exportConfirmed:exportConfirmed,backupStatus:backupStatus,cryptoReady:cryptoReady};
});
