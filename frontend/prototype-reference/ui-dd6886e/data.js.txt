// data.js — single data layer for all three screens
// Set USE_REAL_API = true and wire API_BASE once backend endpoints exist.
// Missing endpoints that need implementation:
//   GET /menu, GET /tables, POST /orders, GET /orders?server_id=X,
//   PATCH /dishes/:id, GET /orders (kitchen), POST /orders/:id/confirm,
//   WS /ws/kitchen, WS /ws/server/:id, GET /ingredients
//
// IMPORTANT: every state change — real realtime OR a simulated test event —
// is applied through the `bus.*` appliers below, so simulated events travel
// the exact same path (mutate state → _emit) as real ones. See INTEGRATION.md.
const USE_REAL_API = false;
const API_BASE = (typeof window !== 'undefined' && window.KITCHEN_COPILOT_API) || 'http://localhost:8000';

// ── Mock state ────────────────────────────────────────────────────────────────

const _mock = {
  server: { id: 'srv-1', name: 'Alex' },

  // Device status (surfaced in the UI)
  mic_status:    'listening', // listening | paused | processing | offline
  camera_status: 'live',      // live | offline

  // Take-order live transcript line
  transcript: 'two backhoes for seat one',

  // Kitchen "Last heard" strip — each voice command + its result
  last_heard: [
    { id: 'lh-0', cmd: 'order table 12', result: 'Zones 12·1 to 12·4 queued', dishId: null, prevStatus: null },
  ],

  // Camera clarification cards (unexpected plate / removal)
  clarifications: [
    { id: 'clar-seed', zone: '9·2', kind: 'placed', text: 'Plate seen in Zone 9·2, which dish?' },
  ],

  // Dig In — The Construction Kitchen menu
  menu: [
    // 01 / Groundwork — Appetizers
    { id: 'tots',    name: 'Gravel Pit Tots',  price:  9.00, category: 'Appetizers', station: 'Fry',   prep_seconds: 300, desc: 'Crispy tots buried under queso, bacon, and scallions.' },
    { id: 'beams',   name: 'Steel Beams',      price:  8.00, category: 'Appetizers', station: 'Fry',   prep_seconds: 240, desc: 'Golden mozzarella sticks with marinara for dipping.' },
    { id: 'poppers', name: 'Dynamite Poppers', price: 10.00, category: 'Appetizers', station: 'Grill', prep_seconds: 360, desc: 'Bacon-wrapped jalapeños stuffed with cream cheese.' },
    // 02 / Heavy Lifting — Mains
    { id: 'bulldozer', name: 'The Bulldozer',    price: 16.00, category: 'Mains', station: 'Grill', prep_seconds: 480, desc: 'Double smash burger, cheddar, crispy onions, pickles, house sauce.' },
    { id: 'backhoe',   name: 'The Backhoe',      price: 15.00, category: 'Mains', station: 'Grill', prep_seconds: 540, desc: 'BBQ pulled pork on a toasted bun with slaw and pickles.' },
    { id: 'macmixer',  name: 'Cement Mixer Mac', price: 13.00, category: 'Mains', station: 'Saute', prep_seconds: 420, desc: 'Three-cheese macaroni with a crunchy breadcrumb topping.' },
    // 03 / Finishing Touches — Desserts
    { id: 'dirtsite', name: 'Dirt Site',            price: 8.00, category: 'Desserts', station: 'Pantry', prep_seconds: 180, desc: 'Chocolate pudding, Oreo soil, gummy worms, and a shovel spoon.' },
    { id: 'brownie',  name: 'Wrecking Ball Brownie', price: 9.00, category: 'Desserts', station: 'Pantry', prep_seconds: 240, desc: 'Warm fudge brownie, chocolate ice cream, and caramel.' },
  ],

  orders: [
    {
      id: 'ord-t4', table: 4, server_id: 'srv-1', delivery_mode: 'as_ready',
      status: 'in_queue', elapsed_s: 405,
      dishes: [
        { id: 'd4-1', k: 1, name: 'The Bulldozer',    seat: 1, modifiers: '', allergy: '', station: 'Grill', zone: '4·1', status: 'ready',   est_min: null, source: 'camera', note: 'Server alerted 1:50 ago' },
        { id: 'd4-2', k: 2, name: 'Cement Mixer Mac', seat: 1, modifiers: '', allergy: '', station: 'Saute', zone: '4·2', status: 'cooking', est_min: 5,    source: null,     note: 'Started by saute'  },
      ],
    },
    {
      id: 'ord-t12', table: 12, server_id: 'srv-1', delivery_mode: 'all_together',
      status: 'partially_ready', elapsed_s: 500,
      dishes: [
        { id: 'd12-1', k: 1, name: 'The Bulldozer',    seat: 1, modifiers: 'No onion', allergy: '',            station: 'Grill', zone: '12·1', status: 'ready',   est_min: null, source: 'camera', note: '' },
        { id: 'd12-2', k: 2, name: 'Cement Mixer Mac', seat: 2, modifiers: '',         allergy: 'Nut allergy', station: 'Saute', zone: '12·2', status: 'cooking', est_min: 3,    source: null,     note: '' },
        { id: 'd12-3', k: 3, name: 'The Bulldozer',    seat: 3, modifiers: 'Medium',   allergy: '',            station: 'Grill', zone: '12·3', status: 'ready',   est_min: null, source: 'tapped', note: '' },
        { id: 'd12-4', k: 4, name: 'The Backhoe',      seat: 2, modifiers: '',         allergy: '',            station: 'Grill', zone: '12·4', status: 'ready',   est_min: null, source: 'camera', note: '' },
      ],
    },
    {
      id: 'ord-t7', table: 7, server_id: 'srv-1', delivery_mode: 'all_together',
      status: 'submitted', elapsed_s: 60,
      dishes: [
        { id: 'd7-1', k: 1, name: 'The Bulldozer',   seat: 1, modifiers: '', allergy: '', station: 'Grill', zone: '7·1', status: 'queued', est_min: null, source: null, note: '' },
        { id: 'd7-2', k: 2, name: 'Gravel Pit Tots', seat: 2, modifiers: '', allergy: '', station: 'Fry',   zone: '7·2', status: 'queued', est_min: null, source: null, note: '' },
      ],
    },
    {
      id: 'ord-t9', table: 9, server_id: 'srv-2', delivery_mode: 'all_together',
      status: 'submitted', elapsed_s: 30,
      dishes: [
        { id: 'd9-1', k: 1, name: 'The Backhoe',      seat: 1, modifiers: '', allergy: '', station: 'Grill', zone: '9·1', status: 'queued',  est_min: null, source: null, note: '' },
        { id: 'd9-2', k: 2, name: 'Cement Mixer Mac', seat: 2, modifiers: '', allergy: '', station: 'Saute', zone: '9·2', status: 'cooking', est_min: 4,    source: null, note: '' },
        { id: 'd9-3', k: 3, name: 'Dynamite Poppers', seat: 3, modifiers: '', allergy: '', station: 'Grill', zone: '9·3', status: 'queued',  est_min: null, source: null, note: '' },
      ],
    },
  ],

  // Orders heard by head chef voice but not yet line-confirmed
  heard_orders: [
    { id: 'heard-t7', raw: 'Order table 7', table: 7, items: ['The Bulldozer', 'Gravel Pit Tots'], delivery_mode: 'all_together' },
  ],

  // Per-ingredient camera counts: expected vs seen leaving the pass vs in stock
  ingredients: [
    { name: 'Smash patties', expected: 5, seen: 4, stock: 18 },
    { name: 'Pulled pork',   expected: 2, seen: 1, stock:  9 },
    { name: 'Brioche buns',  expected: 5, seen: 4, stock: 22 },
    { name: 'Mac & cheese',  expected: 2, seen: 1, stock: 14 },
    { name: 'Tots',          expected: 3, seen: 3, stock: 30 },
  ],
};

