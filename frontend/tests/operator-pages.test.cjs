const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const {runInNewContext}=require('node:vm');
const apiSandbox={module:{exports:{}},fetch,AbortController,setTimeout,clearTimeout,Date,crypto,TextEncoder,btoa};
runInNewContext(readFileSync(join(__dirname,'../data.js'),'utf8'),apiSandbox);
const {createClient,menuFor,ownOrders,editableLine}=apiSandbox.module.exports;
const reply=(data,status=200)=>({ok:status<400,status,json:async()=>structuredClone(data)});
const snapshot=()=>({menu_revision:'new',menu:{name:'New menu',items:[{id:'new_soup',name:'New soup'}]},menus:{old:{name:'Pinned menu',items:[{id:'the_bulldozer',name:'The Bulldozer',category:'Burgers',price_cents:1200,modifiers:[{id:'no_onion',name:'No onion'}]}]}},tables:{'1':{id:'1',seats:[1,2]}},actors:{'server-1':{id:'server-1',name:'Server One',role:'server'},'server-2':{id:'server-2',name:'Server Two',role:'server'},'cook-1':{id:'cook-1',name:'Cook',role:'cook'}},orders:{},dishes:{},zones:{A:{id:'A',occupancy:'empty',assignment_version:1,camera_id:'cam',dish_id:null}},cameras:{cam:{status:'offline',mode:'mock',reason:'Synthetic demo'}},service_updates:{},computed:{balances:{onion:4},expected_consumption:{onion:2}}});
const actor=id=>({id,name:id,role:id.startsWith('cook')?'cook':'server'});
function transport(state=snapshot()) {
 const calls=[];let id=0, fail=null;
 const fetcher=async(url,options={})=>{
  const body=options.body?JSON.parse(options.body):null;calls.push({url,options,body});
  if(fail){const problem=fail;fail=null;throw problem;}
  if(url.endsWith('/state'))return reply(state);
  if(url.endsWith('/sessions'))return reply({actor:actor(body.actor_id),session_id:`token-${body.actor_id}`});
  if(url.includes('/service/summary'))return reply({actor_id:'server-1',generated_at:'2026-11-14T22:00:00Z',text:'Table 1 ticket order-1: current summary.'});
  const p=body.payload;let result={};
  if(p.action==='start_order') {const orderId=`order-${++id}`;state.orders[orderId]={id:orderId,owner:'server-1',table_id:p.table_id,revision:1,status:'draft',menu_revision:'old',capture_mode:'manual',lines:[],flags:[]};result.order_id=orderId;}
  if(p.action==='edit_draft'){Object.assign(state.orders[p.order_id],{table_id:p.table_id,lines:p.lines,revision:p.revision+1});result.order_id=p.order_id;}
  if(p.action==='confirm_send'){state.orders[p.order_id].status='submitted';state.orders[p.order_id].revision++;result.order_id=p.order_id;}
  return reply({state,result,replayed:false});
 };
 return {state,calls,fetcher,failNext(error=new Error('connection lost')){fail=error;}};
}
function makeClient(t,extra={}) {return createClient({base:'',fetcher:t.fetcher,uuid:()=> 'stable-event',now:()=> '2026-11-14T22:00:00Z',...extra});}
test('hosted empty API base remains same-origin and outages never load prototype records',async()=>{
 const t=transport(),c=makeClient(t);await c.refresh();assert.equal(t.calls[0].url,'/api/v2/state');
 t.failNext();await assert.rejects(c.refresh());assert.equal(c.context().online,false);assert.equal(c.context().state.orders['fake-order'],undefined);
});
test('canonical IDs and old menu revision survive projections without current-menu substitution',()=>{
 const s=snapshot(),order={id:'o',owner:'server-1',menu_revision:'old',status:'draft'};s.orders={o:order,other:{...order,id:'other',owner:'server-2'}};
 assert.equal(menuFor(s,order).items[0].id,'the_bulldozer');assert.equal(menuFor(s,{menu_revision:'missing'}),undefined);assert.equal(JSON.stringify(ownOrders(s,actor('server-1')).map(o=>o.id)),JSON.stringify(['o']));
 const line={id:'line-7',menu_id:'the_bulldozer',quantity:2,seat:2,modifiers:['no_onion'],requests:'Peanut allergy',item_name:'discard transport snapshot label'};
 assert.deepEqual(JSON.parse(JSON.stringify(editableLine(line))),{id:'line-7',menu_id:'the_bulldozer',quantity:2,seat:2,modifiers:['no_onion'],requests:'Peanut allergy'});
});
test('uncertain command blocks new commands/session switches and retries its exact original envelope/session',async()=>{
 const t=transport(),c=makeClient(t);await c.refresh();await c.enter('server-1');
 const payload={action:'start_order',table_id:'1'};t.failNext();await assert.rejects(c.command(payload));payload.table_id='999';
 const original=t.calls.at(-1);assert.ok(c.context().uncertain);await assert.rejects(c.command({action:'start_order',table_id:'2'}));await assert.rejects(c.enter('server-2'));
 await c.refresh();await c.retry();const retry=t.calls.at(-1);assert.equal(retry.options.body,original.options.body);assert.equal(retry.options.headers['X-Demo-Session'],'token-server-1');assert.equal(retry.body.payload.table_id,'1');assert.equal(c.context().uncertain,null);
});
test('explicit HTTP conflict is rejected rather than retained as uncertain success',async()=>{
 const t=transport(),c=makeClient(t,{fetcher:async(url,options)=>url.endsWith('/commands')?reply({detail:'Draft revision changed'},409):t.fetcher(url,options)});
 await c.enter('server-1');await assert.rejects(c.command({action:'confirm_send',order_id:'o',revision:2,human_confirmed:true}),/409/);assert.equal(c.context().uncertain,null);
});
test('late state refresh cannot overwrite an accepted command snapshot',async()=>{
 const t=transport();let finish;const c=makeClient(t,{fetcher:(url,opts)=>url.endsWith('/state')?new Promise(resolve=>finish=resolve):t.fetcher(url,opts)});
 await c.enter('server-1');const pending=c.refresh();await c.command({action:'start_order',table_id:'1'});finish(reply(snapshot()));await pending;assert.ok(c.context().state.orders['order-1']);
});
test('summary is read-only/on-demand and a response after actor switch is discarded',async()=>{
 const t=transport();let finish;const c=makeClient(t,{fetcher:(url,opts)=>url.includes('/service/summary')?new Promise(resolve=>finish=resolve):t.fetcher(url,opts)});
 await c.enter('server-1');const pending=c.summary('server');await c.enter('server-2');finish(reply({text:'Old private summary'}));assert.equal(await pending,null);assert.equal(t.calls.filter(c=>c.url.endsWith('/commands')).length,0);
});
test('concurrent identity entry cannot race two sessions',async()=>{
 let finish;const c=createClient({base:'',fetcher:()=>new Promise(resolve=>finish=resolve)});const pending=c.enter('server-1');await assert.rejects(c.enter('server-2'));finish(reply({actor:actor('server-1'),session_id:'one'}));await pending;assert.equal(c.context().session,'one');
});

