(function(){'use strict';
var pc=document.body.getAttribute('data-page')==='pc';
var pair=document.getElementById('pair'),connected=document.getElementById('connected');
var status=document.getElementById('status'),msg=document.getElementById('message'),queue=document.getElementById('queue'),activity=document.getElementById('activity');
var nonce=0;
function text(node,s){node.textContent=s;}
function notice(s,error){text(msg,s);msg.className='message'+(error?' err':'');}
function request(path,payload){var options={credentials:'same-origin',cache:'no-store'};
 if(payload!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-Bridge-Request':'1'};options.body=JSON.stringify(payload);}
 return fetch(path,options).then(function(r){return r.json().then(function(data){if(!r.ok)throw new Error(data.error||'请求失败 '+r.status);return data;});});}
function makeRequestId(){nonce++;return 'v9-'+Date.now().toString(36)+'-'+nonce.toString(36)+'-'+Math.random().toString(36).slice(2,12);}
function escTime(t){try{return new Date(t*1000).toLocaleTimeString();}catch(e){return ''}}
function refresh(){return request('/api/status').then(function(s){
 pair.hidden=!!s.paired;connected.hidden=!s.paired;
 if(!s.paired){text(status,'尚未配对');return;}
 text(status,s.armed?('已授权自动输入，剩余 '+Math.max(0,Math.ceil(s.armed_seconds/60))+' 分钟；待发 '+s.queued+' 条'):('待发模式；目前 '+s.queued+' 条'));
 return Promise.all([request('/api/queue'),request('/api/activity')]).then(function(items){
 renderQueue(items[0].items||[]);renderActivity(items[1].items||[]);});
 }).catch(function(e){text(status,'网络断开或桥接器已关闭');notice(e.message,true);});}
function renderActivity(items){if(!activity)return;while(activity.firstChild)activity.removeChild(activity.firstChild);
 if(!items.length){var p=document.createElement('p');p.className='small';text(p,'暂无电脑端主动上报的任务状态。此处不会猜测 AI 是否完成。');activity.appendChild(p);return;}
 var states={started:'进行中',done:'已完成',failed:'执行失败',attention:'需要处理',info:'状态信息'};
 items.forEach(function(e){var el=document.createElement('div');el.className='queue-item';
 var b=document.createElement('strong');text(b,(states[e.state]||e.state)+' · '+escTime(e.time));el.appendChild(b);
 var name=document.createElement('div');text(name,e.task);el.appendChild(name);
 if(e.detail){var d=document.createElement('p');d.className='small';text(d,e.detail);el.appendChild(d);}activity.appendChild(el);});}
function renderQueue(items){while(queue.firstChild)queue.removeChild(queue.firstChild);
 if(!items.length){var em=document.createElement('p');em.className='small';text(em,'暂无待发指令');queue.appendChild(em);return;}
 items.slice().reverse().forEach(function(item){var box=document.createElement('div');box.className='queue-item';
 var strong=document.createElement('strong');text(strong,'待发 · '+escTime(item.created)+'（'+Math.max(0,Math.ceil((item.expires-Date.now()/1000)/60))+' 分钟后过期）');box.appendChild(strong);
 var body=document.createElement('div');text(body,item.text);box.appendChild(body);
 if(item.note){var p=document.createElement('p');p.className='small';text(p,item.note);box.appendChild(p);}
 if(!pc){var btn=document.createElement('button');text(btn,'重试发送');btn.addEventListener('click',function(){btn.disabled=true;request('/api/queue/retry',{id:item.id}).then(function(r){showResult(r);return refresh();}).catch(function(e){notice(e.message,true);}).then(function(){btn.disabled=false;});});box.appendChild(btn);}
 queue.appendChild(box);});}
function showResult(r){if(r.result==='sent_unconfirmed')notice('电脑已尝试注入并发送按键；是否被 AI 接收仍需在电脑确认。');
 else if(r.result==='duplicate_skipped')notice('短时间重复点击已忽略。');
 else notice('指令已进入待发队列。'+(r.reason||''),false);}
function fire(payload,btn){if(btn)btn.disabled=true;payload.request_id=makeRequestId();request('/api/dispatch',payload).then(function(r){showResult(r);return refresh();}).catch(function(e){notice(e.message,true);}).then(function(){if(btn)btn.disabled=false;});}
var pairBtn=document.getElementById('pairButton');
if(pairBtn)pairBtn.addEventListener('click',function(){var v=document.getElementById('pin').value.trim();if(!/^\d{8}$/.test(v)){notice('请输入八位数字配对码',true);return;}
 pairBtn.disabled=true;request('/api/pair',{pin:v}).then(function(){document.getElementById('pin').value='';notice('配对成功');return refresh();}).catch(function(e){notice(e.message,true);}).then(function(){pairBtn.disabled=false;});});
var refreshBtn=document.getElementById('refresh');if(refreshBtn)refreshBtn.addEventListener('click',refresh);
if(pc){document.getElementById('arm').addEventListener('click',function(){request('/api/admin/arm',{}).then(function(){notice('已授权十分钟。请切回 AI 对话应用，并将光标放在消息输入框。');refresh();}).catch(function(e){notice(e.message,true);});});
document.getElementById('disarm').addEventListener('click',function(){request('/api/admin/disarm',{}).then(function(){notice('自动输入已关闭');refresh();}).catch(function(e){notice(e.message,true);});});
document.getElementById('clearQueue').addEventListener('click',function(){if(!confirm('确定清空所有尚未发送的指令吗？'))return;request('/api/admin/clear-queue',{}).then(function(){notice('队列已清空');refresh();}).catch(function(e){notice(e.message,true);});});}
else{Array.prototype.forEach.call(document.querySelectorAll('[data-preset]'),function(b){b.addEventListener('click',function(){fire({preset:b.getAttribute('data-preset')},b);});});
document.getElementById('sendCustom').addEventListener('click',function(){var v=document.getElementById('custom').value.trim();if(!v||v.length>180||/[\x00-\x1f\x7f]/.test(v)){notice('请输入不超过 180 字的单行指令',true);return;}fire({text:v},this);});}
refresh();setInterval(function(){if(!document.hidden)refresh();},12000);
})();
