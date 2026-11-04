(function(){
'use strict';
var G=window.PersonalHubGuard,selected=null,verified=null;
var $=function(id){return document.getElementById(id);};
function notice(msg,type){$('message').textContent=msg;$('message').className='message'+(type?' '+type:'');}
function localTime(s){try{return new Date(s).toLocaleString('zh-CN',{hour12:false});}catch(e){return s;}}
function snapshotSummary(s){var counts=s.payload.stores.map(function(x){return x.name+': '+x.rows.length;}).join('，');return counts||'仅有 localStorage 数据';}
async function refresh(){
 var list=await G.listSnapshots(),status=await G.backupStatus(),area=$('snapshots');area.textContent='';
 $('stats').children[0].querySelector('strong').textContent=list.length+' / 12';
 $('stats').children[1].querySelector('strong').textContent=status.lastConfirmedAt?localTime(status.lastConfirmedAt):'尚未确认';
 $('stats').children[2].querySelector('strong').textContent=G.cryptoReady()?'可用 · AES-256':'不可用 · 需明文';
 if(status.reminder)notice('尚无最近 7 天已确认的外部备份；请尽快保存到电脑或其他位置。','warn');
 if(!list.length){var empty=document.createElement('p');empty.textContent='暂无本地快照。';area.appendChild(empty);return;}
 list.forEach(function(s){
  var row=document.createElement('div');row.className='snapshot';var label=document.createElement('span');label.className='meta';label.textContent=localTime(s.at)+' · '+s.reason+' · '+snapshotSummary(s);
  var btn=document.createElement('button');btn.textContent='选中导出';btn.addEventListener('click',function(){selected=s;notice('已选择 '+localTime(s.at)+' 的快照；可点击“导出最新快照”导出该份。');});
  row.appendChild(label);row.appendChild(btn);area.appendChild(row);
 });
}
function download(name,txt){var blob=new Blob([txt],{type:'application/json;charset=utf-8'});var url=URL.createObjectURL(blob);var a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url);},4000);}
async function create(){try{$('snapshot').disabled=true;var s=await G.makeSnapshot('manual');selected=s;await refresh();notice('本地快照已创建并校验。它不等于外部备份；请继续导出文件。');}catch(e){notice('快照失败：'+e.message,'error');}finally{$('snapshot').disabled=false;}}
async function doExport(){
 try{
  var s=selected||await G.latest();if(!s)s=await G.makeSnapshot('export');
  var pwd=$('password').value;
  if(!pwd&&!confirm('你将导出未经加密的完整数据，文件可能包含私人记录或配置密钥。确定要明文导出吗？'))return;
  var content=await G.exportSnapshot(s,pwd);var extension=pwd?'加密':'明文';
  download('personal-hub-backup-'+s.at.slice(0,10)+'-'+extension+'.json',content);
  notice('已触发文件导出。请在下载/文件管理器中实际核对文件，再点击“我已确认保存”。');
 }catch(e){notice('导出失败：'+e.message,'error');}
}
function readFile(file){if(typeof file.text==='function')return file.text();return new Promise(function(resolve,reject){var reader=new FileReader();reader.onload=function(){resolve(reader.result);};reader.onerror=function(){reject(new Error('无法读取文件'));};reader.readAsText(file);});}
async function filePreview(){
 var f=$('file').files[0];verified=null;$('restore').disabled=true;$('preview-detail').textContent='';
 if(!f){notice('请先选择一个备份 JSON 文件','warn');return;}
 if(f.size>15*1024*1024){notice('文件大于 15MB，拒绝读取','error');return;}
 try{
  var content=await readFile(f),envelope=JSON.parse(content),pass='';
  if(envelope.format===2){pass=prompt('请输入该备份文件的加密密码')||'';if(!pass)return;}
  verified=await G.importSnapshot(content,pass);
  $('preview-detail').textContent='校验通过\n时间：'+localTime(verified.at)+'\n原因：'+verified.reason+'\n数据表：'+snapshotSummary(verified)+'\n校验：CRC32 '+verified.crc32+'\n请确认应用已关闭所有其他窗口，并已另存最新备份。';
  $('restore').disabled=false;notice('文件格式和数据校验通过。未修改当前记录。');
 }catch(e){notice('校验失败：'+e.message,'error');}
}
async function restore(){
 if(!verified)return;
 if(!confirm('危险操作：恢复会覆盖快照中列出的当前数据表（不改其他表）。确定已另存当前数据并继续吗？'))return;
 if(!confirm('第二次确认：立即恢复 '+localTime(verified.at)+' 的旧数据？'))return;
 try{$('restore').disabled=true;var r=await G.restoreSnapshot(verified);notice('恢复事务成功；恢复前快照编号 '+r.beforeId+'。请返回主控中心并核对记录。');verified=null;await refresh();}catch(e){notice('恢复未完成：'+e.message+'。请勿连续重试，先核对当前记录与恢复前快照。','error');}
}
$('snapshot').addEventListener('click',create);$('refresh').addEventListener('click',function(){refresh().catch(function(e){notice(e.message,'error');});});
$('export').addEventListener('click',doExport);$('preview').addEventListener('click',filePreview);$('restore').addEventListener('click',restore);
$('confirm-saved').addEventListener('click',async function(){if(confirm('你已在电脑/其他位置打开并确认备份文件确实存在？')){await G.exportConfirmed();await refresh();notice('已记录你确认过的外部备份时间。该确认不是自动检测到文件存在。');}});
refresh().then(function(){return G.autoSnapshot();}).then(function(x){if(x.status==='saved')return refresh();}).catch(function(e){notice('初始化失败：'+e.message,'error');});
})();