// Small dependency-free DOM harness: execute both real production modules and
// dispatch their actual delegated handlers. It is deliberately not a layout or
// browser substitute; root also exercises these pages against a live backend.
function pageHarness(page='order',state=snapshot()) {
 const t=transport(state),elements=new Map(),intervals=[],buttons=[],nodes=[];let currentTime=Date.parse('2026-11-14T22:10:00Z');
 const document={body:{dataset:{operatorPage:page}},activeElement:null,hidden:false,getElementById:id=>elements.get(id)||null,querySelectorAll:selector=>selector.includes('button')?buttons:selector==='[data-started]'?nodes.filter(n=>n.dataset.started):selector==='[data-submitted]'?nodes.filter(n=>n.dataset.submitted):[]};
 function element(tag='div',attributes='',inside=false) {
  const attrs=Object.fromEntries([...attributes.matchAll(/([\w-]+)(?:="([^"]*)")?/g)].map(m=>[m[1],m[2]??'']));
  const el={tagName:tag.toUpperCase(),id:attrs.id||'',dataset:Object.fromEntries(Object.entries(attrs).filter(([k])=>k.startsWith('data-')).map(([k,v])=>[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase()),v])),value:attrs.value||'',checked:'checked'in attrs,disabled:'disabled'in attrs,hidden:false,textContent:'',listeners:{},options:[],inside,
   classList:{toggle(){}},addEventListener(name,fn){this.listeners[name]=fn;},contains(other){return Boolean(other?.inside);},querySelectorAll(selector){return selector==='button'?buttons:[];},focus(){document.activeElement=this;},blur(){if(document.activeElement===this)document.activeElement=null;},setSelectionRange(){},closest(){return this;}};
  Object.defineProperty(el,'innerHTML',{get(){return this.html||'';},set(value){this.html=value;this.options=[...value.matchAll(/<option\b/g)];if(this.id==='operatorMain'){buttons.length=0;nodes.length=0;}for(const m of value.matchAll(/<(button|input|select|textarea|span|summary)\b([^>]*)>/g)){const node=element(m[1],m[2],this.id==='operatorMain'||this.inside);nodes.push(node);if(node.id)elements.set(node.id,node);if(m[1]==='button')buttons.push(node);}}});
  if(el.id)elements.set(el.id,el);return el;
 }
 const html=readFileSync(join(__dirname,`../${page==='order'?'server-order':page==='tables'?'server-tables':'kitchen'}.html`),'utf8');
 for(const m of html.matchAll(/<(button|select|div|span|form|input)\b([^>]*\bid="[^"]+"[^>]*)>/g))element(m[1],m[2]);
 const window={DIG_IN_API:'',fetch:t.fetcher,crypto:{randomUUID:()=>`line-${t.calls.length}`},btoa,addEventListener(){}};
 class TestDate extends Date {static now(){return currentTime;}}
 const sandbox={window,document,crypto:window.crypto,AbortController,setTimeout,clearTimeout,setInterval:fn=>intervals.push(fn),Date:TestDate,TextEncoder,confirm:()=>true,console};
 runInNewContext(readFileSync(join(__dirname,'../data.js'),'utf8'),sandbox);sandbox.DigInOperator=window.DigInOperator;
 runInNewContext(readFileSync(join(__dirname,'../operator-pages.js'),'utf8'),sandbox);
 const settle=()=>new Promise(resolve=>setImmediate(resolve));
 const click=async(name,id)=>{const button=buttons.find(b=>b.dataset.action===name&&(id===undefined||b.dataset.id===id));assert.ok(button,`Missing action ${name}/${id}`);assert.equal(button.disabled,false,`Disabled action ${name}`);await elements.get('operatorMain').listeners.click({target:button});await settle();};
 return {t,elements,document,buttons,nodes,intervals,settle,click,html:()=>elements.get('operatorMain').innerHTML,async enter(id=page==='kitchen'?'cook-1':'server-1'){await settle();elements.get('operatorActor').value=id;await elements.get('enterSession').listeners.click();await settle();},advance(ms){currentTime+=ms;intervals[1]();}};
}
test('real composer starts empty, saves canonical menu line, then one separate human confirm submits saved revision',async()=>{
 const h=pageHarness();await h.enter();assert.doesNotMatch(h.html(),/Salmon|Chicken bowl|Listening/);h.elements.get('newTable').value='1';await h.click('start');await h.click('add','the_bulldozer');
 let confirm=h.buttons.find(b=>b.dataset.action==='confirm');assert.equal(confirm.disabled,true);assert.equal(h.t.calls.filter(c=>c.body?.payload?.action==='confirm_send').length,0);
 await h.click('save');const saved=h.t.calls.find(c=>c.body?.payload?.action==='edit_draft').body.payload;assert.equal(saved.lines[0].menu_id,'the_bulldozer');assert.equal(saved.revision,1);assert.equal(saved.lines[0].seat,null);
 await h.click('confirm');const sent=h.t.calls.find(c=>c.body?.payload?.action==='confirm_send').body.payload;assert.equal(sent.revision,2);assert.equal(sent.human_confirmed,true);assert.equal(h.t.state.orders['order-1'].status,'submitted');
});
test('server table screen scopes tickets/updates and safely escapes staff-authored guest/update text',async()=>{
 const s=snapshot();s.orders={mine:{id:'mine',owner:'server-1',table_id:'1',status:'cooking'},other:{id:'other',owner:'server-2',table_id:'1',status:'cooking'}};
 s.dishes={d:{id:'d',line_id:'line',order_id:'mine',item_name:'<unsafe>',stage:'ready',zone_id:'A',requests:'<img onerror=x>',modifier_names:['No onion']}};s.zones.A.dish_id='d';
 s.service_updates={u:{id:'u',order_id:'mine',revision:3,kind:'pickup_request',note:'<script>bad</script>',recipient_id:'server-1',sender_id:'cook-1',status:'unread'}};
 const h=pageHarness('tables',s);await h.enter();assert.match(h.html(),/Ticket mine/);assert.doesNotMatch(h.html(),/Ticket other|<script>bad|<img onerror/);assert.match(h.html(),/&lt;script&gt;/);await h.click('acknowledge_service_update','u');const p=h.t.calls.at(-1).body.payload;assert.deepEqual(p,{action:'acknowledge_service_update',update_id:'u',revision:3});assert.equal(h.t.state.dishes.d.stage,'ready');
});
test('kitchen lineup preserves exact unit context and gates manual ready on current assignment/review',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'acknowledged',acknowledged_at:'2026-11-14T22:00:00Z',zone_status:'waiting'}};
 s.dishes={d:{id:'d',line_id:'line-1',order_id:'o',item_name:'The Bulldozer',stage:'queued',zone_id:null,seat:2,requests:'Nut allergy',modifier_names:['No onion'],typical_minutes:null}};
 const h=pageHarness('kitchen',s);await h.enter();assert.match(h.html(),/Seat 2/);assert.match(h.html(),/No onion/);assert.match(h.html(),/Nut allergy/);assert.match(h.html(),/Usual time unknown/);assert.ok(h.buttons.some(b=>b.dataset.action==='start_dish'));assert.ok(!h.buttons.some(b=>b.dataset.action==='ready_dish'));
 s.dishes.d.zone_id='A';s.zones.A.dish_id='d';s.zones.A.needs_review=true;await h.intervals[0]();await h.settle();assert.ok(!h.buttons.some(b=>b.dataset.action==='ready_dish'));assert.match(h.html(),/requires staff review/);
 s.zones.A.needs_review=false;await h.intervals[0]();await h.settle();assert.ok(h.buttons.some(b=>b.dataset.action==='ready_dish'));
});
test('polling preserves an active authored update field instead of discarding it',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'submitted'}};const h=pageHarness('kitchen',s);await h.enter();
 const input=h.elements.get('note-o');input.value='Guest needs a delay';input.focus();s.orders.o.status='acknowledged';await h.intervals[0]();await h.settle();assert.equal(h.elements.get('note-o'),input);assert.equal(input.value,'Guest needs a delay');
});
test('new page source loads only integrated modules and keeps prototype code unloaded',()=>{
 for(const name of ['server-order','server-tables','kitchen']){
  const text=readFileSync(join(__dirname,`../${name}.html`),'utf8');assert.match(text,/operator-pages\.js/);assert.doesNotMatch(text,/startMockRealtime|api\._mock|api\._bus|lucide|cdn\./);
 }
});

