/* Personal Hub 1.7: Android-only native pinned-HTTPS transport.
 * No browser fetch() to LAN and no JavaScript access to session cookies.
 * Only loaded on the dedicated sync/command pages.
 */
(function(root,factory){
 'use strict';var api=factory(root);
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root&&root.document)root.PersonalHubNativeTransport=api;
})(typeof window!=='undefined'?window:null,function(w){
 'use strict';
 var pending=Object.create(null),listenerInstalled=false,serial=0;
 function isShell(){return !!(w&&w.navigator&&/PersonalHubV9Shell\//.test(w.navigator.userAgent||''));}
 function available(){return isShell()&&!!(w.PersonalHubNative&&typeof w.PersonalHubNative.postMessage==='function');}
 function onReply(event){var data;try{data=JSON.parse(event.data);}catch(e){return;}
  if(!data||!Object.prototype.hasOwnProperty.call(pending,data.id))return;
  var p=pending[data.id];delete pending[data.id];clearTimeout(p.timer);
  if(data.ok)p.resolve(data.data||{});else p.reject(Error(String(data.message||'电脑桥请求失败')));
 }
 function call(type,fields){if(!available())return Promise.reject(Error(isShell()?'安卓 WebView 不支持安全原生消息接口':'此功能仅支持 Android APK'));
  if(!listenerInstalled){w.PersonalHubNative.onmessage=onReply;listenerInstalled=true;}
  return new Promise(function(resolve,reject){
   var id='hubnet-'+Date.now().toString(36)+'-'+(++serial).toString(36);
   var timer=setTimeout(function(){if(pending[id]){delete pending[id];reject(Error('电脑端未在超时时间内确认。若刚才是写入操作，请先重新读取状态，不要重复提交。'));}},26000);
   pending[id]={resolve:resolve,reject:reject,timer:timer};
   try{w.PersonalHubNative.postMessage(JSON.stringify(Object.assign({id:id,type:type},fields||{})));}
   catch(e){clearTimeout(timer);delete pending[id];reject(e);}
  });
 }
 function checkConfig(ip,port,fingerprint){
  if(!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip))throw Error('电脑 IPv4 格式不正确');
  var a=ip.split('.').map(Number);
  if(a.some(function(x){return x>255;}))throw Error('IPv4 数字超出范围');
  if(!(a[0]===10||(a[0]===172&&a[1]>=16&&a[1]<=31)||(a[0]===192&&a[1]===168)))throw Error('仅允许私有局域网地址');
  if(!/^\d+$/.test(String(port))||Number(port)<1024||Number(port)>65535)throw Error('端口不合法');
  var fp=String(fingerprint||'').replace(/[:\s]/g,'').toUpperCase();
  if(!/^[A-F0-9]{64}$/.test(fp))throw Error('请输入 64 位 SHA-256 证书指纹');
  return {ip:a.join('.'),port:Number(port),fingerprint:fp};
 }
 function configure(ip,port,fingerprint,confirmed){try{
  if(!confirmed)throw Error('必须先在电脑本机核对证书指纹并勾选确认');
  return call('bridge_config',Object.assign(checkConfig(ip,port,fingerprint),{confirmed:true}));
 }catch(e){return Promise.reject(e);}}
 function request(method,path,body){return call('bridge_request',{method:method,path:path,body:body||{}}).then(function(r){
  if(typeof r.status!=='number'||!r.body||typeof r.body!=='object')throw Error('电脑响应数据格式异常');
  return r;
 });}
 return {isShell:isShell,available:available,checkConfig:checkConfig,configure:configure,forget:function(){return call('bridge_forget');},status:function(){return call('bridge_status');},request:request};
});
