const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const {runInNewContext}=require('node:vm');
const source=readFileSync(join(__dirname,'../service-coordination.js'),'utf8');
const html=readFileSync(join(__dirname,'../index.html'),'utf8');
function setup(options={}) {
  const elements=new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(match=>[match[1],{value:'',disabled:false,hidden:false,textContent:'',innerHTML:'',listeners:{},addEventListener(name,fn){this.listeners[name]=fn;},focus(){this.focused=true;},async emit(name,event={preventDefault(){}}){return this.listeners[name]?.(event);}}]));
  const el=id=>{assert.ok(elements.has(id),`Missing actual element ${id}`);return elements.get(id);};
  const state={orders:{o1:{id:'o1',owner:'server-1',table_id:'1',status:'acknowledged'}},dishes:{d1:{id:'d1',order_id:'o1',item_name:'Soup',stage:'ready',zone_id:'A',station:null}},service_updates:{u1:{id:'u1',revision:1,order_id:'o1',kind:'pickup_request',note:'<img onerror=x>',recipient_id:'server-1',status:'unread'}},zones:{A:{}},cameras:{}};
  const context={state,actor:{id:'server-1',role:'server'},session:'token-1',view:'server',busy:false,uncertain:null,online:true};
  const requests=[],commands=[],spoken=[];let canceled=0,printed=0;
  const window={addEventListener(){},print(){printed++;},speechSynthesis:options.noSpeech?undefined:{cancel(){canceled++;},speak(value){spoken.push(value);}},SpeechSynthesisUtterance:function(text){this.text=text;}};
  const document={getElementById:el,activeElement:null};
  runInNewContext(source,{window,document,Date:options.Date || Date});
  const summary={generated_at:'2026-11-14T22:00:00Z',text:'Table 1, ticket o1: one unit ready for pickup.'};
  const controller=window.createServiceCoordination({getContext:()=>context,esc:value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),request:async(...args)=>{requests.push(args);return options.request?options.request(...args):summary;},dispatch:async payload=>{commands.push(payload);return {};}});
  return {el,document,context,controller,requests,commands,spoken,get canceled(){return canceled;},get printed(){return printed;}};
}
test('summary is explicit and never automatically spoken; speak is a separate action',async()=>{
 const h=setup();assert.equal(h.requests.length,0);assert.equal(h.spoken.length,0);
 await h.el('service-server-ask').emit('click');assert.equal(h.requests.length,1);assert.equal(h.spoken.length,0);
 assert.match(h.requests[0][0],/audience=server/);assert.match(h.el('service-server-summary').textContent,/ticket o1/);
 await h.el('service-server-speak').emit('click');assert.equal(h.spoken.length,1);
 await h.el('service-server-stop').emit('click');assert.equal(h.el('service-server-stop').disabled,true);
});
test('state changes cancel spoken output and block stale print/speech',async()=>{
 const h=setup();await h.el('service-server-ask').emit('click');await h.el('service-server-speak').emit('click');
 const before=h.canceled;h.context.state.dishes.d1.stage='picked_up';h.controller.sync();
 assert.ok(h.canceled>before);assert.match(h.el('service-server-summary-meta').textContent,/STALE/);
 await h.el('service-server-speak').emit('click');await h.el('service-server-print').emit('click');
 assert.equal(h.spoken.length,1);assert.equal(h.printed,0);
 assert.match(h.el('service-server-updates').innerHTML,/No ready units now/);
});
test('actor switch clears summaries and print material',async()=>{
 const h=setup();await h.el('service-server-ask').emit('click');await h.el('service-server-print').emit('click');assert.equal(h.printed,1);
 h.context.session='different';h.context.actor={id:'server-2',role:'server'};h.controller.sync();
 assert.match(h.el('service-server-summary').textContent,/Ask for a summary/);
 assert.equal(h.el('service-print-text').textContent,'');assert.equal(h.el('service-server-print').disabled,true);
 assert.ok(!h.el('service-server-updates').innerHTML.includes('u1'));
});
test('pending summary response is ignored after changing the active view',async()=>{
 let resolve;const h=setup({request:()=>new Promise(done=>{resolve=done;})});const pending=h.el('service-server-ask').emit('click');
 h.context.view='kitchen';h.controller.sync();resolve({text:'obsolete',generated_at:'2026-11-14T22:00:00Z'});await pending;
 assert.ok(!h.el('service-server-summary').textContent.includes('obsolete'));assert.equal(h.el('service-server-ask').disabled,false);
});
test('role, outage and uncertain-command states prevent new requests/actions',async()=>{
 const h=setup();await h.el('service-kitchen-ask').emit('click');assert.equal(h.requests.length,0);
 h.context.online=false;h.controller.sync();await h.el('service-server-ask').emit('click');assert.equal(h.requests.length,0);
 h.context.online=true;h.context.uncertain={payload:{action:'publish_service_update'}};h.controller.sync();await h.el('service-server-ask').emit('click');assert.equal(h.requests.length,0);
});
test('notes are escaped and kitchen publishes through shared dispatch',async()=>{
 const h=setup();assert.ok(!h.el('service-server-updates').innerHTML.includes('<img'));assert.match(h.el('service-server-updates').innerHTML,/&lt;img/);
 h.context.actor={id:'cook-1',role:'cook'};h.context.session='cook-token';h.context.view='kitchen';h.controller.sync();
 h.el('service-update-order').value='o1';h.el('service-update-kind').value='delay';h.el('service-update-note').value='Waiting on sauce';
 await h.el('service-update-form').emit('submit');assert.equal(h.commands.length,1);assert.equal(h.commands[0].action,'publish_service_update');assert.equal(h.commands[0].order_id,'o1');
});
test('unsupported speech retains displayed summary and printing',async()=>{
 const h=setup({noSpeech:true});await h.el('service-server-ask').emit('click');
 assert.equal(h.el('service-server-speak').disabled,true);assert.match(h.el('service-server-speech-note').textContent,/unavailable/);
 await h.el('service-server-print').emit('click');assert.equal(h.printed,1);
});

