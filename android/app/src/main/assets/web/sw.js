/* Personal Hub 1.4 integration baseline, static shell only. No private-data caching. */
var CACHE='personal-hub-shell-v17';
var SHELL=['./','./index.html','./styles.css','./app.js','./manifest.webmanifest',
 './assets/icon.svg','./assets/icon-192.png','./assets/icon-512.png',
 './native-file.js','./swipe-nav.js','./remote.html','./remote.js','./device.html','./device.js',
 './bridge-launch.html','./bridge-launch.css','./bridge-launch.js',
 './safety/safety.html','./safety/safety.css','./safety/safety-ui.js',
 './safety/guard-core.js','./safety/guard-auto.js',
 './diag/v9-check.html','./diag/v9-check.js',
 './ops/index.html','./ops/ops.css','./ops/ops.js','./ops/logic.js',
 './sync/index.html','./sync/sync.css','./sync/merge.js','./sync/sync.js','./sync/native-transport.js'];
var SCOPE=new URL('./',self.registration.scope).pathname;
self.addEventListener('install',function(event){
 event.waitUntil(caches.open(CACHE).then(function(cache){return cache.addAll(SHELL);}).then(function(){return self.skipWaiting();}));
});
self.addEventListener('activate',function(event){
 event.waitUntil(caches.keys().then(function(keys){return Promise.all(keys.filter(function(k){return k.indexOf('personal-hub-shell-')===0 && k!==CACHE;}).map(function(k){return caches.delete(k);}));}).then(function(){return self.clients.claim();}));
});
self.addEventListener('fetch',function(event){
 var req=event.request,url=new URL(req.url);
 if(req.method!=='GET'||url.origin!==self.location.origin||url.pathname.indexOf(SCOPE)!==0)return;
 // Never store fetch responses containing personal API data or backups.
 var path='./'+url.pathname.slice(SCOPE.length);
 if(!SHELL.some(function(x){return x==='./'||x===path;}))return;
 if(req.mode==='navigate'){
  event.respondWith(fetch(req).then(function(resp){if(resp.ok){var copy=resp.clone();caches.open(CACHE).then(function(c){return c.put(req,copy);}).catch(function(){});}return resp;}).catch(function(){return caches.match(req).then(function(m){return m||caches.match('./index.html');});}));
  return;
 }
 event.respondWith(caches.match(req).then(function(found){return found||fetch(req);}));
});
