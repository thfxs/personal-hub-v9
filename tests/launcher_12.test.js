const test=require('node:test'),assert=require('node:assert/strict');
const {parseIP,endpoint}=require('../web/bridge-launch.js');
test('accept RFC1918 addresses and loopback PC check',()=>{for(const s of ['10.0.0.2','172.16.1.15','172.31.255.254','192.168.1.88','127.0.0.1'])assert.equal(parseIP(s),s)});
test('block public or malformed IPv4 and URL injection',()=>{for(const s of ['8.8.8.8','172.32.1.2','169.254.1.1','192.168.1.999','192.168.1.1/abc','evil.example','192.168.001.1.example','::1'])assert.throws(()=>parseIP(s));});
test('normalize safe endpoint and require valid port',()=>{assert.equal(endpoint(' 192.168.0.3 ',' 8765 '),'https://192.168.0.3:8765/');for(const p of ['0','80','65536','8765/evil','-1'])assert.throws(()=>endpoint('192.168.0.3',p))});
