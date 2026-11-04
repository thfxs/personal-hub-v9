(function(){'use strict';
var $=function(id){return document.getElementById(id);};var current=[],filter='all';
function node(tag,label,className){var e=document.createElement(tag);if(label!==undefined)e.textContent=String(label);if(className)e.className=className;return e;}
function clear(target){while(target.firstChild)target.removeChild(target.firstChild);}
function entry(target,title,details,level){var e=node('div',null,'entry'+(level?' '+level:''));e.appendChild(node('strong',title));if(details)e.appendChild(node('div',details,'meta'));target.appendChild(e);return e;}
function request(path,payload){var opts={cache:'no-store',credentials:'same-origin'};if(payload!==undefined){opts.method='POST';opts.headers={'Content-Type':'application/json','X-Bridge-Request':'1'};opts.body=JSON.stringify(payload);}return fetch(path,opts).then(function(r){return r.json().then(function(d){if(!r.ok)throw Error(d.error||'HTTP '+r.status);return d;});});}
function fmt(t){if(!t)return '未知时间';var d=typeof t==='number'?new Date(t*1000):new Date(t);return isNaN(d.getTime())?'时间未知':d.toLocaleString();}
function show(snapshot){var gh=$('github'),pj=$('projects'),ai=$('ai');clear(gh);clear(pj);clear(ai);
if(snapshot.config_note)entry(gh,snapshot.config_note,'请参考 monitor.example.json 设置电脑本地配置。');
if(!snapshot.github.length)entry(gh,'尚未配置 GitHub 仓库','只读取 config 中列出的 owner/repo；公共仓库无须 Token。');
snapshot.github.forEach(function(repo){var e=entry(gh,repo.repo,repo.state==='ok'?('最新记录 '+repo.runs.length+' 条'):('不可用 · '+repo.reason));if(repo.state==='ok')repo.runs.forEach(function(run){var row=node('div',null,'meta');row.appendChild(node('span',run.name+' · '+run.status+' / '+(run.conclusion||'尚未结束')+' · '+fmt(run.updated_at)));
if(run.url){var a=node('a',' · 打开 GitHub');a.href=run.url;a.target='_blank';a.rel='noopener noreferrer';row.appendChild(a);}e.appendChild(row);});});
if(!snapshot.projects.length)entry(pj,'尚未配置本地 Git 项目','电脑本地项目路径需手动填写，手机无法直接读取电脑磁盘。');
snapshot.projects.forEach(function(x){entry(pj,x.name,x.state==='ok'?(x.branch+' · '+x.sha.slice(0,8)+' · '+x.changed_files+' 个文件变更'):'不可用 · '+x.reason,x.dirty?'yellow':'');});
var c=snapshot.codex||{},d=snapshot.deepseek||{};
if(c.state==='ok'){var lines=[];['primary','secondary'].forEach(function(k){var x=c[k];if(x)lines.push(k+'：已使用 '+x.used_percent+'%，剩余 '+x.remaining_percent+'%，重置 '+fmt(x.reset_at));});entry(ai,'Codex · '+(c.limit_name||'额度窗口'),lines.join('；')||'本次没有额度窗口数据');}
else entry(ai,'Codex',c.state==='disabled'?'未启用（电脑本地配置 codex:true）':'不可用：'+(c.reason||'未知'));
if(d.state==='ok')entry(ai,'DeepSeek API 余额',d.balances.map(function(x){return x.currency+' '+x.balance;}).join(' · '));
else entry(ai,'DeepSeek',d.state==='disabled'?'未启用（电脑本地配置 deepseek:true）':'不可用：'+(d.reason||'未知'));
$('status').textContent='最近采集：'+fmt(snapshot.checked_at)+'；15 分钟内复用缓存；网页可见时每 60 秒更新事件。';}
function drawEvents(){var div=$('events');clear(div);$('unread').textContent=current.filter(function(e){return !e.read;}).length+' 未读';var view=current.filter(function(e){return filter==='all'||(filter==='unread'?!e.read:e.level===filter);});if(!view.length)entry(div,'暂无匹配事件','提醒仅在数据源已配置、实际观测到事件时产生。');view.forEach(function(e){var box=entry(div,e.title,e.detail+' · '+fmt(e.time),e.level+(e.read?' read':''));if(!e.read){var b=node('button','标记已读');b.type='button';b.addEventListener('click',function(){mark([e.id]);});box.appendChild(b);}});}
function mark(ids){request('/api/events/read',{ids:ids}).then(function(){return loadEvents();}).catch(function(e){$('status').textContent='操作失败：'+e.message;});}
function loadEvents(){return request('/api/events').then(function(r){current=r.items||[];drawEvents();});}
function refresh(){return request('/api/status').then(function(st){$('pair').hidden=!!st.paired;$('private').hidden=!st.paired;if(!st.paired){$('status').textContent='尚未配对：先在电脑启动桥接器并输入配对码。';return;}
return request('/api/monitor').then(function(d){show(d.data);return loadEvents();});}).catch(function(e){$('status').textContent='读取失败：'+e.message;});}
$('pairBtn').addEventListener('click',function(){var pin=$('pin').value.trim();if(!/^\d{8}$/.test(pin)){$('status').textContent='配对码应为 8 位数字';return;}request('/api/pair',{pin:pin}).then(function(){$('pin').value='';return refresh();}).catch(function(e){$('status').textContent='配对失败：'+e.message;});});
$('reload').addEventListener('click',refresh);$('readAll').addEventListener('click',function(){var ids=current.filter(function(e){return !e.read&&(filter==='all'||(filter==='unread'?!e.read:e.level===filter));}).map(function(e){return e.id;});if(ids.length)mark(ids);});
Array.prototype.forEach.call(document.querySelectorAll('[data-filter]'),function(b){b.addEventListener('click',function(){filter=b.getAttribute('data-filter');Array.prototype.forEach.call(document.querySelectorAll('[data-filter]'),function(x){x.classList.toggle('on',x===b);});drawEvents();});});
refresh();setInterval(function(){if(!document.hidden)refresh();},60000);
})();
