/* Personal Hub 1.2 local bridge launcher. No remote API or background network requests. */
(function(root,factory){
 'use strict';var api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root&&root.document)api.init(root);
})(typeof window!=='undefined'?window:null,function(){
 'use strict';
 function parseIP(raw){
  if(typeof raw!=='string'||!/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(raw))throw new Error('请输入电脑的 IPv4 地址，不要填写网址、域名或配对码');
  var a=raw.split('.').map(Number);
  if(a.some(function(n){return n<0||n>255;}))throw new Error('IPv4 地址不合法');
  var privateIP=(a[0]===10)||(a[0]===172&&a[1]>=16&&a[1]<=31)||(a[0]===192&&a[1]===168);
  var loopback=a[0]===127&&a[1]===0&&a[2]===0&&a[3]===1;
  if(!privateIP&&!loopback)throw new Error('只允许 10.x、172.16～31.x、192.168.x 或电脑本机 127.0.0.1');
  return a.join('.');
 }
 function endpoint(ip,port){
  var host=parseIP(ip.trim()),p=String(port).trim();
  if(!/^\d{4,5}$/.test(p)||Number(p)<1024||Number(p)>65535)throw new Error('端口需为 1024～65535 的数字');
  return (host==='127.0.0.1'?'http://':'https://')+host+':'+Number(p)+'/';
 }
 function init(w){
  var doc=w.document,ip=doc.getElementById('ip'),port=doc.getElementById('port'),message=doc.getElementById('message');
  if(!ip||!port||!message)return;
  try{var saved=w.localStorage.getItem('personal_hub_bridge_endpoint_v12');if(saved){var u=new URL(saved);ip.value=u.hostname;port.value=u.port||'8765';}}catch(e){}
  doc.getElementById('connect').addEventListener('submit',function(ev){ev.preventDefault();
   try{var url=endpoint(ip.value,port.value);w.localStorage.setItem('personal_hub_bridge_endpoint_v12',url);message.textContent='正在打开 '+url+'。如打不开，请确认电脑桥接器已经启动。';w.location.assign(url);}catch(e){message.textContent=e.message;}
  });
 }
 return {parseIP:parseIP,endpoint:endpoint,init:init};
});
