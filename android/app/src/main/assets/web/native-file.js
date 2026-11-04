/* 1.5: origin-scoped native SAF document export. Browser/PWA remains supported.
 * Native host replies only AFTER a system file save; do not claim success on picker launch.
 */
(function(root,factory){
 'use strict';var api=factory(root);
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root&&root.document)root.PersonalHubFiles=api;
})(typeof window!=='undefined'?window:null,function(w){
 'use strict';
 var pending={},listen=false,n=0;
 function nativeReady(){return !!(w&&w.PersonalHubNative&&typeof w.PersonalHubNative.postMessage==='function');}
 function isShell(){return !!(w&&w.navigator&&/PersonalHubV9Shell\//.test(w.navigator.userAgent||''));}
 function id(){return 'hubfile-'+Date.now().toString(36)+'-'+(++n).toString(36);}
 function receive(event){
  var reply;try{reply=JSON.parse(event.data);}catch(e){return;}
  if(!reply||typeof reply.id!=='string'||!Object.prototype.hasOwnProperty.call(pending,reply.id))return;
  var task=pending[reply.id];delete pending[reply.id];clearTimeout(task.timer);
  if(reply.ok)task.resolve(reply.data||{message:reply.message});
  else task.reject(new Error(String(reply.message||'原生操作未完成')));
 }
 function request(type,values){
  if(!nativeReady())return Promise.reject(new Error('当前运行环境没有 Android 原生文件接口'));
  if(!listen){w.PersonalHubNative.onmessage=receive;listen=true;}
  return new Promise(function(resolve,reject){
   var key=id();pending[key]={resolve:resolve,reject:reject,timer:setTimeout(function(){
    if(pending[key]){delete pending[key];reject(new Error('系统文件操作未返回确认，请核对实际文件，不要重复导入/覆盖'));}
   },180000)};
   try{w.PersonalHubNative.postMessage(JSON.stringify(Object.assign({type:type,id:key},values||{})));}
   catch(e){clearTimeout(pending[key].timer);delete pending[key];reject(e);}
  });
 }
 function saveJson(filename,content){
  if(typeof filename!=='string'||!/^.{1,120}\.json$/i.test(filename))return Promise.reject(Error('备份文件名不合法'));
  if(typeof content!=='string'||content.length>4*1024*1024)return Promise.reject(Error('备份文件过大或内容异常'));
  try{JSON.parse(content);}catch(e){return Promise.reject(Error('导出内容不是 JSON 文件'));}
  return request('save_json',{filename:filename,content:content});
 }
 return {isNative:nativeReady,isShell:isShell,saveJson:saveJson,deviceStatus:function(){return request('device_status');},devicePreferences:function(immersive,awake){return request('device_preferences',{immersive:!!immersive,awake:!!awake});}};
});
