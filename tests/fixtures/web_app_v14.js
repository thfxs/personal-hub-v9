/* Personal Hub V9 engineering build 0.1
 * Original implementation: lightweight, local-first, no third-party dependencies.
 * External synchronization and health integrations are NOT implemented in this build.
 */
(function(){
'use strict';
var VERSION='0.1.0';
var DB_NAME='personal_hub_v9';
var state=null, db=null, storageMode='starting', currentPage='overview', currentFilter='all', currentSearch='', saveChain=Promise.resolve(), toastTimer=null;
var sections=[
 ['overview','总览','overview'],['tasks','目标计划','calendar'],['projects','项目中心','folder'],['business','创业商业','chart'],
 ['jobs','求职追踪','briefcase'],['ideas','灵感知识','spark'],['health','健康生活','heart'],['links','快捷入口','link'],['settings','系统设置','settings']
];
var titles={overview:'主控中心',tasks:'目标与计划',projects:'项目中心',business:'创业商业化',jobs:'求职追踪',ideas:'灵感与知识',health:'健康与生活',links:'快捷入口',settings:'系统设置'};
var typeNames={tasks:'任务',projects:'项目',business:'商业记录',jobs:'求职记录',ideas:'灵感记录',health:'健康记录',links:'快捷入口'};
var statuses={
 tasks:[['todo','待办'],['doing','进行中'],['done','已完成']],
 projects:[['unsynced','未录入进度'],['planned','规划中'],['active','进行中'],['paused','已暂停'],['complete','已完成']],
 business:[['idea','构思'],['validate','验证'],['build','开发'],['launch','已上线'],['revenue','已有收入'],['pause','暂停']],
 jobs:[['saved','已收藏'],['qualified','符合条件'],['applied','已投递'],['exam','笔试'],['interview','面试'],['offer','录用'],['closed','结束']]
};
var navIcons={
 overview:'<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 10h18"/><path d="m8 16 2 2 5-5"/>',
 folder:'<path d="M3 6a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v10H3z"/><path d="M3 11h18"/>',
 chart:'<path d="M3 21h18M5 17l5-6 4 3 6-9"/><path d="M15 5h5v5"/>',
 briefcase:'<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13a22 22 0 0 0 18 0"/>',
 spark:'<path d="m12 2 2.1 7.9L22 12l-7.9 2.1L12 22l-2.1-7.9L2 12l7.9-2.1z"/>',
 heart:'<path d="M20.8 4.5a5.5 5.5 0 0 0-7.8 0L12 5.6l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.7a5.5 5.5 0 0 0 0-7.8z"/><path d="M5 12h4l2-3 3 6 2-3h3"/>',
 link:'<path d="M10 13a5 5 0 0 0 7 .1l3-3a5 5 0 0 0-7-7l-1.7 1.7M14 11a5 5 0 0 0-7-.1l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
 settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06-1.9 1.9-.06-.06A1.7 1.7 0 0 0 16 18.4l-.16.07a1.7 1.7 0 0 0-1 1.55V21h-2.7v-.08a1.7 1.7 0 0 0-1-1.55L11 19.3a1.7 1.7 0 0 0-1.87.34l-.06.06-1.9-1.9.06-.06A1.7 1.7 0 0 0 7.6 16l-.07-.16a1.7 1.7 0 0 0-1.55-1H5v-2.7h.08a1.7 1.7 0 0 0 1.55-1L6.7 11a1.7 1.7 0 0 0-.34-1.87L6.3 9.1l1.9-1.9.06.06A1.7 1.7 0 0 0 10 7.6l.16-.07a1.7 1.7 0 0 0 1-1.55V5h2.7v.08a1.7 1.7 0 0 0 1 1.55l.16.07a1.7 1.7 0 0 0 1.87-.34l.06-.06 1.9 1.9-.06.06A1.7 1.7 0 0 0 18.4 10l.07.16a1.7 1.7 0 0 0 1.55 1H21v2.7h-.08a1.7 1.7 0 0 0-1.55 1z"/>',
 plus:'<path d="M12 4v16M4 12h16"/>',clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>'};
function icon(name){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(navIcons[name]||navIcons.overview)+'</svg>';}
function e(v){return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function id(){return 'ph_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,9);}
function today(){var d=new Date();return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());}
function pad(v){return String(v).padStart(2,'0');}
function dayStart(s){if(!s)return null;var a=s.split('-').map(Number);return new Date(a[0],a[1]-1,a[2]);}
function daysUntil(s){if(!s)return null;var d=dayStart(s), n=dayStart(today());return d?Math.round((d.getTime()-n.getTime())/86400000):null;}
function dateGroup(d,period){if(!d)return false;var n=daysUntil(d);if(period==='today')return n===0;if(period==='week')return n>=0 && n<=6;if(period==='month'){return d.slice(0,7)===today().slice(0,7);}return true;}
function timeLabel(date){if(!date)return '未设置';return date.replace(/-/g,'.');}
function safeHref(raw){if(typeof raw!=='string')return '';try{var u=new URL(raw);return (u.protocol==='https:'||u.protocol==='http:')?u.href:'';}catch(err){return '';}}
function fmtNum(n){return Number(n||0).toLocaleString('zh-CN');}
function humanStatus(type,status){var a=statuses[type]||[];for(var i=0;i<a.length;i++)if(a[i][0]===status)return a[i][1];return status||'未分类';}
function seed(){return {version:1,createdAt:new Date().toISOString(),updatedAt:new Date().toISOString(),projects:[
  '材料管家','OmiScope Cell','OmiScope Bulk','OmiScope Microbiome','教育产品矩阵','股票研究','准时迷路'
].map(function(n){return {id:id(),title:n,status:'unsynced',category:'项目',progress:null,note:'',nextStep:'',deadline:'',createdAt:new Date().toISOString()};}),tasks:[],business:[],jobs:[],ideas:[],health:[],links:[],settings:{motion:true,showClock:true}};}
function normalize(data){if(!data||typeof data!=='object'||Array.isArray(data))throw new Error('备份文件不是有效的数据对象');
 if(data.version!==1)throw new Error('备份版本不兼容（需要版本 1）');
 var fields=['projects','tasks','business','jobs','ideas','health','links'];
 fields.forEach(function(k){if(!Array.isArray(data[k]))throw new Error('备份缺少 '+k+' 数组');if(data[k].length>200000)throw new Error(k+' 条目数量异常');data[k].forEach(function(r){if(!r||typeof r!=='object'||Array.isArray(r)||typeof r.id!=='string')throw new Error(k+' 存在无效记录');});});
 data.settings=data.settings&&typeof data.settings==='object'?data.settings:{motion:true,showClock:true};return data;}
function openDB(){return new Promise(function(resolve,reject){if(!('indexedDB' in window)){reject(new Error('浏览器无 IndexedDB'));return;}var request=window.indexedDB.open(DB_NAME,1);request.onupgradeneeded=function(){var d=request.result;if(!d.objectStoreNames.contains('kv'))d.createObjectStore('kv',{keyPath:'key'});};request.onsuccess=function(){resolve(request.result);};request.onerror=function(){reject(request.error||new Error('数据库打开失败'));};request.onblocked=function(){reject(new Error('数据库被其他标签页锁定'));};});}
function getDB(){return new Promise(function(resolve,reject){var req=db.transaction(['kv'],'readonly').objectStore('kv').get('main');req.onsuccess=function(){resolve(req.result?req.result.value:null);};req.onerror=function(){reject(req.error);};});}
function putDB(data){return new Promise(function(resolve,reject){var tx=db.transaction(['kv'],'readwrite');tx.objectStore('kv').put({key:'main',value:data});tx.oncomplete=function(){resolve();};tx.onerror=function(){reject(tx.error||new Error('写入失败'));};tx.onabort=function(){reject(tx.error||new Error('写入被取消'));};});}
function setStorageLabel(){var label=document.getElementById('storage-label');if(!label)return;label.textContent=storageMode==='indexeddb'?'本地数据库就绪':storageMode==='localStorage'?'简化本地存储':'存储异常';}
function save(){var snapshot=JSON.parse(JSON.stringify(state));document.getElementById('save-status').textContent='正在保存…';saveChain=saveChain.catch(function(){}).then(function(){if(storageMode==='indexeddb')return putDB(snapshot);if(storageMode==='localStorage'){localStorage.setItem(DB_NAME,JSON.stringify(snapshot));return;}throw new Error('没有可用的存储方式');}).then(function(){document.getElementById('save-status').textContent='已保存到 '+(storageMode==='indexeddb'?'IndexedDB':'浏览器本地存储');return true;}).catch(function(err){document.getElementById('save-status').textContent='保存失败：请立即导出备份';toast('保存失败：'+err.message);return false;});return saveChain;}
function mutate(fn,msg){fn(state);state.updatedAt=new Date().toISOString();save().then(function(ok){if(ok&&msg)toast(msg);});render();}
function toast(msg){var el=document.getElementById('toast');el.textContent=msg;el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(function(){el.classList.remove('show');},2600);}
function navigate(page){if(!titles[page])return;currentPage=page;currentFilter='all';currentSearch='';render();document.getElementById('main-content').scrollTop=0;}
function nav(){document.getElementById('navigation').innerHTML=sections.map(function(s){return '<button type="button" class="nav-item '+(currentPage===s[0]?'active':'')+'" data-nav="'+s[0]+'" aria-label="'+s[1]+'" title="'+s[1]+'">'+icon(s[2])+'<span class="nav-label">'+s[1]+'</span></button>';}).join('');document.getElementById('page-title').textContent=titles[currentPage];}
function frame(inner){document.getElementById('main-content').innerHTML=inner;}
function panel(title,content,action,auxIcon){return '<section class="panel"><div class="panel-in"><div class="panel-head"><div class="panel-title">'+icon(auxIcon||'overview')+e(title)+'</div>'+(action||'')+'</div>'+content+'</div></section>';}
function empty(text,type){return '<div class="empty"><span class="big">◇</span>'+e(text)+(type?'<div><button class="button tiny" data-action="add" data-type="'+type+'">＋ 新增'+typeNames[type]+'</button></div>':'')+'</div>';}
function badge(text,kind){return '<span class="tag '+(kind||'')+'">'+e(text)+'</span>';}
function displayStatus(type,value){if(value==='done'||value==='complete'||value==='offer'||value==='revenue')return badge(humanStatus(type,value),'green');if(value==='paused'||value==='closed')return badge(humanStatus(type,value),'danger');if(value==='unsynced')return badge('待同步','amber');if(value==='doing'||value==='active'||value==='interview'||value==='applied')return badge(humanStatus(type,value),'purple');return badge(humanStatus(type,value));}
function metric(label,value,sub,style){return '<article class="panel metric"><span class="metric-label">'+e(label)+'</span><div class="metric-val '+(style||'')+'">'+e(value)+'</div><span class="metric-caption">'+e(sub)+'</span></article>';}
function projectMini(p){var prog=(p.progress==null||p.progress==='')?null:Number(p.progress);return '<div class="entry"><div class="entry-main"><div class="entry-title">'+e(p.title)+'</div><div class="entry-desc">'+displayStatus('projects',p.status)+(p.nextStep?' · '+e(p.nextStep):'')+'</div>'+(prog!=null&&isFinite(prog)?'<div class="dots"><div class="fill" style="width:'+Math.max(0,Math.min(100,prog))+'%"></div></div>':'')+'</div><button class="button tiny" data-action="edit" data-type="projects" data-id="'+e(p.id)+'">查看</button></div>';}
function renderOverview(){
 var ts=state.tasks, done=ts.filter(function(t){return t.status==='done';}).length, active=ts.filter(function(t){return t.status!=='done';}).length;
 var due=ts.filter(function(t){return t.status!=='done'&&t.due&&daysUntil(t.due)!==null&&daysUntil(t.due)<=0;}).length;
 var applied=state.jobs.filter(function(j){return ['applied','exam','interview','offer'].indexOf(j.status)>=0;}).length;
 var upcoming=ts.filter(function(t){return t.status!=='done';}).sort(function(a,b){return (a.due||'9999').localeCompare(b.due||'9999');}).slice(0,4);
 var pname=state.projects.filter(function(p){return p.status==='active';}).length;
 var percent=ts.length?Math.round(done/ts.length*100):0;
 var statusInfo=storageMode==='localStorage'?'<div class="data-warning">浏览器未能使用 IndexedDB，当前采用容量较小的 localStorage。请经常导出备份。</div>':'';
 frame(statusInfo+'<div class="hero"><section class="hero-main"><div class="hero-index">COMMAND CENTER · LOCAL SYSTEM</div><h2>掌控你的每一步<span style="color:var(--cyan)">.</span></h2><p>项目推进、目标执行、创业与求职，随时查看和编辑。所有个人记录优先保存在本机。</p><div class="hero-buttons"><button class="button primary" data-action="quick">＋ 快速记录</button><button class="button" data-nav="tasks">今日计划 →</button></div><div class="hero-ornament"><span>V9</span></div></section><div class="side-metrics">'+
 metric('待办任务',active,'真实记录','accent')+metric('已完成',done,ts.length?'全部任务的 '+percent+'%':'尚无任务','accent-green')+metric('进行中项目',pname,'未录入状态不计入','accent-pink')+metric('已投递 / 进入流程',applied,'求职数据','accent')+'</div></div>'+
 '<div class="grid-two">'+panel('今日优先事项',upcoming.length?'<div class="entry-list">'+upcoming.map(function(t){return taskMini(t);}).join('')+'</div>':empty('还没有任务。新增后这里会自动显示最近待办。','tasks'),'<button class="panel-link" data-nav="tasks">全部任务 →</button>','calendar')+
 panel('项目作战区',state.projects.length?'<div class="entry-list">'+state.projects.slice(0,5).map(projectMini).join('')+'</div>':empty('暂无项目','projects'),'<button class="panel-link" data-nav="projects">项目中心 →</button>','folder')+'</div>'+
 '<div class="grid-three">'+panel('创业商业化','<div class="big-number">'+state.business.length+'</div><div class="notice">商业记录 · 已上线 '+state.business.filter(function(x){return x.stage==='launch'||x.stage==='revenue';}).length+' 项</div>','<button class="panel-link" data-nav="business">进入模块 →</button>','chart')+
 panel('求职进度','<div class="big-number">'+state.jobs.length+'</div><div class="notice">岗位记录 · 面试 '+state.jobs.filter(function(x){return x.status==='interview';}).length+' 项</div>','<button class="panel-link" data-nav="jobs">进入模块 →</button>','briefcase')+
 panel('灵感与健康','<div class="stats-strip">'+badge(state.ideas.length+' 条灵感','purple')+badge(state.health.length+' 条健康记录','green')+'</div><div class="line-sep"></div><div class="notice">新想法和健康数据可直接在 V9 上录入。</div>','<button class="panel-link" data-nav="ideas">灵感库 →</button>','spark')+'</div>');}
function taskMini(t){var delta=daysUntil(t.due);return '<div class="entry"><div class="entry-main"><div class="entry-title">'+e(t.title)+'</div><div class="entry-desc">'+e(t.due?('截至 '+timeLabel(t.due)+(delta<0?' · 已逾期':delta===0?' · 今天':'')):'未设置日期')+' · '+e(t.priority||'普通')+'</div></div><div class="entry-side"><button class="button tiny" data-action="toggle" data-id="'+e(t.id)+'" title="标记完成">✓</button><button class="button tiny" data-action="edit" data-type="tasks" data-id="'+e(t.id)+'">编辑</button></div></div>';}
function sectionTitle(title,desc,type){return '<div class="page-head"><div><h2>'+e(title)+'</h2><p>'+e(desc)+'</p></div><div class="action-row"><button class="button primary" data-action="add" data-type="'+type+'">＋ 新增'+typeNames[type]+'</button></div></div>';}
function genericList(type,desc){var data=state[type].slice();var title=titles[type];
 if(currentSearch){var q=currentSearch.toLowerCase();data=data.filter(function(x){return JSON.stringify(x).toLowerCase().indexOf(q)>=0;});}
 if(type==='tasks'&&currentFilter!=='all')data=data.filter(function(x){return dateGroup(x.due,currentFilter);});
 if(type==='tasks')data.sort(function(a,b){return (a.status==='done'?1:0)-(b.status==='done'?1:0)||(a.due||'9999').localeCompare(b.due||'9999');});
 else if(type==='health')data.sort(function(a,b){return String(b.date||'').localeCompare(String(a.date||''));});
 else data.sort(function(a,b){return String(b.updatedAt||b.createdAt||'').localeCompare(String(a.updatedAt||a.createdAt||''));});
 var top=sectionTitle(title,desc,type);
 top+='<div class="toolbar"><input type="search" id="list-search" placeholder="搜索'+e(typeNames[type])+'…" value="'+e(currentSearch)+'" aria-label="搜索" />';
 if(type==='tasks'){[['all','全部'],['today','今天'],['week','未来7天'],['month','本月']].forEach(function(item){top+='<button class="chip '+(currentFilter===item[0]?'active':'')+'" data-action="filter" data-filter="'+item[0]+'">'+item[1]+'</button>';});}
 top+='</div>';
 top+='<div class="page-grid">'+(data.length?data.map(function(rec){return genericCard(type,rec);}).join(''):empty(currentSearch?'没有匹配的记录':'目前没有记录',type))+'</div>';
 frame(top);
}
function genericCard(type,x){var title=(x.title||x.position||x.company||x.date||'未命名'), extra='', status='', sub='';
 if(type==='projects'){status=displayStatus(type,x.status);extra=(x.progress==null||x.progress==='')?'进度：待录入':'进度：'+e(x.progress)+'%';sub=x.nextStep||x.note;}
 if(type==='tasks'){status=displayStatus(type,x.status);extra='到期 '+(x.due?timeLabel(x.due):'未设置')+' · '+e(x.priority||'普通');sub=x.note||'';}
 if(type==='jobs'){title=x.position||'未命名职位';status=displayStatus(type,x.status);extra=e(x.company||'未填写单位')+' · '+(x.deadline?'截止 '+timeLabel(x.deadline):'未设置截止');sub=x.note||'';}
 if(type==='business'){status=displayStatus(type,x.stage);extra=x.amount?'预估金额 '+e(x.amount)+' 元':'金额未录入';sub=x.nextStep||x.note;}
 if(type==='ideas'){status=badge(x.category||'灵感','purple');extra=x.projectId?projectName(x.projectId):'未关联项目';sub=x.text||'';}
 if(type==='health'){title=timeLabel(x.date);status=badge('手动记录','green');extra='步数 '+(x.steps!==''&&x.steps!=null?e(x.steps):'—')+' · 睡眠 '+(x.sleep!==''&&x.sleep!=null?e(x.sleep)+'h':'—');sub='体重 '+(x.weight!==''&&x.weight!=null?e(x.weight)+'kg':'—')+(x.note?' · '+e(x.note):'');}
 if(type==='links'){status=badge(x.category||'链接');extra=safeHref(x.url)?'<a target="_blank" rel="noopener noreferrer" href="'+e(safeHref(x.url))+'">访问链接 ↗</a>':'链接格式无效';sub=x.note||'';}
 return '<article class="entry"><div class="entry-main"><div class="entry-title">'+e(title)+'</div><div class="entry-desc">'+status+' <span class="muted">'+extra+'</span></div>'+(sub?'<div class="entry-desc">'+e(sub.length>150?sub.slice(0,150)+'…':sub)+'</div>':'')+(type==='projects'&&x.progress!=null&&x.progress!==''?'<div class="dots"><div class="fill" style="width:'+Math.max(0,Math.min(100,Number(x.progress)||0))+'%"></div></div>':'')+'</div><div class="entry-side">'+(type==='tasks'?'<button class="button tiny" data-action="toggle" data-id="'+e(x.id)+'">'+(x.status==='done'?'↶':'✓')+'</button>':'')+'<button class="button tiny" data-action="edit" data-type="'+type+'" data-id="'+e(x.id)+'">编辑</button></div></article>';}
function projectName(pid){for(var i=0;i<state.projects.length;i++)if(state.projects[i].id===pid)return state.projects[i].title;return '关联项目已删除';}
function renderHealth(){genericList('health','步数、睡眠、体重等指标；本版仅支持手动录入。华为健康尚未连接。');}
function renderSettings(){var sets=state.settings, total=['projects','tasks','business','jobs','ideas','health','links'].reduce(function(v,k){return v+state[k].length;},0);
 frame('<div class="page-head"><div><h2>系统与数据</h2><p>本地数据、备份与视觉控制。自动云同步暂未启用。</p></div></div>'+
 panel('本地数据库','<div class="setting-row"><div><strong>存储方式</strong><p>当前 '+e(storageMode==='indexeddb'?'IndexedDB（推荐）':storageMode==='localStorage'?'localStorage（降级模式）':'未就绪')+'；共有 '+total+' 条记录（包括初始项目名录）。</p></div>'+badge(storageMode==='indexeddb'?'已连接':'需留意',storageMode==='indexeddb'?'green':'amber')+'</div>'+
 '<div class="setting-row"><div><strong>导出完整备份</strong><p>下载 JSON 文件，内容包含全部个人记录。请妥善保存，不要上传到公开仓库。</p></div><button class="button" data-action="export">导出 JSON</button></div>'+
 '<div class="setting-row"><div><strong>恢复备份</strong><p>导入将替换当前所有记录；操作前请先导出备份。</p></div><button class="button" data-action="import">导入 JSON</button></div>'+
 '<div class="setting-row"><div><strong>动效模式</strong><p>控制 HUD 呼吸、光效和背景动画，低电量时可以关闭。</p></div><button type="button" aria-label="切换动效" class="switch '+(sets.motion?'on':'')+'" data-action="motion"></button></div>',null,'settings')+
 '<div style="height:14px"></div>'+panel('数据连接与边界','<div class="entry-list">'+
 '<div class="entry"><div class="entry-main"><div class="entry-title">GitHub / 项目测试报告</div><div class="entry-desc">尚未配置授权或数据适配器，因此不会自动更新仓库进度。</div></div>'+badge('未接入','amber')+'</div>'+
 '<div class="entry"><div class="entry-main"><div class="entry-title">跨设备同步</div><div class="entry-desc">暂不支持 V9、Mac、Windows 自动合并修改；目前可通过 JSON 备份迁移。</div></div>'+badge('未接入','amber')+'</div>'+
 '<div class="entry"><div class="entry-main"><div class="entry-title">华为运动健康</div><div class="entry-desc">目前仅支持手动填写；自动读取需要官方授权和另行兼容验证。</div></div>'+badge('未接入','amber')+'</div>'+
 '</div>',null,'link')+'<div class="notice" style="margin-top:14px">安全提醒：本工程无账户密码和云端数据库。不要把导出的个人 JSON、求职信息或健康记录提交到公开 GitHub 仓库。浏览器清除网站数据可能导致本地记录丢失，请定期备份。</div>');}
function renderLinks(){genericList('links','保存常用网址作为按钮，访问时会在新标签页打开。');}
function render(){if(!state)return;nav();document.documentElement.classList.toggle('no-motion',state.settings.motion===false);setStorageLabel();if(currentPage==='overview')renderOverview();else if(currentPage==='settings')renderSettings();else if(currentPage==='health')renderHealth();else if(currentPage==='links')renderLinks();else{
 var desc={tasks:'今日、本周、本月目标；支持直接编辑、完成标记和截止日期。',projects:'追踪真实项目、里程碑、状态和下一步行动；不自动伪造完成率。',business:'创业方向、产品验证、商业阶段、下一步及金额记录。',jobs:'岗位筛选、投递、笔面试与截止时间，保存在本地。',ideas:'记录创业灵感、新奇想法，关联项目与待验证问题。'};
 genericList(currentPage,desc[currentPage]||'');}
}
function field(key,label,type,placeholder,options,value,required,wide){var input='';value=value==null?'':value;
 if(type==='select'){input='<select name="'+key+'">'+options.map(function(op){return '<option value="'+e(op[0])+'" '+(String(value)===String(op[0])?'selected':'')+'>'+e(op[1])+'</option>';}).join('')+'</select>';}
 else if(type==='textarea'){input='<textarea name="'+key+'" maxlength="8000" placeholder="'+e(placeholder||'')+'">'+e(value)+'</textarea>';}
 else {input='<input name="'+key+'" type="'+type+'" '+(type==='number'?'step="any" ':'')+(required?'required ':'')+'maxlength="'+(type==='url'?2000:200)+'" placeholder="'+e(placeholder||'')+'" value="'+e(value)+'" />';}
 return '<div class="field '+(wide?'wide':'')+'"><label for="">'+e(label)+'</label>'+input+'</div>';}
function choices(type){return statuses[type]||[];}
function projectOpts(){return [['','不关联']].concat(state.projects.map(function(p){return [p.id,p.title];}));}
function fieldsFor(type,x){var f='';
 if(type==='projects'){f+=field('title','项目名称','text','例如：材料管家',null,x.title,true,true);f+=field('status','项目状态','select',null,choices(type),x.status||'unsynced');f+=field('progress','人工核实的完成率（%）','number','留空表示未核实',null,x.progress==null?'':x.progress);f+=field('category','项目分类','text','软件 / 研究 / 创作',null,x.category||'');f+=field('deadline','目标日期','date','',null,x.deadline||'');f+=field('nextStep','下一步行动','text','',null,x.nextStep||'',false,true);f+=field('note','项目备注','textarea','',null,x.note||'',false,true);}
 if(type==='tasks'){f+=field('title','任务名称','text','',null,x.title,true,true);f+=field('status','状态','select','',choices(type),x.status||'todo');f+=field('priority','优先级','select','',[['普通','普通'],['高','高'],['紧急','紧急'],['低','低']],x.priority||'普通');f+=field('due','截止日期','date','',null,x.due||'');f+=field('projectId','关联项目','select','',projectOpts(),x.projectId||'');f+=field('note','任务说明','textarea','',null,x.note||'',false,true);}
 if(type==='business'){f+=field('title','创业方向 / 商业事项','text','',null,x.title,true,true);f+=field('stage','阶段','select','',choices(type),x.stage||'idea');f+=field('amount','预估金额（元，可空）','number','',null,x.amount||'');f+=field('deadline','目标日期','date','',null,x.deadline||'');f+=field('nextStep','下一步行动','text','',null,x.nextStep||'',false,true);f+=field('note','备注','textarea','',null,x.note||'',false,true);}
 if(type==='jobs'){f+=field('position','岗位名称','text','',null,x.position,true,true);f+=field('company','单位 / 企业','text','',null,x.company||'');f+=field('status','状态','select','',choices(type),x.status||'saved');f+=field('deadline','截止日期','date','',null,x.deadline||'');f+=field('url','招聘信息网址','url','https://',null,x.url||'',false,true);f+=field('note','报考条件 / 进展 / 备注','textarea','',null,x.note||'',false,true);}
 if(type==='ideas'){f+=field('title','灵感标题','text','',null,x.title,true,true);f+=field('category','分类','select','',[['创业','创业'],['技术','技术'],['科学','科学'],['产品','产品'],['生活','生活'],['其他','其他']],x.category||'创业');f+=field('projectId','关联项目','select','',projectOpts(),x.projectId||'');f+=field('text','想法内容','textarea','写下想法与下一步验证方式',null,x.text||'',false,true);}
 if(type==='health'){f+=field('date','记录日期','date','',null,x.date||today(),true);f+=field('steps','步数','number','',null,x.steps==null?'':x.steps);f+=field('sleep','睡眠（小时）','number','',null,x.sleep==null?'':x.sleep);f+=field('weight','体重（kg）','number','',null,x.weight==null?'':x.weight);f+=field('note','备注','textarea','',null,x.note||'',false,true);}
 if(type==='links'){f+=field('title','名称','text','',null,x.title,true,true);f+=field('url','网址','url','https://',null,x.url||'',true,true);f+=field('category','分类','text','工具 / 项目 / 服务',null,x.category||'');f+=field('note','备注','textarea','',null,x.note||'',false,true);}
 return f;}
function modal(content){document.getElementById('modal-root').innerHTML='<div class="modal-shade" data-action="modal-shade"><section class="modal" role="dialog" aria-modal="true">'+content+'</section></div>';}
function closeModal(){document.getElementById('modal-root').innerHTML='';}
function quick(){var opts=['tasks','projects','ideas','jobs','business','health','links'];modal('<div class="modal-header"><h2>QUICK CAPTURE · 快速记录</h2><button class="modal-close" data-action="close" aria-label="关闭">×</button></div><div class="module-grid">'+opts.map(function(k){return '<button class="module-card" data-action="add" data-type="'+k+'">'+icon(({tasks:'calendar',projects:'folder',ideas:'spark',jobs:'briefcase',business:'chart',health:'heart',links:'link'})[k])+'<strong>'+typeNames[k]+'</strong><span>新建并立即保存</span></button>';}).join('')+'</div>');}
function edit(type,rid){if(!typeNames[type])return;var record=rid?state[type].find(function(x){return x.id===rid;}):null;if(rid&&!record){toast('记录不存在');return;}var x=record||{};
 modal('<div class="modal-header"><h2>'+(rid?'修改':'新增')+typeNames[type]+'</h2><button class="modal-close" data-action="close" aria-label="关闭">×</button></div><form id="edit-form" data-type="'+type+'" data-id="'+e(rid||'')+'"><div class="form-grid">'+fieldsFor(type,x)+'</div><div class="form-actions">'+(rid?'<button type="button" class="button danger" data-action="delete" data-type="'+type+'" data-id="'+e(rid)+'">删除</button>':'')+'<button type="button" class="button" data-action="close">取消</button><button class="button primary" type="submit">保存到本机</button></div></form>');
 var first=document.querySelector('#edit-form input:not([type=date])');if(first)first.focus();}
function onSaveForm(ev){ev.preventDefault();var form=ev.target,type=form.getAttribute('data-type'),rid=form.getAttribute('data-id');if(!typeNames[type])return;var data={};Array.from(form.elements).forEach(function(el){if(!el.name)return;data[el.name]=el.value.trim();});
 if(type==='projects'){if(data.progress!==''){var p=Number(data.progress);if(!isFinite(p)||p<0||p>100){toast('完成率必须为 0～100，或留空');return;}data.progress=p;}else data.progress=null;}
 if(type==='health'){['steps','sleep','weight'].forEach(function(k){if(data[k]!=='')data[k]=Number(data[k]);});if((data.steps!==''&&(!isFinite(data.steps)||data.steps<0))||(data.sleep!==''&&(!isFinite(data.sleep)||data.sleep<0||data.sleep>24))||(data.weight!==''&&(!isFinite(data.weight)||data.weight<=0))){toast('健康数据存在无效数值');return;}}
 if(type==='business'&&data.amount!==''&&(!isFinite(Number(data.amount))||Number(data.amount)<0)){toast('请输入有效金额');return;}
 if((type==='jobs'||type==='links')&&data.url&&!safeHref(data.url)){toast('仅允许 http:// 或 https:// 网址');return;}
 if(type==='links'&&!data.url){toast('请填写网址');return;}
 if(rid){var old=state[type].find(function(x){return x.id===rid;});if(!old){toast('记录已不存在');return;}}
 mutate(function(s){if(rid){var old=s[type].find(function(x){return x.id===rid;});Object.assign(old,data,{updatedAt:new Date().toISOString()});}else{s[type].unshift(Object.assign({id:id(),createdAt:new Date().toISOString()},data));}},'已保存在本机');closeModal();}
function del(type,rid){var old=state[type].find(function(x){return x.id===rid;});if(!old)return;if(!window.confirm('确定删除此'+typeNames[type]+'吗？此操作不可撤销，建议先导出备份。'))return;
 mutate(function(s){s[type]=s[type].filter(function(x){return x.id!==rid;});},'已删除记录');closeModal();}
function toggleTask(rid){mutate(function(s){var x=s.tasks.find(function(t){return t.id===rid;});if(x){x.status=x.status==='done'?'todo':'done';x.completedAt=x.status==='done'?new Date().toISOString():null;x.updatedAt=new Date().toISOString();}},'任务状态已更新');}
function exportBackup(){var backup={kind:'personal-hub-local-backup',exportedAt:new Date().toISOString(),data:state};var json=JSON.stringify(backup,null,2);var blob=new Blob([json],{type:'application/json;charset=utf-8'});var url=URL.createObjectURL(blob);var a=document.createElement('a');a.href=url;a.download='personal-hub-backup-'+today()+'.json';document.body.appendChild(a);a.click();document.body.removeChild(a);setTimeout(function(){URL.revokeObjectURL(url);},1000);toast('备份文件已生成，请保存到可靠位置');}
function importBackup(file){if(!file)return;if(file.size>15*1024*1024){toast('文件大于 15MB，已拒绝导入');return;}var fr=new FileReader();fr.onload=function(){try{var obj=JSON.parse(fr.result),data=normalize(obj.kind==='personal-hub-local-backup'?obj.data:obj);if(!window.confirm('导入将覆盖当前全部记录。确定已经备份当前数据，并继续替换吗？'))return;var previous=state;state=data;save().then(function(ok){if(!ok){state=previous;render();toast('导入未保存，已恢复原先的内存状态');return;}render();toast('备份导入完成');});}catch(err){toast('导入失败：'+err.message);}};fr.onerror=function(){toast('无法读取文件');};fr.readAsText(file);}
function onAction(ev){var btn=ev.target.closest('[data-action],[data-nav]');if(!btn)return;if(btn.hasAttribute('data-nav')){navigate(btn.getAttribute('data-nav'));return;}
 var action=btn.getAttribute('data-action'),type=btn.getAttribute('data-type'),rid=btn.getAttribute('data-id');
 if(action==='modal-shade'){if(ev.target===btn)closeModal();return;}
 if(action==='close')closeModal();if(action==='quick')quick();if(action==='add')edit(type,null);if(action==='edit')edit(type,rid);if(action==='delete')del(type,rid);if(action==='toggle')toggleTask(rid);
 if(action==='filter'){currentFilter=btn.getAttribute('data-filter');render();}
 if(action==='export')exportBackup();if(action==='import')document.getElementById('import-input').click();
 if(action==='motion')mutate(function(s){s.settings.motion=!s.settings.motion;},'显示模式已更新');}
function setupEvents(){document.body.addEventListener('click',onAction);document.getElementById('quick-add').addEventListener('click',quick);document.body.addEventListener('submit',function(ev){if(ev.target.id==='edit-form')onSaveForm(ev);});
 document.getElementById('import-input').addEventListener('change',function(ev){if(ev.target.files.length)importBackup(ev.target.files[0]);ev.target.value='';});
 document.body.addEventListener('input',function(ev){if(ev.target.id==='list-search'){var pos=ev.target.selectionStart;currentSearch=ev.target.value;render();var input=document.getElementById('list-search');if(input){input.focus();try{input.setSelectionRange(pos,pos);}catch(err){}}}});
 document.addEventListener('keydown',function(ev){if(ev.key==='Escape')closeModal();if((ev.ctrlKey||ev.metaKey)&&ev.key==='k'){ev.preventDefault();quick();}});}
function clock(){var now=new Date(),stamp=pad(now.getHours())+':'+pad(now.getMinutes());document.getElementById('top-clock').textContent=stamp;document.getElementById('footer-time').textContent=now.getFullYear()+'.'+pad(now.getMonth()+1)+'.'+pad(now.getDate())+' / '+['周日','周一','周二','周三','周四','周五','周六'][now.getDay()];}
function installSW(){if('serviceWorker' in navigator && (location.protocol==='https:'||location.hostname==='localhost'||location.hostname==='127.0.0.1'))navigator.serviceWorker.register('./sw.js').catch(function(){});}
async function init(){setupEvents();clock();setInterval(clock,15000);try{db=await openDB();storageMode='indexeddb';var stored=await getDB();state=stored?normalize(stored):seed();if(!stored)await putDB(state);}catch(err){try{storageMode='localStorage';var raw=localStorage.getItem(DB_NAME);state=raw?normalize(JSON.parse(raw)):seed();if(!raw)localStorage.setItem(DB_NAME,JSON.stringify(state));}catch(err2){storageMode='broken';state=seed();}}setStorageLabel();render();document.getElementById('save-status').textContent=storageMode==='broken'?'存储不可用：请不要录入重要数据':'离线数据就绪 · '+(storageMode==='indexeddb'?'IndexedDB':'localStorage');if(storageMode==='broken')toast('设备浏览器无法持久化数据');installSW();}
init();
})();
