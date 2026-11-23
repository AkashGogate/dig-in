const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const {runInNewContext}=require('node:vm');

const source=readFileSync(join(__dirname,'../app.js'),'utf8');
const slice=source.slice(source.indexOf('function speak('),source.indexOf('async function captureText('));

function load(extraSandbox={}) {
  const sandbox={window:{},...extraSandbox};
  runInNewContext(slice+';this.isNextTaskQuery=isNextTaskQuery;this.nextTaskAnswer=nextTaskAnswer;',sandbox);
  return sandbox;
}

test('isNextTaskQuery matches known phrasings and rejects order dictation',()=>{
  const {isNextTaskQuery}=load();
  for (const phrase of ["what's next", "what is my next", "next task please", "next dish", "next ticket", "what should I do next"]) {
    assert.ok(isNextTaskQuery(phrase), `expected match: ${phrase}`);
  }
  for (const phrase of ["table 4 one caesar salad", "ready", "start the salmon"]) {
    assert.equal(isNextTaskQuery(phrase), false, `expected no match: ${phrase}`);
  }
});

test('cook next task prioritizes an already-started dish over a queued one',()=>{
  const state={
    dishes:{d1:{stage:'queued',item_name:'Salmon',order_id:'o1'},d2:{stage:'started',item_name:'Salad',order_id:'o2'}},
    orders:{o1:{table_id:'4'},o2:{table_id:'7'}},
  };
  const {nextTaskAnswer}=load({state});
  assert.equal(nextTaskAnswer('cook','cook-1'), 'Finish Salad for table 7.');
});

test('cook falls back to queued dish when nothing is started',()=>{
  const state={dishes:{d1:{stage:'queued',item_name:'Salmon',order_id:'o1'}},orders:{o1:{table_id:'4'}}};
  const {nextTaskAnswer}=load({state});
  assert.equal(nextTaskAnswer('cook','cook-1'), 'Start Salmon for table 4.');
});

test('cook with no queued or started dishes gets the no-pending-tasks fallback',()=>{
  const state={dishes:{},orders:{}};
  const {nextTaskAnswer}=load({state});
  assert.equal(nextTaskAnswer('cook','cook-1'), 'No pending tasks right now.');
});

test('server next task prioritizes ready over flagged over draft, scoped to their own orders',()=>{
  const state={
    dishes:{},
    orders:{
      other:{owner:'someone-else',table_id:'1',status:'ready',lines:[],flags:[]},
      flagged:{owner:'server-1',table_id:'2',status:'submitted',lines:[],flags:[{id:'f1'}]},
      draft:{owner:'server-1',table_id:'3',status:'draft',lines:[{id:'l1'}],flags:[]},
    },
  };
  const {nextTaskAnswer}=load({state});
  // Only the flagged and draft orders belong to server-1; "other" must be ignored despite being ready.
  assert.equal(nextTaskAnswer('server','server-1'), 'Resolve a flag on the order for table 2.');
});

test('server falls back to draft when nothing is ready or flagged',()=>{
  const state={dishes:{},orders:{draft:{owner:'server-1',table_id:'3',status:'draft',lines:[{id:'l1'}],flags:[]}}};
  const {nextTaskAnswer}=load({state});
  assert.equal(nextTaskAnswer('server','server-1'), 'Send the draft order for table 3.');
});

test('lead sees both cook and server work, cook priority wins when both are pending',()=>{
  const state={
    dishes:{d1:{stage:'started',item_name:'Steak',order_id:'o1'}},
    orders:{o1:{table_id:'9'},o2:{owner:'lead-1',table_id:'2',status:'ready',lines:[],flags:[]}},
  };
  const {nextTaskAnswer}=load({state});
  assert.equal(nextTaskAnswer('lead','lead-1'), 'Finish Steak for table 9.');
});

test('no session state yet gives an explicit fallback instead of throwing',()=>{
  const {nextTaskAnswer}=load({state:null});
  assert.equal(nextTaskAnswer('cook','cook-1'), 'No session state yet.');
});
