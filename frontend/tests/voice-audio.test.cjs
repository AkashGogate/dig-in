const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const {runInNewContext}=require('node:vm');
const window={};runInNewContext(readFileSync(join(__dirname,'../voice-audio.js'),'utf8'),{window,Int16Array});
const audio=window.DigInVoiceAudio;
const ctx=()=>({session:'s',actorId:'a',role:'server',view:'server',order:{id:'order-1',revision:2,menu_revision:'menu-1',status:'draft'},menuRevision:'active'});
test('capture pin rejects switching drafts, revisions, menus, sessions and views',()=>{
 const original=ctx(), pin=audio.pin('order',original);assert.ok(audio.matches(pin,original));
 for(const mutate of [c=>c.order.id='order-2',c=>c.order.revision++,c=>c.order.menu_revision='other',c=>c.session='different',c=>c.actorId='different',c=>c.view='kitchen']){const current=ctx();mutate(current);assert.equal(audio.matches(pin,current),false);}
});
test('kitchen capture requires its pinned menu and cook/lead session',()=>{
 const c={...ctx(),role:'cook',view:'kitchen'}, pin=audio.pin('kitchen',c);assert.ok(audio.matches(pin,c));c.menuRevision='new';assert.equal(audio.matches(pin,c),false);c.menuRevision='active';c.role='server';assert.equal(audio.matches(pin,c),false);
});
test('resampler emits declared mono PCM16 duration with clipped samples',()=>{
 const source=new Float32Array(48000).fill(2);const bytes=audio.pcm16(source,48000);assert.equal(bytes.byteLength,32000);assert.equal(new Int16Array(bytes)[0],32767);
 source.fill(-2);assert.equal(new Int16Array(audio.pcm16(source,48000))[0],-32768);assert.throws(()=>audio.pcm16(source,8000));
});
test('hosted empty API origin is preserved and late startup cannot clear a newer hold',async()=>{
 const source=readFileSync(join(__dirname,'../app.js'),'utf8');assert.ok(source.includes('window.DIG_IN_API ??'));
 const begin=source.slice(source.indexOf('function beginHold('),source.indexOf('function endHold('));
 const attempts=[],button={classList:{add(){},remove(){}},setAttribute(){}};
 const sandbox={busy:false,uncertain:null,session:'s',holding:false,captureEpoch:0,voice:{live:true},state:{orders:{o:{}}},draftId:'o',kitchenRole:()=>true,feedback(){},serviceCoordination:{stopSpeech(){}},captureUi:()=>({button,status:{textContent:''}}),startLive:()=>new Promise(resolve=>attempts.push(resolve))};
 runInNewContext(begin+';this.begin=beginHold;',sandbox);sandbox.begin();sandbox.holding=false;sandbox.begin();attempts[0](false);await Promise.resolve();assert.equal(sandbox.holding,true);attempts[1](true);await Promise.resolve();
});
test('protected backend 401 marks the shared backend offline',async()=>{
 const source=readFileSync(join(__dirname,'../app.js'),'utf8');
 const request=source.slice(source.indexOf('async function request('),source.indexOf('function setBusy('));
 let online=true;
 const sandbox={API:'',connected:ok=>online=ok,AbortController,setTimeout,clearTimeout,
  fetch:async()=>({status:401,ok:false,json:async()=>{throw new Error('plain text challenge');}})};
 runInNewContext(request+';this.call=request;',sandbox);
 await assert.rejects(sandbox.call('/api/v2/state'),error=>error.status===401);
 assert.equal(online,false);
});
