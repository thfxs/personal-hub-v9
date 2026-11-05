/* Progressive UI enhancement: read already rendered, user-entered percentages.
 * Never changes personal records or application business logic.
 * No fake percentages for projects with unknown progress.
 */
(function(root,factory){
 'use strict';var api=factory(root);
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root&&root.document)api.attach(root);
})(typeof window!=='undefined'?window:null,function(win){
 'use strict';
 function progressFromText(text){
  var match=String(text||'').match(/进度[：:]\s*(\d+(?:\.\d+)?)\s*%/);
  if(!match)return null;
  var num=Number(match[1]);
  return isFinite(num)&&num>=0&&num<=100?num:null;
 }
 function progressFromEntry(node){
  var main=node.querySelector('.entry-main');
  var result=progressFromText(main?main.textContent:'');
  if(result!==null)return result;
  // Project summary cards from the original UI only have a proportional bar.
  var fill=node.querySelector('.dots .fill');
  if(fill){var width=String(fill.style.width||'');var value=Number(width.replace('%',''));
   if(width.slice(-1)==='%'&&isFinite(value)&&value>=0&&value<=100)return value;}
  return null;
 }
 function formatPercent(num){return Number(num.toFixed(1)).toString()+'%';}
 function buildRing(doc,progress,compact){
  var verified=progress!==null;
  var box=doc.createElement('div');
  box.className='ph-progress-ring'+(compact?' compact':'')+(verified?'':' unverified');
  var label=verified?formatPercent(progress):'—';
  box.setAttribute('role','img');box.setAttribute('aria-label',verified?'人工录入完成率 '+label:'完成率待录入');
  var pct=verified?progress:0;
  box.innerHTML='<svg viewBox="0 0 64 64" focusable="false" aria-hidden="true">'+
   '<circle class="ph-ring-track" cx="32" cy="32" r="25"/>'+
   '<circle class="ph-ring-arc" cx="32" cy="32" r="25" pathLength="100" stroke-dasharray="'+pct+' 100" transform="rotate(-90 32 32)"/>'+
   '</svg><span class="ph-ring-value">'+label+'</span>'+
   (verified?'':'<span class="ph-ring-unknown">待录入</span>');
  return box;
 }
 function decorate(root){
  if(!root||!root.querySelectorAll)return 0;
  var nodes=root.querySelectorAll('.entry');var added=0;
  for(var i=0;i<nodes.length;i++){
   var node=nodes[i];
   if(node.classList.contains('ph-progress-ready'))continue;
   // Only project cards carry the project edit action.
   var button=node.querySelector('[data-action="edit"][data-type="projects"]');
   if(!button)continue;
   var pct=progressFromEntry(node);var ring=buildRing(node.ownerDocument,pct,!node.querySelector('.entry-side'));
   node.classList.add('project-entry','ph-progress-ready');
   var bar=node.querySelector('.dots');if(bar)bar.parentNode.removeChild(bar);
   var side=node.querySelector('.entry-side');
   node.insertBefore(ring,side||button);added++;
  }
  return added;
 }
 function attach(w){
  var main=w.document.getElementById('main-content');if(!main)return;
  decorate(main);
  if(typeof w.MutationObserver==='function'){
   var obs=new w.MutationObserver(function(){decorate(main);});
   obs.observe(main,{childList:true,subtree:true});
  }
 }
 return {attach:attach,decorate:decorate,progressFromText:progressFromText,progressFromEntry:progressFromEntry,buildRing:buildRing};
});
