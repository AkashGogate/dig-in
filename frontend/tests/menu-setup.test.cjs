const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');

const source = readFileSync(join(__dirname, '../menu-setup.js'), 'utf8');
const html = readFileSync(join(__dirname, '../index.html'), 'utf8');
const candidate = () => ({
  candidate_id:'candidate-1', expected_menu_revision:'old', menu_revision:'new',
  menu:{name:'Cafe', ingredient_zones:{}, items:[{id:'soup', name:'Tomato soup', aliases:['soup'], modifiers:[], description:'Roasted tomatoes', category:null, price_cents:null, recipe:null, station:null, typical_minutes:null, call_out_name:null}]},
  index:{item_count:1,semantic:false}, warnings:[], import_status:{missing_kitchen_fields:{soup:['station','recipe']}},
});
function setup(options = {}) {
  const elements = new Map([...html.matchAll(/\bid="([^"]+)"/g)].map(match => [match[1], {
    value:'', checked:false, hidden:false, disabled:false, textContent:'', innerHTML:'', files:[],
    classList:{toggle(){}}, listeners:{}, attrs:{},
    addEventListener(event, handler) { this.listeners[event] = handler; },
    setAttribute(key, value) { this.attrs[key] = value; },
    removeAttribute(key) { delete this.attrs[key]; },
    focus() { this.focused = true; },
    async emit(event) { return this.listeners[event]?.({preventDefault(){}}); },
  }]));
  const el = id => { assert.ok(elements.has(id), `Missing real HTML element ${id}`); return elements.get(id); };
  el('menu-format').value='text/plain'; el('menu-content').value='Tomato soup | Roasted tomatoes';
  const context = {state:{menu_revision:'old',menu:{name:'Current menu',items:[]}}, actor:{role:'lead'}, session:'lead-token', online:true, busy:false, uncertain:null};
  const requests = [], commands = [];
  const window = {};
  runInNewContext(source, {window, document:{getElementById:el}, Intl});
  const view = window.createMenuSetup({
    getContext:() => context,
    esc:value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])),
    request:async (...args) => {requests.push(args); return options.request ? options.request(...args) : candidate();},
    dispatch:async payload => {commands.push(payload); return options.dispatch ? options.dispatch(payload,context) : null;},
  });
  return {el,context,view,requests,commands};
}

test('upload automatically encodes, while review is required before activation', async () => {
  const h=setup();
  h.el('menu-upload').files=[{name:'cafe.csv',size:42,text:async ()=>'name,description\nTomato soup,Roasted tomatoes'}];
  await h.el('menu-upload').emit('change');
  assert.equal(h.requests.length,1);
  const body=JSON.parse(h.requests[0][1].body);
  assert.equal(body.media_type,'text/csv'); assert.equal(body.name,'cafe');
  assert.equal(h.el('menu-preview').hidden,false);
  assert.equal(h.el('menu-activate').disabled,true);
  await h.el('menu-activate').emit('click'); assert.equal(h.commands.length,0);
  h.el('menu-reviewed').checked=true; await h.el('menu-reviewed').emit('change');
  assert.equal(h.el('menu-activate').disabled,false);
  await h.el('menu-activate').emit('click');
  assert.equal(h.commands.length,1);
  assert.equal(h.commands[0].action,'activate_menu'); assert.equal(h.commands[0].human_confirmed,true);
});

test('editing prepared input invalidates the reviewed candidate immediately', async () => {
  const h=setup(); await h.el('menu-import-form').emit('submit');
  h.el('menu-reviewed').checked=true; await h.el('menu-reviewed').emit('change');
  h.el('menu-content').value='A different menu'; await h.el('menu-content').emit('input');
  assert.equal(h.el('menu-preview').hidden,true); assert.equal(h.el('menu-reviewed').checked,false);
  await h.el('menu-activate').emit('click'); assert.equal(h.commands.length,0);
});