// ── Event bus ─────────────────────────────────────────────────────────────────

const _listeners = {};

function on(event, cb) {
  _listeners[event] = _listeners[event] || [];
  _listeners[event].push(cb);
  return () => { _listeners[event] = _listeners[event].filter(f => f !== cb); };
}

function _emit(event, data) {
  (_listeners[event] || []).forEach(cb => cb(data));
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function _findDish(dishId) {
  for (const o of _mock.orders) {
    const d = o.dishes.find(d => d.id === dishId);
    if (d) return { dish: d, order: o };
  }
  return { dish: null, order: null };
}

function _nextDishByStatus(status) {
  for (const o of _mock.orders) {
    const d = o.dishes.find(d => d.status === status);
    if (d) return d.id;
  }
  return null;
}

function _zoneRange(order) {
  const zones = order.dishes.map(d => d.zone);
  if (zones.length <= 1) return zones.join('');
  return `${zones[0]} to ${zones[zones.length - 1]}`;
}

function _pushLastHeard(cmd, result, meta = {}) {
  const entry = { id: 'lh-' + Date.now() + '-' + Math.floor(Math.random() * 1000), cmd, result, ...meta };
  _mock.last_heard.unshift(entry);
  _mock.last_heard = _mock.last_heard.slice(0, 8);
  _emit('last_heard', entry);
  return entry;
}

function _maybeServerAlert(order, readyDish) {
  if (order.delivery_mode === 'as_ready') {
    _emit('server_alert', {
      table: order.table, order_id: order.id,
      zones: readyDish ? [readyDish.zone] : [],
      dishes: readyDish ? [readyDish] : [],
      all_ready: false,
    });
  } else { // all_together
    const allReady = order.dishes.every(d => d.status === 'ready');
    if (allReady) {
      _emit('server_alert', {
        table: order.table, order_id: order.id,
        zones: order.dishes.map(d => d.zone),
        zone_range: _zoneRange(order),
        dishes: order.dishes.slice(),
        all_ready: true,
      });
    }
  }
}

// ── Appliers (the single path: mutate state → emit) ───────────────────────────
// Both the realtime mock timeline and api.sim.* call these.

const bus = {
  // Take order: head chef voice transcription heard
  voiceHeard(text, parsed) {
    _mock.transcript = text;
    if (_mock.mic_status !== 'offline') _mock.mic_status = 'listening';
    _emit('voice_transcript', { text, mic_status: _mock.mic_status });
    if (parsed) _emit('voice_item', parsed); // {name, seat, qty}
  },

  micStatus(status) {
    _mock.mic_status = status;
    _emit('mic_status', status);
  },

  cameraStatus(status) {
    _mock.camera_status = status;
    _emit('camera_status', status);
  },

  // Kitchen: head chef calls out a whole order to the line
  headChefCallout(heard) {
    _mock.heard_orders.push(heard);
    _pushLastHeard(`callout: ${heard.raw}`, `Table ${heard.table} awaiting confirm`, {});
    _emit('heard_order', heard);
  },

  // Station starts cooking a dish
  stationStarted(dishId) {
    const { dish, order } = _findDish(dishId);
    if (!dish || dish.status === 'ready') return;
    const prev = dish.status;
    dish.status = 'cooking';
    _pushLastHeard(`starting ${dish.zone}`, `Zone ${dish.zone} cooking`, { dishId, prevStatus: prev });
    _emit('dish_update', { dish, order });
  },

  // Camera (or tap) marks a plate ready in its zone
  plateReady(dishId, source) {
    const { dish, order } = _findDish(dishId);
    if (!dish || dish.status === 'ready') return;
    const prev = dish.status;
    dish.status = 'ready'; dish.est_min = null; dish.source = source;
    order.status = order.dishes.every(d => d.status === 'ready') ? 'ready' : 'partially_ready';
    const how = source === 'camera' ? 'plate seen' : 'marked ready';
    _pushLastHeard(`${how} ${dish.zone}`, `Zone ${dish.zone} ready`, { dishId, prevStatus: prev });
    _emit('dish_ready', { dish, order, source });
    _emit('dish_update', { dish, order });
    _maybeServerAlert(order, dish);
  },

  // Camera sees an unexpected plate in a zone → clarification card
  plateUnexpected(zone) {
    const c = { id: 'clar-' + Date.now(), zone, kind: 'placed', text: `Plate seen in Zone ${zone}, which dish?` };
    _mock.clarifications.push(c);
    _emit('clarification', c);
  },

  // Camera sees a plate removed unexpectedly → clarification card
  plateRemoved(zone) {
    const c = { id: 'clar-' + Date.now(), zone, kind: 'removed', text: `Plate removed from Zone ${zone}, which dish?` };
    _mock.clarifications.push(c);
    _emit('clarification', c);
  },

  resolveClarification(id) {
    _mock.clarifications = _mock.clarifications.filter(c => c.id !== id);
    _emit('clarification_resolved', id);
  },

  // Undo a "last heard" result (reverts the dish)
  undoLastHeard(id) {
    const entry = _mock.last_heard.find(e => e.id === id);
    if (!entry) return;
    if (entry.dishId && entry.prevStatus != null) {
      const { dish, order } = _findDish(entry.dishId);
      if (dish) {
        dish.status = entry.prevStatus;
        if (entry.prevStatus !== 'ready') dish.source = null;
        _emit('dish_update', { dish, order });
      }
    }
    _mock.last_heard = _mock.last_heard.filter(e => e.id !== id);
    _emit('last_heard_undo', id);
  },
};

// ── HTTP helpers ──────────────────────────────────────────────────────────────

async function _get(path) {
  if (!USE_REAL_API) return null;
  try { const r = await fetch(API_BASE + path); return r.ok ? r.json() : null; } catch { return null; }
}
async function _post(path, body) {
  if (!USE_REAL_API) return null;
  try {
    const r = await fetch(API_BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return r.ok ? r.json() : null;
  } catch { return null; }
}
async function _patch(path, body) {
  if (!USE_REAL_API) return null;
  try {
    const r = await fetch(API_BASE + path, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return r.ok ? r.json() : null;
  } catch { return null; }
}

// ── Public API ────────────────────────────────────────────────────────────────

const api = {
  getServer() { return _mock.server; },

  getMicStatus()    { return _mock.mic_status; },
  getCameraStatus() { return _mock.camera_status; },
  getTranscript()   { return _mock.transcript; },
  getLastHeard()    { return _mock.last_heard; },
  getClarifications() { return _mock.clarifications; },

  async getMenu() { return (await _get('/menu')) || _mock.menu; },

  async getTables() { return (await _get('/tables')) || Array.from({ length: 20 }, (_, i) => i + 1); },

  async submitOrder(payload) {
    const result = await _post('/orders', payload);
    if (result) return result;
    const id = 'ord-t' + payload.table + '-' + Date.now();
    const newOrder = {
      id, table: payload.table, server_id: payload.server_id,
      delivery_mode: payload.delivery_mode, status: 'submitted', elapsed_s: 0,
      dishes: payload.dishes.map((d, i) => ({
        id: `${id}-d${i + 1}`, k: i + 1, name: d.name, seat: d.seat,
        modifiers: d.modifiers || '', allergy: d.allergy_note || '',
        station: d.station || '?', zone: `${payload.table}·${i + 1}`,
        status: 'queued', est_min: null, source: null, note: '',
      })),
    };
    _mock.orders.push(newOrder);
    _emit('order_submitted', newOrder);
    return newOrder;
  },

  async getMyOrders(serverId) {
    return (await _get(`/orders?server_id=${serverId}`)) || _mock.orders.filter(o => o.server_id === serverId);
  },

  async getKitchenQueue() { return (await _get('/orders')) || _mock.orders; },

  async getHeardOrders() { return _mock.heard_orders; },

  async confirmHeardOrder(heardId) {
    await _post(`/heard/${heardId}/confirm`, {});
    _mock.heard_orders = _mock.heard_orders.filter(h => h.id !== heardId);
    _emit('heard_confirmed', heardId);
    return { ok: true };
  },

  async markPickedUp(dishId) {
    await _patch(`/dishes/${dishId}`, { status: 'picked_up' });
    for (const o of _mock.orders) {
      const d = o.dishes.find(d => d.id === dishId);
      if (d) { d.status = 'picked_up'; _emit('dish_update', { dish: d, order: o }); break; }
    }
  },

  async markServed(dishId) {
    await _patch(`/dishes/${dishId}`, { status: 'served' });
    for (const o of _mock.orders) {
      const d = o.dishes.find(d => d.id === dishId);
      if (d) { d.status = 'served'; _emit('dish_update', { dish: d, order: o }); break; }
    }
  },

  // Line marks a cooking dish ready by hand (used when camera is offline)
  async markDishReady(dishId) {
    await _patch(`/dishes/${dishId}`, { status: 'ready', source: 'tapped' });
    bus.plateReady(dishId, 'tapped');
  },

  async getIngredients() { return (await _get('/ingredients')) || _mock.ingredients; },

  // Confirm a voice item on the take-order screen (dashed blue → solid)
  acceptVoiceItem(payload) { _emit('voice_item_accepted', payload); },

  // Resolve a camera clarification card
  resolveClarification(id) { bus.resolveClarification(id); },

  // Undo a kitchen "last heard" result
  undoLastHeard(id) { bus.undoLastHeard(id); },

  // ── Test-event simulators — all route through `bus.*`, same as real events ──
  // Handy for manual/automated testing without a backend. See INTEGRATION.md §6.
  sim: {
    voiceHeard() {
      const lines = [
        { text: 'two backhoes for seat one', parsed: { name: 'The Backhoe', seat: 1, qty: 2 } },
        { text: 'add gravel pit tots for seat two', parsed: { name: 'Gravel Pit Tots', seat: 2, qty: 1 } },
        { text: 'cement mixer mac for seat three, extra crispy', parsed: { name: 'Cement Mixer Mac', seat: 3, qty: 1, modifiers: 'Extra crispy' } },
      ];
      const pick = lines[Math.floor(Math.random() * lines.length)];
      bus.voiceHeard(pick.text, pick.parsed);
    },
    headChefCallout() {
      const n = 2 + Math.floor(Math.random() * 18);
      bus.headChefCallout({ id: 'heard-' + Date.now(), raw: `Order table ${n}`, table: n, items: ['The Bulldozer', 'Dirt Site'], delivery_mode: 'all_together' });
    },
    stationStarted() { const id = _nextDishByStatus('queued'); if (id) bus.stationStarted(id); },
    plateInZone()    { const id = _nextDishByStatus('cooking'); if (id) bus.plateReady(id, 'camera'); },
    plateRemoved()   { bus.plateRemoved('9·2'); },
    plateUnexpected(){ bus.plateUnexpected('9·2'); },
    cameraOffline()  { bus.cameraStatus(_mock.camera_status === 'offline' ? 'live' : 'offline'); },
    micOffline()     { bus.micStatus(_mock.mic_status === 'offline' ? 'listening' : 'offline'); },
  },

  // Expose mock state + bus for screens that need raw access
  _mock,
  _bus: bus,
};

// ── Mock real-time: simulate a dish completing mid-demo ───────────────────────

function startMockRealtime() {
  // After 8s: 12-2 (Chicken bowl) goes ready via the camera path →
  // Table 12 becomes fully ready → server alert fires. Same path as a real event.
  setTimeout(() => {
    const { dish } = _findDish('d12-2');
    if (dish && dish.status === 'cooking') bus.plateReady('d12-2', 'camera');
  }, 8000);
}
