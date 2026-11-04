/* Manual, confirmed same-origin LAN synchronization. No background uploads. */
(function(){'use strict';
var M=window.PersonalHubSyncMerge,G=window.PersonalHubGuard,N=window.PersonalHubNativeTransport,$=function(id){return document.getElementById(id);};
var DB='personal_hub_v9',BASE='personal_hub_sync_base_v14',preview=null,busy=false,nativeConfig=null;
function isNative(){return !!(N&&N.available());}
function baseKey(){if(!isNative())return BASE;if(!nativeConfig||!nativeConfig.configured)throw Error('请先保存电脑证书配置');return BASE+'_native_'+nativeConfig.ip+'_'+nativeConfig.port+'_'+nativeConfig.fingerprint;}

function say(s){$('message').textContent=s;}
function id(){return 'phsync-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,13);}
function api(path,body){if(isNative()){return N.request(body===undefined?'GET':'POST',path,body).then(function(resp){if(resp.status>=400)throw Error((resp.body.error||'HTTP '+resp.status)+(resp.status===409?' [冲突]':''));return resp.body;});}var options={cache:'no-store',credentials:'same-origin'};if(body!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-Bridge-Request':'1'};options.body=JSON.stringify(body);}return fetch(path,options).then(function(resp){return resp.json().then(function(v){if(!resp.ok)throw Error((v.error||'HTTP '+resp.status)+(resp.status===409?' [冲突]':''));return v;});});}
function transactRead(db){return new Promise(function(resolve,reject){if(!db.objectStoreNames.contains('kv')){reject(Error('本地业务表尚未创建，请先打开主控'));return;}
 var tx=db.transaction('kv','readonly'),r=tx.objectStore('kv').get('main');r.onsuccess=function(){resolve(r.result&&r.result.value);};r.onerror=function(){reject(r.error||Error('数据库读取失败'));};});}
function openIDB(){return new Promise(function(resolve,reject){if(!window.indexedDB){reject(Error('无 IndexedDB'));return;}var req=indexedDB.open(DB,1);req.onsuccess=function(){resolve(req.result);};req.onerror=function(){reject(req.error||Error('无 IndexedDB'));};req.onblocked=function(){reject(Error('数据库被其他标签页锁定'));};});}
async function readLocal(){
 var db=null;try{db=await openIDB();}catch(e){/* Browser might be in localStorage fallback. */}
 if(db){try{
  if(db.objectStoreNames.contains('kv')){
   var data=await transactRead(db);
   if(data){M.validate(data);return {data:data,mode:'idb'};}
   // Existing database with no main record: do not load potentially stale localStorage.
   throw Error('IndexedDB 主记录不存在，请先打开主控并检查来源，不自动合并旧数据');
  }
 }finally{db.close();}}
 var raw=localStorage.getItem(DB);
 if(!raw)throw Error('当前网址没有业务记录：先打开同地址主控；从 GitHub Pages 迁移需先在此导入原备份');
 var doc=JSON.parse(raw);M.validate(doc);return {data:doc,mode:'localStorage'};
}
async function writeLocal(mode,expected,updated){M.validate(updated);if(mode==='localStorage'){
  var raw=localStorage.getItem(DB);if(!raw||!M.equal(JSON.parse(raw),expected))throw Error('本地数据已改变，请重新预览，未覆盖');
  localStorage.setItem(DB,JSON.stringify(updated));return;
 }
 var db=await openIDB();try{
  await new Promise(function(resolve,reject){var done=false,tx=db.transaction('kv','readwrite'),store=tx.objectStore('kv'),r=store.get('main'),reason='本地数据库写入失败';
   tx.oncomplete=function(){done=true;resolve();};tx.onabort=tx.onerror=function(){if(!done)reject(Error(reason));};
   r.onerror=function(){reason='本地读取失败';tx.abort();};
   r.onsuccess=function(){if(!r.result||!M.equal(r.result.value,expected)){reason='本地记录已被其他页面修改，未覆盖；请重新预览';tx.abort();return;}store.put({key:'main',value:updated});};
  });
 }finally{db.close();}}
function getBase(){var raw=localStorage.getItem(baseKey());if(!raw)return null;try{var b=JSON.parse(raw);M.validate(b.state);if(!Number.isInteger(b.revision)||b.revision<0)throw Error('版本号异常');return b;}catch(e){throw Error('本地同步基线异常，请勿继续写入；先导出原数据并检查存储。'+e.message);}}
function clear(){preview=null;$('statistics').textContent='';$('version').textContent='尚未读取';erase($('conflicts'));$('commit').disabled=true;$('commit').textContent='先预览，再确认提交';$('consent').checked=false;}
function erase(el){while(el.firstChild)el.removeChild(el.firstChild);}
function textNode(tag,t){var e=document.createElement(tag);e.textContent=t;return e;}
function renderConflicts(items){var host=$('conflicts');erase(host);if(items.length){host.appendChild(textNode('p','发现 '+items.length+' 处冲突。请选择每项处理方式，未选完不允许提交。'));}
 items.forEach(function(c){var panel=document.createElement('div');panel.className='conflict';panel.appendChild(textNode('strong',c.section+' · '+c.label));panel.appendChild(textNode('small','本机：'+(c.local?JSON.stringify(c.local).slice(0,180):'已删除')+'；电脑：'+(c.remote?JSON.stringify(c.remote).slice(0,180):'已删除')));
 var select=document.createElement('select');select.dataset.choice=c.key;[['','请选择（必选）'],['local','保留本机版本'],['remote','采用电脑版本']].forEach(function(p){var op=document.createElement('option');op.value=p[0];op.textContent=p[1];select.appendChild(op);});panel.appendChild(select);host.appendChild(panel);});}
function selectedChoices(){var choices={};document.querySelectorAll('select[data-choice]').forEach(function(el){if(el.value)choices[el.dataset.choice]=el.value;});return choices;}
async function status(){var result=await api('/api/status');$('pair').hidden=!!result.paired;$('connection').textContent=result.paired?'已连接到电脑桥；手动点击预览才会传输业务数据':'尚未配对，请输入电脑端显示的 8 位临时码。';return result;}
function ensureHub(){if(isNative())return;if(N&&N.isShell())throw Error('当前 Android 系统 WebView 不支持安全原生接口，请升级 WebView 后再使用同步。');if(!location.pathname.startsWith('/hub/')||(location.protocol!=='https:'&&!(['127.0.0.1','localhost'].includes(location.hostname))))throw Error('请打开电脑安全桥的 https://电脑IP:8765/hub/；必须信任正确的电脑证书。GitHub Pages 不能跨站访问该接口。');}
async function scan(){if(busy)return;busy=true;clear();try{ensureHub();var paired=await status();if(!paired.paired)throw Error('请先完成配对');
 var local=await readLocal(),r=await api('/api/sync'),base=getBase();if(base&&r.revision<base.revision)throw Error('电脑同步仓库疑似被重置：版本号回退，拒绝自动合并。');
 if(r.state!==null)M.validate(r.state);var merged=M.merge(local.data,r.state,base&&base.state||null);
 preview={local:local,remote:r,base:base};$('version').textContent='电脑版本 '+r.revision+' · 本机 '+local.mode;
 var qty=M.FIELDS.reduce(function(n,k){return n+merged.result[k].length;},0);
 $('statistics').textContent='预览：合并结果约 '+qty+' 条记录；相较本机变化 '+merged.localChanges+' 条；冲突 '+merged.conflicts.length+' 项。设置的冲突需人工确认。';renderConflicts(merged.conflicts);$('commit').disabled=false;$('commit').textContent='确认并执行同步';say('预览完成，尚未写入任何业务记录。');
 }catch(e){clear();say('预览失败：'+e.message);}finally{busy=false;}}
async function commit(){if(busy||!preview)return;if(!$('consent').checked){say('请先确认私人局域网传输风险并关闭其他编辑页面');return;}if(!window.confirm('将把合并结果保存到电脑和本机。此操作会合并/删除所选择的记录，请确认已备份。确定继续？'))return;
 busy=true;$('commit').disabled=true;var sent=false;
 try{var old=preview,choices=selectedChoices(),merged=M.merge(old.local.data,old.remote.state,old.base&&old.base.state||null,choices);
 if(merged.conflicts.length)throw Error('仍有 '+merged.conflicts.length+' 个冲突未指定处理方式');
 var latest=await readLocal();if(latest.mode!==old.local.mode||!M.equal(latest.data,old.local.data))throw Error('本机数据已变化，请重新预览；没有写入');
 var snapshot=await G.makeSnapshot('before-sync-14');say('本地恢复快照已保存：'+snapshot.id+'。正在提交电脑端版本…');
 var result=await api('/api/sync',{revision:old.remote.revision,state:merged.result,request_id:id()});sent=true;
 await writeLocal(old.local.mode,old.local.data,merged.result);
 var verified=await readLocal();if(!M.equal(verified.data,merged.result))throw Error('本地数据回读核对不一致');
 localStorage.setItem(baseKey(),JSON.stringify({revision:result.revision,state:merged.result}));
 say('同步成功！电脑版本 '+result.revision+'。本地快照 '+snapshot.id+' 已保留。请关闭当前页面并重新打开主控刷新数据。');clear();
 }catch(e){say((sent?'⚠ 电脑端可能已写入，但本机未完成；不要重试原操作，重新预览后处理。':'同步已停止，未提交新数据到电脑。')+'\n'+e.message);preview=null;}
 finally{busy=false;$('commit').disabled=true;}}
$('pairBtn').addEventListener('click',function(){var pin=$('pin').value.trim();if(!/^\d{8}$/.test(pin)){say('请填写 8 位配对码');return;}api('/api/pair',{pin:pin}).then(function(){$('pin').value='';return status();}).then(function(){say('配对成功。下一步请读取并预览差异。');}).catch(function(e){say('配对失败：'+e.message);});});
$('preview').addEventListener('click',scan);$('commit').addEventListener('click',commit);$('reset').addEventListener('click',function(){clear();say('本次预览已取消，未写入。');});
async function initNative(){
 if(!isNative())return;
 $('nativeConfig').hidden=false;
 async function refresh(){nativeConfig=await N.status();if(nativeConfig.configured){
  $('nativeIP').value=nativeConfig.ip;$('nativePort').value=String(nativeConfig.port);
  $('nativeFingerprint').value=nativeConfig.fingerprint;
  $('nativeMessage').textContent='已固定电脑地址和证书指纹。更换配置后，旧会话自动清除。';
 }else{$('nativeMessage').textContent='尚未配置电脑。先在电脑本机核对指纹；手机不进行自动信任。';}}
 $('nativeSave').addEventListener('click',async function(){try{
  var val=await N.configure($('nativeIP').value.trim(),$('nativePort').value.trim(),$('nativeFingerprint').value,$('nativeVerified').checked);
  nativeConfig=null;clear();await refresh();$('nativeVerified').checked=false;
  $('nativeMessage').textContent='指纹配置已保存，现在输入电脑端 8 位临时配对码。';
 }catch(e){$('nativeMessage').textContent='未保存：'+e.message;}});
 $('nativeForget').addEventListener('click',async function(){if(!confirm('确定清除电脑证书配置和配对吗？本机业务记录不会删除。'))return;
  try{await N.forget();nativeConfig=null;clear();await refresh();say('电脑配置已清除，当前业务数据保留。');}catch(e){say(e.message);}});
 try{await refresh();}catch(e){$('nativeMessage').textContent='原生证书配置读取失败：'+e.message;}
}
try{ensureHub();if(isNative())initNative().then(function(){status().catch(function(e){say('电脑桥尚未连通：'+e.message);});});else status().catch(function(e){say('电脑桥不可用：'+e.message);});}catch(e){$('connection').textContent=e.message;say(e.message);$('pairBtn').disabled=true;$('preview').disabled=true;}
})();