test('refresh during an in-flight command never issues a stale GET or overwrites the result',async()=>{
 const t=transport();let finish;const c=makeClient(t,{fetcher:(url,opts)=>url.endsWith('/commands')?new Promise(resolve=>finish=()=>resolve(t.fetcher(url,opts))):t.fetcher(url,opts)});
 await c.refresh();await c.enter('server-1');const pending=c.command({action:'start_order',table_id:'1'});const before=t.calls.length;await c.refresh();assert.equal(t.calls.length,before);finish();await pending;assert.ok(c.context().state.orders['order-1']);
});
test('authored kitchen note, kind and open panel survive polling after focus leaves',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'submitted'}};const h=pageHarness('kitchen',s);await h.enter();
 h.elements.get('note-o').value='Wait for guest';h.elements.get('kind-o').value='needs_attention';h.elements.get('operatorMain').listeners.input({target:h.elements.get('note-o')});
 h.elements.get('operatorMain').listeners.toggle({target:{dataset:{updateForm:'o'},open:true}});
 s.orders.o.status='acknowledged';await h.intervals[0]();await h.settle();assert.match(h.html(),/Wait for guest/);assert.match(h.html(),/value="needs_attention" selected/);assert.match(h.html(),/data-update-form="o" open/);
 await h.click('discard-update','o');assert.doesNotMatch(h.html(),/Wait for guest/);
});
test('unchanged kitchen polls advance elapsed time while preserving the focused unit action',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'cooking',acknowledged_at:'2026-11-14T22:00:00Z'}};
 s.dishes={d:{id:'d',line_id:'line',order_id:'o',item_name:'The Bulldozer',stage:'started',zone_id:'A',started_at:'2026-11-14T22:10:00Z',requests:'',modifier_names:[]}};s.zones.A.dish_id='d';
 const h=pageHarness('kitchen',s);await h.enter();const button=h.buttons.find(b=>b.dataset.action==='ready_dish');button.focus();const clock=h.nodes.find(n=>n.dataset.started);assert.equal(clock.textContent,'0 min elapsed');h.advance(61000);assert.equal(clock.textContent,'1 min elapsed');await h.intervals[0]();await h.settle();assert.equal(h.document.activeElement,button);assert.equal(h.nodes.find(n=>n.dataset.started),clock);
});

