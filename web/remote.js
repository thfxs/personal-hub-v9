(function(){'use strict';
 var N=window.PersonalHubNativeTransport,$=function(id){return document.getElementById(id);},busy=false;
 function report(s){$('result').textContent=s;}
 if(!N||!N.available()){
  $('state').textContent='当前不是可用的 Android 原生消息环境。请通过电脑桥网页使用旧版快捷指令。';
  document.querySelectorAll('button').forEach(function(b){b.disabled=true;});return;
 }
 function request(method,path,body){return N.request(method,path,body).then(function(r){
  if(r.status>=400)throw Error((r.body&&r.body.error)||('HTTP '+r.status));return r.body;
 });}
 function status(){return Promise.all([N.status(),request('GET','/api/status')]).then(function(values){
  var config=values[0],s=values[1];
  $('state').textContent='电脑 '+config.ip+':'+config.port+' · '+(s.paired?'配对有效':'尚未配对')+
   (s.paired&&s.armed!==undefined?(s.armed?' · 已授权':' · 电脑端未授权'):'');
 }).catch(function(e){$('state').textContent='无法连接：'+e.message+'。请先去同步页检查证书配置。';});}
 function dispatch(body){if(busy)return;if(!$('readyToSend').checked){report('先核对电脑焦点窗口并勾选一次确认，然后每个快捷键只需点击一次。');return;}
  busy=true;report('正在向电脑桥提交……');
  body.request_id='hub17-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,12);
  request('POST','/api/dispatch',body).then(function(r){report('电脑桥响应：'+JSON.stringify(r).slice(0,450)+'。请在电脑确认 AI 是否实际收到，桥接器返回不代表 AI 已完成。');})
   .catch(function(e){report('发送未确认：'+e.message+'。如有网络超时，不要连续点击以免重复。');})
   .finally(function(){busy=false;});
 }
 $('pair').addEventListener('click',function(){var pin=$('pin').value.trim();if(!/^\d{8}$/.test(pin)){report('请填写电脑终端显示的 8 位临时码');return;}
  request('POST','/api/pair',{pin:pin}).then(function(){ $('pin').value='';report('配对成功');return status();}).catch(function(e){report('配对失败：'+e.message);});});
 $('check').addEventListener('click',status);
 $('monitorBtn').addEventListener('click',function(){
  $('monitor').textContent='正在从电脑端查询……';
  request('GET','/api/monitor').then(function(r){
   var d=r.data||{},parts=[];
   (d.github||[]).slice(0,5).forEach(function(x){parts.push('GitHub '+x.repo+'：'+(x.state==='ok'?((x.runs||[]).length+' 条构建记录'):'未连接/失败'));});
   (d.projects||[]).slice(0,5).forEach(function(x){parts.push('项目 '+x.name+'：'+(x.state==='ok'?(x.branch+'，'+x.changed_files+' 项变更'):'不可用'));});
   var c=d.codex||{},ds=d.deepseek||{};
   parts.push('Codex：'+(c.state==='ok'?(c.primary&&c.primary.remaining_percent!==undefined?'剩余额度 '+c.primary.remaining_percent+'%':'已连通'):'未接入或不可用'));
   parts.push('DeepSeek：'+(ds.state==='ok'?(ds.balances||[]).map(function(x){return x.currency+' '+x.balance;}).join('，'):'未接入或不可用'));
   if((d.activities||[]).length)parts.push('电脑上报任务：'+d.activities.length+' 条（不代表所有网页 AI 任务）');
   $('monitor').textContent=parts.join('\n');
  }).catch(function(e){$('monitor').textContent='监控查询失败：'+e.message;});
 });
 $('presets').addEventListener('click',function(e){var b=e.target.closest('button[data-preset]');if(b)dispatch({preset:b.dataset.preset});});
 $('send').addEventListener('click',function(){var s=$('custom').value.trim();if(!s||s.length>2000){report('指令文字需为 1～2000 字');return;}dispatch({text:s});});
 status();
})();
