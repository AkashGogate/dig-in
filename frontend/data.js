/* UI branch integration seam. Backend snapshots are the only restaurant state.
 * No prototype fallback, automatic capture, browser persistence or legacy API.
 * Injectable fetch/clock/ID factories make the exact retry contract testable.
 */
(function (root) {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const editableLine = line => ({id:line.id, menu_id:line.menu_id, quantity:line.quantity, modifiers:[...line.modifiers], seat:line.seat, requests:line.requests});
  const menuFor = (state, order) => order ? state.menus?.[order.menu_revision] : state.menu;
  const ownOrders = (state, actor, kitchen=false) => Object.values(state.orders).filter(o => kitchen ? o.status !== 'draft' : o.owner === actor?.id);
  const unitsFor = (state, orderId) => Object.values(state.dishes).filter(d => d.order_id === orderId);
  function createClient({base = root.DIG_IN_API ?? 'http://localhost:8000', fetcher = root.fetch.bind(root), uuid = () => root.crypto.randomUUID(), now = () => new Date().toISOString(), timeoutMs = 10000} = {}) {
    let state = null, actor = null, session = null, busy = false, uncertain = null, online = false, generation = 0, auth = null, needsAuth = false;
    const listeners = new Set();
    const context = () => ({state,actor,session,busy,uncertain,online,generation,needsAuth});
    const emit = () => listeners.forEach(fn => fn(context()));
    async function request(path, options = {}) {
      const controller = new AbortController(), timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetcher(`${base.replace(/\/$/, '')}${path}`, {...options,headers:{...(auth?{Authorization:`Basic ${auth}`} : {}),...options.headers},signal:controller.signal});
        let data = null;
        try {data = await response.json();} catch (_) { /* Plaintext Basic challenges still require access UI. */ }
        if (!response.ok) {
          const error = new Error(`${response.status}: ${typeof data?.detail === 'string' ? data.detail : 'Request rejected; refresh and review.'}`);
          error.rejected = true; error.status = response.status; if(response.status===401) needsAuth = true; throw error;
        }
        if(data===null) throw new Error('Backend returned an unreadable response.');
        online = true; needsAuth = false; return data;
      } catch (error) { if (!error.rejected) online = false; throw error; }
      finally { clearTimeout(timer); }
    }
    async function refresh() {
      // A GET started during an in-flight POST may describe its older state.
      if (busy) return state;
      const before = generation;
      try { const snapshot = await request('/api/v2/state'); if (before === generation && !busy) state = snapshot; }
      finally { emit(); }
      return state;
    }
    async function authenticate(username,password) {
      if(busy) throw new Error('Wait for the current request to finish.');
      if(!username || username.includes(':') || !password) throw new Error('Enter a username and password.');
      const previous = auth;
      const bytes = new TextEncoder().encode(`${username}:${password}`);
      auth = root.btoa(String.fromCharCode(...bytes));
      busy=true;generation++;emit();
      try {state=await request('/api/v2/state');return state;} catch(error) {auth=previous;throw error;} finally {busy=false;emit();}
    }
    async function enter(actorId) {
      if (busy || uncertain) throw new Error('Resolve the pending command before switching sessions.');
      busy = true; generation++; emit();
      try {
        const data = await request('/api/v2/sessions', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_id:actorId})});
        actor = data.actor; session = data.session_id; return context();
      } finally {busy = false; emit();}
    }
    async function command(payload, retry=false) {
      if (!session || busy || (uncertain && !retry)) throw new Error('Enter a session and resolve any pending command first.');
      const attempt = retry ? uncertain : {session, envelope:{schema_version:2,event_id:uuid(),source:'tap',time:now(),run_id:'operator-pages',simulated:true,payload:JSON.parse(JSON.stringify(payload))}};
      if (!attempt || attempt.session !== session) throw new Error('Retry belongs to the original session.');
      busy = true; generation++; emit();
      try {
        const data = await request('/api/v2/commands', {method:'POST',headers:{'Content-Type':'application/json','X-Demo-Session':attempt.session},body:JSON.stringify(attempt.envelope)});
        uncertain = null; state = data.state; return data;
      } catch (error) {
        uncertain = error.rejected ? null : attempt;
        throw error;
      } finally { generation++; busy = false; emit(); }
    }
    async function summary(audience) {
      if (!session || busy || uncertain) throw new Error('Enter a session and resolve the pending command first.');
      const before = generation, token = session;
      const result = await request(`/api/v2/service/summary?audience=${encodeURIComponent(audience)}`, {headers:{'X-Demo-Session':token}});
      if (before !== generation || token !== session) return null;
      return result;
    }
    return {context, refresh, authenticate, enter, command, summary, retry:() => command(null,true), subscribe(fn) {listeners.add(fn); return () => listeners.delete(fn);}};
  }
  root.DigInOperator = {createClient,escape,editableLine,menuFor,ownOrders,unitsFor};
  if (typeof module !== 'undefined') module.exports = root.DigInOperator;
})(typeof window !== 'undefined' ? window : globalThis);