test('401 reveals the in-memory credential seam; success is only reported after backend verification',async()=>{
 const t=transport(),valid=`Basic ${btoa('demo:temporary')}`;
 const c=makeClient(t,{fetcher:(url,opts={})=>opts.headers?.Authorization===valid?t.fetcher(url,opts):Promise.resolve(reply({detail:'Demo sign-in required'},401))});
 await assert.rejects(c.refresh(),/401/);assert.equal(c.context().needsAuth,true);await assert.rejects(c.authenticate('demo','wrong'),/401/);assert.equal(c.context().needsAuth,true);
 await c.authenticate('demo','temporary');assert.equal(c.context().needsAuth,false);assert.ok(c.context().state);assert.equal('auth' in c.context(),false);await c.enter('server-1');assert.equal(t.calls.at(-1).options.headers.Authorization,valid);
});

test('plaintext HTTP Basic challenge still sets needsAuth and cannot fabricate verified access',async()=>{
 const c=createClient({base:'',fetcher:async()=>({ok:false,status:401,json:async()=>{throw new SyntaxError('plain response');}})});
 await assert.rejects(c.refresh(),/401/);assert.equal(c.context().needsAuth,true);await assert.rejects(c.authenticate('demo','invalid'),/401/);assert.equal(c.context().state,null);
});
test('ready units with no captured start event show unknown start time, not a fabricated not-started milestone',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'ready'}};s.dishes={d:{id:'d',order_id:'o',line_id:'line',item_name:'Soup',stage:'ready',zone_id:'A',requests:'',modifier_names:[]}};s.zones.A.dish_id='d';
 const h=pageHarness('tables',s);await h.enter();assert.match(h.html(),/Start time unknown/);assert.doesNotMatch(h.html(),/Not started/);
});

