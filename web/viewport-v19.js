/* Huawei/HarmonyOS WebView may not implement 100dvh consistently. */
(function(){'use strict';
 var root=document.documentElement,queued=false;
 function sync(){queued=false;var h=window.innerHeight;
  if(window.visualViewport&&window.visualViewport.height>0){
    h=Math.min(h||Infinity,window.visualViewport.height);
  }
  if(h>180)root.style.setProperty('--ph-window-height',Math.round(h)+'px');
 }
 function request(){if(queued)return;queued=true;(window.requestAnimationFrame||function(fn){return setTimeout(fn,0);})(sync);}
 request();window.addEventListener('resize',request,{passive:true});window.addEventListener('orientationchange',request,{passive:true});
 if(window.visualViewport)window.visualViewport.addEventListener('resize',request,{passive:true});
})();
