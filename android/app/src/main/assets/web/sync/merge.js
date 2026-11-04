/* Personal Hub 1.4: deterministic, explicit three-way record merge. No network I/O. */
(function(root,factory){var api=factory();if(typeof module!=='undefined'&&module.exports)module.exports=api;if(root)root.PersonalHubSyncMerge=api;})(typeof window!=='undefined'?window:this,function(){'use strict';
var FIELDS=['projects','tasks','business','jobs','ideas','health','links'];
function stable(v){
 if(v===null||typeof v!=='object')return JSON.stringify(v);
 if(Array.isArray(v))return '['+v.map(stable).join(',')+']';
 return '{'+Object.keys(v).sort().map(function(k){return JSON.stringify(k)+':'+stable(v[k]);}).join(',')+'}';
}
function equal(a,b){return stable(a)===stable(b);}
function validate(data){
 if(!data||typeof data!=='object'||Array.isArray(data)||data.version!==1||!data.settings||typeof data.settings!=='object'||Array.isArray(data.settings))throw Error('需要 Personal Hub v1 的完整数据结构');
 Object.keys(data).forEach(function(k){if(k==='__proto__'||k==='constructor'||k==='prototype')throw Error('业务数据包含危险顶层字段，拒绝同步');});
 FIELDS.forEach(function(k){var ids=Object.create(null);if(!Array.isArray(data[k])||data[k].length>20000)throw Error(k+' 数组无效');data[k].forEach(function(v){if(!v||typeof v!=='object'||typeof v.id!=='string'||!v.id||v.id.length>160||Object.prototype.hasOwnProperty.call(ids,v.id))throw Error(k+' 记录 ID 异常');ids[v.id]=1;});});
 return data;
}
function empty(){var out={version:1,settings:{motion:true,showClock:true},createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()};FIELDS.forEach(function(k){out[k]=[];});return out;}
function pick(b,l,r){if(equal(l,r))return{value:l};if(equal(l,b))return{value:r};if(equal(r,b))return{value:l};return{conflict:true};}
function mapOf(items){var m=Object.create(null);items.forEach(function(x){m[x.id]=x;});return m;}
function merge(local,remote,base,choices){
 validate(local);if(remote!==null)validate(remote);if(base!==null)validate(base);
 choices=choices||{};var fresh=remote===null,remoteData=remote||empty(),baseData=base||empty();
 var result={version:1,createdAt:local.createdAt||remoteData.createdAt||new Date().toISOString(),updatedAt:new Date().toISOString()};
 var conflicts=[],changes=0;
 var cs=pick(base===null?undefined:base.settings,local.settings,fresh?undefined:remoteData.settings);
 if(fresh)cs={value:local.settings};
 if(cs.conflict){var choice=choices.settings;if(choice==='local'||choice==='remote')cs={value:choice==='local'?local.settings:remoteData.settings};else conflicts.push({key:'settings',section:'settings',label:'系统设置',local:local.settings,remote:remoteData.settings});}
 result.settings=cs.value||local.settings;
 FIELDS.forEach(function(field){
  var lm=mapOf(local[field]),rm=mapOf(remoteData[field]),bm=mapOf(baseData[field]);
  var ids=Object.create(null);[].concat(local[field].map(function(x){return x.id;}),remoteData[field].map(function(x){return x.id;}),baseData[field].map(function(x){return x.id;})).forEach(function(id){ids[id]=true;});
  var out=[];
  Object.keys(ids).forEach(function(id){
   var l=lm[id],r=rm[id],b=base===null?undefined:bm[id];
   var choiceResult=fresh?{value:l}:pick(b,l,r),key=field+':'+id;
   if(choiceResult.conflict){
    var choice=choices[key];
    if(choice==='local'||choice==='remote')choiceResult={value:choice==='local'?l:r};
    else{conflicts.push({key:key,section:field,label:String((l||r||b||{}).title||(l||r||b||{}).position||(l||r||b||{}).company||id).slice(0,100),local:l||null,remote:r||null});return;}
   }
   if(choiceResult.value!==undefined){out.push(choiceResult.value);if(!equal(choiceResult.value,l))changes++;}
   else if(l!==undefined)changes++;
  });
  result[field]=out;
 });
 // Preserve unknown v1 extension fields instead of silently discarding them.
 var known={version:true,createdAt:true,updatedAt:true,settings:true};FIELDS.forEach(function(k){known[k]=true;});
 var extra=Object.create(null);
 [local,remoteData,baseData].forEach(function(d){Object.keys(d).forEach(function(k){if(!Object.prototype.hasOwnProperty.call(known,k))extra[k]=true;});});
 Object.keys(extra).forEach(function(k){
  var l=local[k],r=fresh?undefined:remoteData[k],b=base===null?undefined:baseData[k];
  var chosen=fresh?{value:l}:pick(b,l,r),ckey='extra:'+k;
  if(chosen.conflict){
   var c=choices[ckey];
   if(c==='local'||c==='remote')chosen={value:c==='local'?l:r};
   else{conflicts.push({key:ckey,section:'扩展字段',label:k,local:l===undefined?null:l,remote:r===undefined?null:r});return;}
  }
  if(chosen.value!==undefined)result[k]=chosen.value;
  if(!equal(chosen.value,l))changes++;
 });
 // Avoid a new revision for a no-op: only advance updatedAt when business data changed.
 function sameBusiness(a){
  if(!a||!equal(a.settings,result.settings))return false;
  for(var i=0;i<FIELDS.length;i++)if(!equal(a[FIELDS[i]],result[FIELDS[i]]))return false;
  for(var k of Object.keys(extra))if(!equal(a[k],result[k]))return false;
  return true;
 }
 if(!fresh&&sameBusiness(remoteData)){
  result.createdAt=remoteData.createdAt;result.updatedAt=remoteData.updatedAt;
 }else if(sameBusiness(local)){
  result.createdAt=local.createdAt;result.updatedAt=local.updatedAt;
 }
 return{result:result,conflicts:conflicts,localChanges:changes};
}
return {FIELDS:FIELDS,validate:validate,empty:empty,stable:stable,equal:equal,merge:merge};
});
