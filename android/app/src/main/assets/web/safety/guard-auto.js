/* Load after guard-core.js on the main app page. Runs only while the app page is active. */
(function(){'use strict';
 var G=window.PersonalHubGuard;if(!G)return;
 function protect(){G.autoSnapshot().catch(function(err){if(typeof console!=='undefined')console.warn('Personal Hub local snapshot skipped:',err.message);});}
 function start(){setTimeout(protect,7000);setInterval(function(){if(!document.hidden)protect();},30*60*1000);
  document.addEventListener('visibilitychange',function(){if(!document.hidden)protect();});
  /* Never intercept user input, navigation, or app's own save(). */
  G.backupStatus().then(function(status){if(!status.reminder)return;
   var link=document.createElement('a');link.href='./safety/safety.html';link.textContent='备份提醒';
   link.setAttribute('aria-label','距离上次确认外部备份已超过7天，打开数据保护中心');
   link.style.cssText='position:fixed;right:14px;bottom:15px;z-index:9000;display:block;padding:9px 12px;color:#fff2ce;background:#513617;border:1px solid #c09342;border-radius:9px;text-decoration:none;font:13px system-ui;box-shadow:0 0 12px #ffcb6133;';
   document.body.appendChild(link);
  }).catch(function(){});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