test('another device changing the active menu blocks stale activation', async () => {
  const h=setup(); await h.el('menu-import-form').emit('submit');
  h.el('menu-reviewed').checked=true; await h.el('menu-reviewed').emit('change');
  h.context.state.menu_revision='other-device'; h.view.sync();
  assert.equal(h.el('menu-activate').disabled,true);
  assert.match(h.el('menu-activation-gate').textContent,/active menu changed/);
  await h.el('menu-activate').emit('click'); assert.equal(h.commands.length,0);
});

test('lead permission and connectivity gates prevent preparation and activation', async () => {
  const h=setup(); h.context.actor={role:'server'}; h.view.sync();
  assert.equal(h.el('menu-permission').hidden,false); assert.equal(h.el('menu-input-fields').disabled,true);
  await h.el('menu-import-form').emit('submit'); assert.equal(h.requests.length,0);
  h.context.actor={role:'lead'}; h.context.online=false; h.view.sync();
  await h.el('menu-import-form').emit('submit'); assert.equal(h.requests.length,0);
});

test('encoding response from a previous session is discarded', async () => {
  let resolve;
  const h=setup({request:() => new Promise(done => {resolve=done;})});
  const pending=h.el('menu-import-form').emit('submit');
  assert.equal(h.el('menu-input-panel').attrs['aria-busy'],'true');
  h.context.session='other-token'; h.context.actor={role:'server'}; h.view.sync();
  resolve(candidate()); await pending;
  assert.equal(h.el('menu-preview').hidden,true); assert.equal(h.el('menu-activate').disabled,true);
});

test('encoding errors preserve input and leave activation unavailable', async () => {
  const h=setup({request:async () => {throw Object.assign(new Error('bad input'),{rejected:true,detail:'Invalid menu input'});}});
  await h.el('menu-import-form').emit('submit');
  assert.equal(h.el('menu-content').value,'Tomato soup | Roasted tomatoes');
  assert.match(h.el('menu-setup-status').textContent,/Invalid menu input/);
  assert.equal(h.el('menu-activate').disabled,true);
});

test('uncertain activation directs exact retry and accepts its eventual result', async () => {
  const h=setup({dispatch:async (payload,context) => {context.uncertain={payload};}});
  await h.el('menu-import-form').emit('submit'); h.el('menu-reviewed').checked=true; await h.el('menu-reviewed').emit('change');
  await h.el('menu-activate').emit('click');
  assert.match(h.el('menu-setup-status').textContent,/Retry last event/);
  assert.equal(h.el('menu-prepare').disabled,true);
  await h.el('menu-activate').emit('click'); assert.equal(h.commands.length,1);
  h.context.uncertain=null; h.context.state.menu_revision='new';
  h.view.accepted({},h.commands[0]);
  assert.match(h.el('menu-setup-status').textContent,/now active/);
  assert.equal(h.el('menu-review-confirmation').hidden,true);
});

test('unsupported or oversized files clear previous input and never encode', async () => {
  for (const file of [{name:'menu.exe',size:20},{name:'menu.txt',size:500000}]) {
    const h=setup(); h.el('menu-upload').files=[file]; await h.el('menu-upload').emit('change');
    assert.equal(h.requests.length,0); assert.equal(h.el('menu-content').value,'');
    assert.equal(h.el('menu-preview').hidden,true);
  }
});

test('preview escapes uploaded markup and shows missing data and alias warnings', async () => {
  const preview=candidate(); preview.menu.items[0].name='<img src=x onerror=alert(1)>';
  preview.warnings=[{alias:'special',candidates:['soup']}];
  const h=setup({request:async () => preview}); await h.el('menu-import-form').emit('submit');
  assert.ok(!h.el('menu-preview-items').innerHTML.includes('<img'));
  assert.match(h.el('menu-preview-items').innerHTML,/&lt;img/);
  assert.match(h.el('menu-preview-items').innerHTML,/Still unknown/);
  assert.equal(h.el('menu-matching-warnings').hidden,false);
});