test('glanceable Kitchen sorts oldest sent first and only fully current-ready tickets get green accent',async()=>{
 const s=snapshot();s.orders={newer:{id:'newer',table_id:'1',owner:'server-1',status:'cooking',submitted_at:'2026-11-14T22:08:00Z'},older:{id:'older',table_id:'1',owner:'server-1',status:'ready',submitted_at:'2026-11-14T22:00:00Z'}};
 s.dishes={a:{id:'a',order_id:'older',line_id:'a',item_name:'Old dish',stage:'ready',zone_id:'A',requests:'',modifier_names:[]},b:{id:'b',order_id:'newer',line_id:'b',item_name:'New dish',stage:'started',requests:'',modifier_names:[]}};s.zones.A.dish_id='a';
 const h=pageHarness('kitchen',s);await h.enter();assert.ok(h.html().indexOf('data-ticket="older"')<h.html().indexOf('data-ticket="newer"'));assert.match(h.html(),/class="ticket allready" data-ticket="older"/);assert.doesNotMatch(h.html(),/class="ticket allready" data-ticket="newer"/);assert.match(h.html(),/Active units/);assert.doesNotMatch(h.html(),/>All day</);assert.match(h.html(),/1\/1 ready/);
 s.dishes.a.stage='picked_up';await h.intervals[0]();await h.settle();assert.doesNotMatch(h.html(),/class="ticket allready" data-ticket="older"/);
});
test('Kitchen station filter keeps full-ticket ready ratio and unit actions/context authoritative',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'cooking',acknowledged_at:'2026-11-14T22:00:00Z'}};s.dishes={a:{id:'a',order_id:'o',line_id:'a',item_name:'Grill unit',station:'grill',stage:'ready',zone_id:'A',requests:'Exact guest words',modifier_names:['No onion']},b:{id:'b',order_id:'o',line_id:'b',item_name:'Other unit',station:'oven',stage:'started',requests:'',modifier_names:[]}};s.zones.A.dish_id='a';
 const h=pageHarness('kitchen',s);await h.enter();const select=h.elements.get('stationFilter');select.value='grill';await h.elements.get('operatorMain').listeners.change({target:select});assert.match(h.html(),/1\/2 ready/);assert.match(h.html(),/ready count covers the full ticket/);assert.doesNotMatch(h.html(),/class="ticket allready"/);assert.match(h.html(),/Exact guest words/);assert.doesNotMatch(h.html(),/Other unit/);
});
test('Kitchen sent-age clocks advance without replacing focused actions and retain honest unknown age',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'submitted',submitted_at:'2026-11-14T22:01:00Z'},unknown:{id:'unknown',table_id:'1',owner:'server-1',status:'submitted'}};const h=pageHarness('kitchen',s);await h.enter();const clock=h.nodes.find(n=>n.dataset.submitted);assert.equal(clock.textContent,'9m since sent');const button=h.buttons.find(b=>b.dataset.action==='acknowledge');button.focus();h.advance(61000);assert.equal(clock.textContent,'10m since sent');assert.equal(h.document.activeElement,button);assert.match(h.html(),/Sent time unknown/);
});

