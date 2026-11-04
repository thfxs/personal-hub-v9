'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const G=require('../safety/guard-core.js');
const good={dbName:'personal_hub_v9',stores:[{name:'kv',keyPath:'key',autoIncrement:false,rows:[{key:'main',value:{key:'main',value:{projects:[{id:'a',title:'材料管家'}]}}}]}],localStorageValue:null};
test('CRC32 standard ASCII test vector',()=>assert.equal(G.crc32('123456789'),'cbf43926'));
test('CRC32 matches UTF-8 implementation for Chinese characters',()=>{
 const s='中文数据🔒';const expected=require('node:zlib').crc32(Buffer.from(s,'utf8')).toString(16).padStart(8,'0');assert.equal(G.crc32(s),expected);
});
test('wrap and validate snapshot',()=>{const s=G.wrapSnapshot(good,'manual');assert.equal(G.validateSnapshot(s).reason,'manual');});
test('reject checksum corruption',()=>{const s=G.wrapSnapshot(good,'manual');s.payload.stores[0].rows[0].value.value.projects[0].title='坏记录';assert.throws(()=>G.validateSnapshot(s),/校验失败/);});
test('reject different database',()=>{assert.throws(()=>G.wrapSnapshot({...good,dbName:'other'}),/不是当前/);});
test('reject cyclic and unserializable values',()=>{let x={};x.self=x;assert.throws(()=>G.safeJSON(x),/循环引用/);assert.throws(()=>G.safeJSON({v:new Map()}),/非 JSON/);assert.throws(()=>G.safeJSON({v:undefined}),/无法安全/);});
test('detect duplicate store names',()=>{const s=G.wrapSnapshot(good);s.payload.stores.push({...s.payload.stores[0]});s.crc32=G.crc32(JSON.stringify(s.payload));assert.throws(()=>G.validateSnapshot(s),/格式错误/);});
test('plaintext export and import round-trip',async()=>{const s=G.wrapSnapshot(good);const raw=await G.exportSnapshot(s);const back=await G.importSnapshot(raw);assert.deepEqual(back,s);});
test('reject malformed backup',async()=>{await assert.rejects(G.importSnapshot('{"kind":"else"}'),/不是 Personal/);});
test('encrypted export and import plus wrong password',async()=>{
 if(!G.cryptoReady())return;
 const pass='example-strong-passphrase-2026';const s=G.wrapSnapshot(good);
 const enc=await G.exportSnapshot(s,pass);const envelope=JSON.parse(enc);
 assert.equal(envelope.cipher,'AES-256-GCM');assert.equal(typeof envelope.snapshot,'undefined');
 assert.deepEqual(await G.importSnapshot(enc,pass),s);
 await assert.rejects(G.importSnapshot(enc,'wrong-passphrase'),/无法解密/);
});
test('app database identifier stable',()=>assert.equal(G.APP_DB,'personal_hub_v9'));
