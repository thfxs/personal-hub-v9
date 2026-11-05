/* Personal Hub V9 landscape page fitting, 1.9.1.
 * Landscape: one viewport per subpage; data stays in the original JS store.
 * Portrait: original vertical scrolling. Modals keep their own scroll.
 * No timer/polling loop and no interception of vertical gestures.
 */
(function(root, factory){
 'use strict';
 var api=factory(root);
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root&&root.document)api.attach(root);
})(typeof window!=='undefined'?window:null,function(win){
 'use strict';
 var doc=win&&win.document, main, observer, live=false, raw='', currentModule='', currentIndex=0, pages=[], pending=false, resizeJob=0, gesture=null;
 function enabled(){return !!(win&&win.matchMedia&&win.matchMedia('(orientation: landscape)').matches&&win.innerHeight>=290&&win.innerWidth>=540);}
 function element(tag,cls){var n=doc.createElement(tag);if(cls)n.className=cls;return n;}
 function focusable(node){return !!(node&&node.closest&&node.closest('button,a,input,textarea,select,[contenteditable],.modal,[role="dialog"]'));}
 function countPerSlide(width,height){
  var cols=width>=570?2:1;
  // Do not force more rows than the available card heights can display.
  var rows=Math.max(1,Math.min(3,Math.floor((height+8)/100)));
  return {cols:cols,rows:rows,capacity:cols*rows};
 }
 function slide(className){return element('section','ph20-slide '+(className||''));}
 function setPage(idx){
  if(!pages.length)return;
  currentIndex=Math.min(pages.length-1,Math.max(0,idx));
  for(var i=0;i<pages.length;i++){
   var active=i===currentIndex;
   pages[i].hidden=!active;
   pages[i].setAttribute('aria-hidden',active?'false':'true');
  }
  var count=main.querySelector('.ph20-count'),prev=main.querySelector('.ph20-prev'),next=main.querySelector('.ph20-next');
  if(count)count.textContent=(currentIndex+1)+' / '+pages.length;
  if(prev)prev.disabled=currentIndex===0;
  if(next)next.disabled=currentIndex>=pages.length-1;
 }
 function makeControls(){
  var bar=element('div','ph20-controls');bar.setAttribute('aria-label','横屏内容翻页');
  var left=element('button','ph20-prev');left.type='button';left.textContent='← 上一页';left.setAttribute('aria-label','上一页');
  var label=element('span','ph20-count');label.setAttribute('aria-live','polite');
  var right=element('button','ph20-next');right.type='button';right.textContent='下一页 →';right.setAttribute('aria-label','下一页');
  bar.appendChild(left);bar.appendChild(label);bar.appendChild(right);return bar;
 }
 function overflowNote(text){var note=element('p','ph20-slide-tip');note.textContent=text;return note;}
 function makeGridSlides(source,available){
  var items=Array.prototype.slice.call(source.children);
  var layout=countPerSlide(main.clientWidth,available);
  for(var p=0;p<Math.max(1,Math.ceil(items.length/layout.capacity));p++){
   var s=slide('ph20-list-page');var grid=element('div','page-grid ph20-grid');
   grid.style.setProperty('--ph20-cols',String(layout.cols));
   grid.style.setProperty('--ph20-rows',String(layout.rows));
   items.slice(p*layout.capacity,(p+1)*layout.capacity).forEach(function(n){grid.appendChild(n);});
   s.appendChild(grid);pages.push(s);
  }
 }
 function makePanelSlides(panel,available,kind){
  var list=panel.querySelector('.entry-list');
  var rows=panel.querySelectorAll('.setting-row');
  var items=list?Array.prototype.slice.call(list.children):Array.prototype.slice.call(rows);
  var cols=main.clientWidth>=580?2:1;
  var itemHeight=kind==='settings'?97:69;
  var perSlide=Math.max(1,Math.floor((available-42+9)/itemHeight))*cols;
  if(!items.length)perSlide=1;
  for(var i=0;i<Math.max(1,Math.ceil(items.length/perSlide));i++){
   var copy=panel.cloneNode(true), bodyList=copy.querySelector('.entry-list'), settings=copy.querySelectorAll('.setting-row');
   var included=items.slice(i*perSlide,(i+1)*perSlide);
   if(bodyList){bodyList.innerHTML='';included.forEach(function(node){bodyList.appendChild(node.cloneNode(true));});bodyList.classList.add('ph20-entry-grid');}
   else if(settings.length){
    var wrap=element('div','ph20-settings-grid');
    Array.prototype.slice.call(settings).forEach(function(node){node.remove();});
    included.forEach(function(node){wrap.appendChild(node.cloneNode(true));});
    var head=copy.querySelector('.panel-head');if(head)head.insertAdjacentElement('afterend',wrap);
   }
   var s=slide('ph20-panel-page');copy.classList.add('ph20-filled-panel');
   if(items.length>perSlide){
    var tit=copy.querySelector('.panel-title');if(tit)tit.appendChild(doc.createTextNode(' · '+(i+1)+'/'+Math.ceil(items.length/perSlide)));
   }
   s.appendChild(copy);pages.push(s);
  }
 }
 function makeOverview(content,available){
  Array.prototype.slice.call(content.children).forEach(function(node){
   if(node.classList.contains('hero')){
    var s=slide('ph20-hero-page');s.appendChild(node);pages.push(s);
   }else if(node.classList.contains('grid-two')){
    Array.prototype.slice.call(node.children).forEach(function(panel){makePanelSlides(panel,available,'overview');});
   }else if(node.classList.contains('grid-three')){
    var group=slide('ph20-stats-page');group.appendChild(node);pages.push(group);
   }else{
    var other=slide();other.appendChild(node);pages.push(other);
   }
  });
 }
 function makeSettings(content,available){
  Array.prototype.slice.call(content.children).forEach(function(node){
   if(node.classList.contains('panel'))makePanelSlides(node,available,'settings');
   else if(node.textContent.trim()){
    var s=slide('ph20-note-page');s.appendChild(node);pages.push(s);
   }
  });
 }
 function unwrap(){
  if(!main||!live)return;
  main.classList.remove('ph20-active');
  main.innerHTML=raw;
  live=false;pages=[];
 }
 function build(){
  pending=false;if(!main)return;
  if(!enabled()){if(live)unwrap();return;}
  if(live){
   if(main.querySelector(':scope > .ph20-stage'))unwrap();
   else{live=false;pages=[];main.classList.remove('ph20-active');}
  }
  if(main.querySelector(':scope > .ph20-stage'))return;
  if(!main.children.length)return;
  raw=main.innerHTML;
  var active=doc.querySelector('#navigation .nav-item.active'),module=active?active.getAttribute('data-nav'):'overview';
  if(module!==currentModule){currentModule=module;currentIndex=0;}
  // Preserve focus and caret when an input causes re-rendering.
  var focused=doc.activeElement,focusId=focused&&focused.id,selectionStart=null;
  try{if(focused&&typeof focused.selectionStart==='number')selectionStart=focused.selectionStart;}catch(ignore){}
  var stage=element('div','ph20-stage'),fixed=element('div','ph20-fixed'),viewport=element('div','ph20-viewport'),controls=makeControls();
  var items=Array.prototype.slice.call(main.children);
  var content=element('div');
  for(var i=0;i<items.length;i++){
   var node=items[i];
   if(node.classList.contains('page-head')||node.classList.contains('toolbar')||node.classList.contains('data-warning'))fixed.appendChild(node);
   else content.appendChild(node);
  }
  stage.appendChild(fixed);stage.appendChild(viewport);stage.appendChild(controls);
  main.appendChild(stage);main.classList.add('ph20-active');
  var available=viewport.clientHeight;
  pages=[];
  if(module==='overview')makeOverview(content,available);
  else if(module==='settings')makeSettings(content,available);
  else{
   var grid=content.querySelector('.page-grid');
   if(grid)makeGridSlides(grid,available);
   else if(content.children.length){var other=slide();while(content.firstChild)other.appendChild(content.firstChild);pages.push(other);}
  }
  if(!pages.length){var fallback=slide();fallback.appendChild(overflowNote('当前页面暂无记录'));pages.push(fallback);}
  pages.forEach(function(s){viewport.appendChild(s);});
  live=true;
  setPage(currentIndex);
  if(focusId){var replacement=doc.getElementById(focusId);if(replacement&&focused!==replacement){replacement.focus();if(selectionStart!==null&&replacement.setSelectionRange)try{replacement.setSelectionRange(selectionStart,selectionStart);}catch(ignore){}}}
 }
 function schedule(){if(pending)return;pending=true;win.requestAnimationFrame(build);}
 function attach(w){
  if(!w||!w.document)return;
  main=w.document.getElementById('main-content');if(!main)return;
  observer=new w.MutationObserver(function(records){
   if(!enabled())return;
   if(!main.querySelector(':scope > .ph20-stage'))schedule();
  });
  observer.observe(main,{childList:true});
  main.addEventListener('click',function(ev){
   if(!live)return;
   if(ev.target.closest('.ph20-prev')){ev.stopPropagation();setPage(currentIndex-1);}
   if(ev.target.closest('.ph20-next')){ev.stopPropagation();setPage(currentIndex+1);}
  });
  main.addEventListener('touchstart',function(ev){
   gesture=null;
   if(!live||ev.touches.length!==1||focusable(ev.target))return;
   gesture={x:ev.touches[0].clientX,y:ev.touches[0].clientY,time:Date.now()};
  },true);
  main.addEventListener('touchend',function(ev){
   if(!live||!gesture||!ev.changedTouches.length)return;
   var dx=ev.changedTouches[0].clientX-gesture.x,dy=ev.changedTouches[0].clientY-gesture.y,dt=Date.now()-gesture.time;gesture=null;
   if(Math.abs(dx)<55||Math.abs(dx)<Math.abs(dy)*1.5||dt>1100)return;
   var nextIndex=currentIndex+(dx<0?1:-1);
   // At the subpage boundary, preserve the existing swipe-between-modules behavior.
   if(nextIndex<0||nextIndex>=pages.length)return;
   ev.stopImmediatePropagation();
   setPage(nextIndex);
  },true);
  main.addEventListener('touchcancel',function(){gesture=null;},true);
  main.addEventListener('keydown',function(ev){
   if(!live||focusable(ev.target)||ev.altKey||ev.metaKey||ev.ctrlKey)return;
   if(ev.key==='ArrowLeft'||ev.key==='ArrowRight'){
    ev.preventDefault();ev.stopPropagation();setPage(currentIndex+(ev.key==='ArrowRight'?1:-1));
   }
  });
  function resize(){win.clearTimeout(resizeJob);resizeJob=win.setTimeout(function(){if(enabled()||live)schedule();},130);}
  w.addEventListener('resize',resize);w.addEventListener('orientationchange',resize);
  schedule();
 }
 return {attach:attach,enabled:enabled,countPerSlide:countPerSlide};
});