test('ready stage count stays honest while reviewed or reassigned zones withhold actionable green accent',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'ready',submitted_at:'2026-11-14T22:00:00Z'},unknown:{id:'unknown',table_id:'1',owner:'server-1',status:'submitted',created_at:'2026-11-14T20:00:00Z'}};s.dishes={d:{id:'d',order_id:'o',line_id:'l',item_name:'Soup',stage:'ready',zone_id:'A',requests:'',modifier_names:[]}};s.zones.A.dish_id='d';s.zones.A.needs_review=true;
 const h=pageHarness('kitchen',s);await h.enter();assert.match(h.html(),/1\/1 ready/);assert.doesNotMatch(h.html(),/class="ticket allready"|class="ticket-ready-pill done"/);assert.ok(h.html().indexOf('data-ticket="o"')<h.html().indexOf('data-ticket="unknown"'));
 s.zones.A.needs_review=false;s.zones.A.dish_id='different';await h.intervals[0]();await h.settle();assert.doesNotMatch(h.html(),/class="ticket allready"/);assert.match(h.html(),/1\/1 ready/);
});

test('new Kitchen unit disclosure keeps open state and keyboard focus across changed polls',async()=>{
 const s=snapshot();s.orders={o:{id:'o',table_id:'1',owner:'server-1',status:'cooking'}};s.dishes={d:{id:'d',line_id:'line',order_id:'o',item_name:'Soup',stage:'started',requests:'',modifier_names:[]}};
 const h=pageHarness('kitchen',s);await h.enter();h.elements.get('operatorMain').listeners.toggle({target:{dataset:{unitDetails:'d'},open:true}});h.elements.get('unit-details-d').focus();s.orders.o.zone_status='waiting';await h.intervals[0]();await h.settle();assert.match(h.html(),/data-unit-details="d" open/);assert.equal(h.document.activeElement.id,'unit-details-d');assert.match(h.html(),/id="kitchen-summary-toggle"/);
});

