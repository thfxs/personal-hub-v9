/* Optional landscape-only swipe across existing main navigation pages. No animation loop. */
(function(root,factory){'use strict';var api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;if(root&&root.document)api.attach(root);})(typeof window!=='undefined'?window:null,function(w){
 'use strict';
 var order=['overview','tasks','projects','business','jobs','ideas','health','links','settings'];
 function shouldIgnore(el){
  if(!el||!el.closest)return true;
  return !!el.closest('button,a,input,textarea,select,[contenteditable],.modal,.modal-overlay,[role=dialog],.horizontal-scroll,.chart-container');
 }
 function targetPage(current,dir){var i=order.indexOf(current);if(i<0)return null;var next=i+(dir<0?1:-1);return next>=0&&next<order.length?order[next]:null;}
 function attach(win){
  var doc=win.document,main=doc.getElementById('main-content');if(!main)return;
  var start=null;
  main.addEventListener('touchstart',function(event){
   start=null;
   if(!win.matchMedia('(orientation: landscape)').matches||event.touches.length!==1||shouldIgnore(event.target))return;
   try{if(win.localStorage.getItem('personal_hub_landscape_swipe')==='off' && !main.classList.contains('ph20-active'))return;}catch(e){}
   start={x:event.touches[0].clientX,y:event.touches[0].clientY,time:Date.now(),node:event.target};
  },{passive:true});
  main.addEventListener('touchend',function(event){
   if(!start||!event.changedTouches.length){start=null;return;}
   var old=start;start=null;
   if(doc.querySelector('[role=dialog],.modal-overlay:not([hidden]),#modal-root:not(:empty)'))return;
   var dx=event.changedTouches[0].clientX-old.x,dy=event.changedTouches[0].clientY-old.y;
   if(Math.abs(dx)<75||Math.abs(dx)<Math.abs(dy)*1.6||Date.now()-old.time>900)return;
   var active=doc.querySelector('#navigation .nav-item.active');if(!active)return;
   var page=targetPage(active.getAttribute('data-nav'),dx);
   if(page){var nav=doc.querySelector('#navigation [data-nav="'+page+'"]');if(nav)nav.click();}
  },{passive:true});
  main.addEventListener('touchcancel',function(){start=null;},{passive:true});
 }
 return {order:order,targetPage:targetPage,shouldIgnore:shouldIgnore,attach:attach};
});