test('canonical lineup keeps per-unit modifiers, seat, guest request and unknown timing',()=>{
 const h=setup();Object.assign(h.context.state.dishes.d1,{seat:3,modifiers:['no_butter'],modifier_names:['No butter'],requests:'Severe allergy: check with guest'});h.controller.sync();
 const markup=h.el('service-kitchen-lineup').innerHTML;assert.match(markup,/seat 3/);assert.match(markup,/No butter/);assert.match(markup,/Severe allergy/);assert.match(markup,/Start time unknown/);assert.match(markup,/Typical time unknown/);
});
test('acknowledged waiting queued units can start, while ready still needs a zone',()=>{
 const h=setup();h.context.actor={id:'cook-1',role:'cook'};h.context.view='kitchen';Object.assign(h.context.state.dishes.d1,{stage:'queued',zone_id:null});h.controller.sync();
 assert.match(h.el('service-kitchen-lineup').innerHTML,/data-service-dish-action="start_dish"/);
 h.context.state.dishes.d1.stage='started';h.controller.sync();assert.ok(!h.el('service-kitchen-lineup').innerHTML.includes('data-service-dish-action="ready_dish"'));assert.match(h.el('service-kitchen-lineup').innerHTML,/Waiting for zone reservation/);
});
test('remote update refresh restores the focused update control',()=>{
 const h=setup(), old={dataset:{serviceAction:'acknowledge_service_update',updateId:'u1',revision:'1'}};let restored=false;
 const replacement={disabled:false,dataset:{...old.dataset},focus(){restored=true;}};
 h.document.activeElement=old;h.el('service-server-updates').contains=target=>target===old;h.el('service-server-updates').querySelectorAll=()=>[replacement];
 h.context.state.service_updates.u1.note='Updated staff note';h.controller.sync();assert.equal(restored,true);
});

test('lineup does not offer ready before unexpected-zone review',()=>{
 const h=setup();h.context.actor={id:'cook-1',role:'cook'};h.context.view='kitchen';h.context.state.dishes.d1.stage='started';h.context.state.zones.A.needs_review=true;h.controller.sync();
 assert.ok(!h.el('service-kitchen-lineup').innerHTML.includes('data-service-dish-action="ready_dish"'));assert.match(h.el('service-kitchen-lineup').innerHTML,/unexpected\/returned plate/);
});

test('unchanged polling advances elapsed text without replacing focused controls',()=>{
 let now=Date.parse('2026-11-14T22:00:00Z');class Clock extends Date {static now(){return now;}}
 const h=setup({Date:Clock}), container=h.el('service-kitchen-lineup');
 h.context.state.dishes.d1.started_at='2026-11-14T22:00:00Z';h.controller.sync();
 const timer={dataset:{serviceElapsed:'2026-11-14T22:00:00Z'},textContent:''};container.querySelectorAll=selector=>selector==='[data-service-elapsed]'?[timer]:[];
 let markup=container.innerHTML,replacements=0;Object.defineProperty(container,'innerHTML',{get(){return markup;},set(value){replacements++;markup=value;}});
 const focused={dataset:{serviceDishAction:'ready_dish',dishId:'d1'}};h.document.activeElement=focused;
 h.controller.sync();assert.equal(timer.textContent,'0 min elapsed');now+=120000;h.controller.sync();
 assert.equal(timer.textContent,'2 min elapsed');assert.equal(replacements,0);assert.equal(h.document.activeElement,focused);
});