test('grouped zone panels preserve exact tickets at the same table and every physical unassigned zone',async()=>{
 const s=snapshot();s.orders={one:{id:'one',table_id:'1',owner:'server-1',status:'cooking'},two:{id:'two',table_id:'1',owner:'server-1',status:'cooking'}};
 s.zones={A:{id:'A',order_id:'one',dish_id:'d1',camera_id:'cam',assignment_version:2,occupancy:'occupied'},B:{id:'B',order_id:'two',dish_id:'d2',camera_id:'cam',assignment_version:3,occupancy:'empty'},C:{id:'C',order_id:null,dish_id:null,camera_id:'cam',assignment_version:4,occupancy:'unknown',needs_review:true}};
 s.dishes={d1:{id:'d1',order_id:'one',zone_id:'A',line_id:'l1',item_name:'First',station:'grill',stage:'ready',requests:'',modifier_names:[]},d2:{id:'d2',order_id:'two',zone_id:'B',line_id:'l2',item_name:'Second',station:'oven',stage:'started',requests:'',modifier_names:[]}};
 const h=pageHarness('kitchen',s);await h.enter();const select=h.elements.get('stationFilter');select.value='grill';h.elements.get('operatorMain').listeners.change({target:select});await h.click('tab','zones');
 assert.match(h.html(),/Table 1 · ticket one/);assert.match(h.html(),/Table 1 · ticket two/);assert.match(h.html(),/Unassigned physical zones/);for(const id of ['A','B','C'])assert.equal((h.html().match(new RegExp(`data-physical-zone="${id}"`,'g'))||[]).length,1);
 assert.match(h.html(),/unknown · assignment v4/);assert.match(h.html(),/Camera: offline · mock/);assert.match(h.html(),/Requires review/);assert.match(h.html(),/1 ready for pickup/);
});
test('zone panel never paints reviewed or mismatched ready units green and escapes unknown ticket/health text',async()=>{
 const s=snapshot();s.zones={A:{id:'A',order_id:'<unknown>',dish_id:'d',camera_id:'cam',assignment_version:1,occupancy:'occupied',needs_review:true},B:{id:'B',order_id:'different-ticket',dish_id:'d',camera_id:'cam',assignment_version:2,occupancy:'unknown'}};
 s.dishes={d:{id:'d',order_id:'<unknown>',zone_id:'A',line_id:'l',item_name:'Ready dish',stage:'ready',requests:'',modifier_names:[]}};s.cameras.cam.reason='<img onerror=bad>';
 const h=pageHarness('kitchen',s);await h.enter();await h.click('tab','zones');assert.doesNotMatch(h.html(),/class="zone-tile ready"/);assert.match(h.html(),/0 ready for pickup/);assert.match(h.html(),/Unknown ticket &lt;unknown&gt;/);assert.match(h.html(),/Assignment mismatch/);assert.match(h.html(),/&lt;img onerror=bad&gt;/);assert.doesNotMatch(h.html(),/<img onerror/);
});
