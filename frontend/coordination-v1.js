/* Plain-JS client. Executable shapes live in backend/app/coordination/contracts.py.
 * Shared backend state is authoritative; no localStorage orders or inventory.
 */
"use strict";
const API = (window.DIG_IN_API || "http://localhost:8000").replace(/\/$/, "");
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const money = cents => new Intl.NumberFormat("en-US", {style:"currency", currency:"USD"}).format(cents / 100);
const human = text => String(text || "").replaceAll("_", " ");
const uid = () => globalThis.crypto?.randomUUID?.() || `web-${Date.now()}-${Math.random().toString(36).slice(2)}`;
let state = null, actor = null, session = null, busy = false, uncertain = null;
let draftId = "", draftSignature = "", bootstrap = false, currentView = "server";
let suggestion = null, lastConnection = false;

function feedback(text, error = false) {
  $("feedback").textContent = text;
  $("feedback").classList.toggle("error", error);
}
function connection(ok) {
  lastConnection = ok;
  $("connection").textContent = ok ? "Shared backend connected" : "Backend unavailable · UNSYNCED";
  $("connection").style.color = ok ? "var(--green)" : "var(--danger)";
}
async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${API}${path}`, {...options, signal:controller.signal});
    const data = await res.json();
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
      const error = new Error(`${res.status}: ${detail}`);
      error.rejected = true;
      throw error;
    }
    connection(true);
    return data;
  } catch (error) {
    if (!error.rejected) connection(false);
    throw error;
  } finally { clearTimeout(timer); }
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll("[data-command]").forEach(button => button.disabled = value || !session || Boolean(uncertain));
  $("retry").disabled = value;
}
async function dispatch(payload, source = "manual", existing = null) {
  if (!session) { feedback("Enter a simulated staff session first.", true); return null; }
  if (busy || (uncertain && !existing)) { feedback("Resolve the uncertain command with Retry before sending another change.", true); return null; }
  const command = existing || {id:uid(),schema_version:1,source,kind:payload.action === "observe" ? "observation" : "command",occurred_at:new Date().toISOString(),device_id:"web-demo",payload};
  setBusy(true);
  feedback("Sending to shared backend…");
  try {
    const section = $("section-only").checked && actor.section !== "all" ? `?section=${encodeURIComponent(actor.section)}` : "";
    const data = await request(`/api/v1/commands${section}`, {method:"POST",headers:{"Content-Type":"application/json","X-Demo-Session":session},body:JSON.stringify(command)});
    uncertain = null;
    $("retry-bar").hidden = true;
    state = data.state;
    if (payload.action === "start_order") {
      draftId = data.result?.order_id || Object.values(state.orders).find(o => o.owner === actor.id && o.status === "draft" && !state.orders[draftId])?.id || draftId;
      suggestion = data.result?.positioning;
    }
    render();
    feedback(payload.action === "confirm_send" ? "Order sent. Kitchen acknowledgment is a separate next step." : "Change accepted by the shared backend.");
    return data;
  } catch (error) {
    if (!error.rejected) { uncertain = command; $("retry-bar").hidden = false; }
    feedback(error.rejected ? `${error.message}. Refresh state and review before trying again.` : "Connection interrupted. Your command may have arrived; nothing is assumed saved. Retry uses the same event ID.", true);
    return null;
  } finally { setBusy(false); }
}
async function refresh() {
  if (busy) return;
  try {
    const section = $("section-only").checked && actor && actor.section !== "all" ? `?section=${encodeURIComponent(actor.section)}` : "";
    state = await request(`/api/v1/state${section}`);
    render();
  } catch (error) {
    if (!state) $("draft-summary").textContent = `Cannot reach ${API}. Start the backend, then Refresh. No orders are stored only in this browser.`;
    if (lastConnection) feedback("Shared state is unavailable. Keep draft edits visible and reconnect; offline transactions are not supported.", true);
  }
}
function fillSelect(id, options, placeholder) {
  const el = $(id), before = el.value;
  el.innerHTML = (placeholder !== undefined ? `<option value="">${esc(placeholder)}</option>` : "") + options.map(([value,label]) => `<option value="${esc(value)}">${esc(label)}</option>`).join("");
  if ([...el.options].some(option => option.value === before)) el.value = before;
}
function orderDishes(orderId) { return Object.values(state.dishes).filter(d => d.order_id === orderId); }
function taskBlockers(task) { const computed = state.computed?.task_blockers?.[task.id]; return Array.isArray(computed) ? computed : task.blocker ? [task.blocker] : []; }
function render() {
  if (!state) return;
  if (!bootstrap) {
    const tables = Object.values(state.tables).map(t => [t.id, `Table ${t.id} · ${t.section}`]);
    ["start-table","draft-table","request-table"].forEach(id => fillSelect(id,tables));
    fillSelect("menu",Object.values(state.menu).map(m => [m.id,`${m.name} · ${money(m.price_cents)}`]));
    fillSelect("stock-zone",Object.values(state.zones).map(z => [z.id,`${z.ingredient} · ${z.unit}`]));
    refreshModifiers(); refreshSeats(); bootstrap = true;
  }
  renderDraft();
  renderUnlessFocused("task-panel", renderTasks);
  renderUnlessFocused("tickets", renderTickets);
  renderUnlessFocused("bays", renderBays);
  renderUnlessFocused("server-orders", renderServerOrders);
  renderOverview();
  setBusy(busy);
}
function renderUnlessFocused(id, fn) {
  const active = document.activeElement, container = $(id);
  if (container.contains(active) && ["INPUT","SELECT","TEXTAREA"].includes(active.tagName)) return;
  const data = container.contains(active) && active.matches("button") ? {...active.dataset} : null;
  fn();
  if (data) [...container.querySelectorAll("button")].find(b => Object.entries(data).every(([k,v])=>b.dataset[k]===v))?.focus({preventScroll:true});
}
function renderDraft() {
  const drafts = Object.values(state.orders).filter(o => o.status === "draft" && o.owner === actor?.id);
  fillSelect("draft-select",drafts.map(o => [o.id,`Table ${o.table_id || "unselected"} · ${o.id.slice(0,8)} · r${o.revision}`]),"Choose a draft");
  if (!drafts.some(o => o.id === draftId)) draftId = drafts[0]?.id || "";
  $("draft-select").value = draftId;
  const order = state.orders[draftId];
  $("editor").hidden = !order;
  if (!order) { $("draft-summary").innerHTML = '<p class="empty">No draft selected. Start with a table above.</p>'; draftSignature = ""; return; }
  const signature = JSON.stringify(order);
  if (signature === draftSignature) return;
  draftSignature = signature;
  $("draft-summary").innerHTML = `<div class="draft-title"><strong>Table ${esc(order.table_id || "—")}</strong><span class="status">Draft · revision ${order.revision}</span></div>${lineList(order)}<p class="note">Ticket ${esc(order.id)} · never submitted by speech</p>`;
  $("draft-table").value = order.table_id || "";
  fillSelect("edit-line",order.lines.map(l => [l.id,`Seat ${l.seat} · ${state.menu[l.menu_id]?.name || l.menu_id}`]),"New dish line");
  refreshSeats();
  if (suggestion) $("position-hint").textContent = `MOCK suggestion: table ${suggestion.suggested_table_id || "unavailable"}. ${suggestion.reason || "Review manually before sending."} The displayed table is manually correctable.`;
  $("send-note").textContent = `Review table ${order.table_id || "—"}, ${order.lines.reduce((n,l)=>n+l.quantity,0)} dishes, seats and requests. This tap approves revision ${order.revision}; it does not authorize payment.`;
  const p = order.proposal;
  $("proposal").innerHTML = p ? `<div class="proposal"><strong>${p.question ? "Clarification needed" : "Proposed correction — not applied"}</strong><p>${p.question ? esc(p.question) : `${esc(p.line_id)}: quantity ${order.lines.find(l=>l.id===p.line_id)?.quantity ?? "?"} → <strong>${p.quantity}</strong>`}</p><p class="note">Transcript: ${esc(p.transcript)}</p>${!p.question && p.quantity ? `<button data-action="accept" data-id="${esc(p.id)}" data-command>Accept correction for review</button>` : ""} <button data-action="keep-draft" data-command>Keep current entries</button></div>` : "";
}
function lineList(order) {
  if (!order.lines.length) return '<p class="empty">Add a dish line. Nothing has been sent.</p>';
  return order.lines.map(l => `<div class="order-line"><div><strong>${l.quantity} × ${esc(state.menu[l.menu_id]?.name || l.menu_id)}</strong><small>Seat ${l.seat} · ${esc(l.course)}${l.modifiers.length ? ` · ${esc(l.modifiers.join(", "))}` : ""}</small>${l.requests ? `<small><strong>Guest request:</strong> ${esc(l.requests)}</small>` : ""}</div><span class="price">${money((state.menu[l.menu_id]?.price_cents || 0) * l.quantity)}</span></div>`).join("");
}
function refreshSeats() {
  const table = state?.tables[$("draft-table").value || $("start-table").value];
  fillSelect("seat",(table?.seats || [1,2,3,4]).map(n=>[n,`Seat ${n}`]));
}
function refreshModifiers() {
  fillSelect("modifier",(state?.menu[$("menu").value]?.modifiers || []).map(m=>[m,m]),"No modifier");
}
function loadLine() {
  const line = state.orders[draftId]?.lines.find(l=>l.id===$("edit-line").value);
  $("seat").value = line?.seat || 1;
  $("menu").value = line?.menu_id || Object.keys(state.menu)[0];
  $("quantity").value = line?.quantity || 1;
  $("course").value = line?.course || "main";
  $("requests").value = line?.requests || "";
  refreshModifiers(); [...$("modifier").options].forEach(o=>o.selected=Boolean(line?.modifiers.includes(o.value)));
}
function renderTasks() {
  const ranked = state.computed?.ranked_tasks || Object.values(state.tasks).filter(t=>t.status === "available").slice(0,3);
  const rankIds = new Set(ranked.map(t=>t.id));
  $("ranked-tasks").innerHTML = ranked.length ? ranked.map(taskMarkup).join("") : '<p class="empty">No available tasks. Ready food and requests appear here.</p>';
  const others = Object.values(state.tasks).filter(t=>!["cancelled","completed"].includes(t.status) && !rankIds.has(t.id));
  $("other-tasks").innerHTML = others.length ? others.map(taskMarkup).join("") : '<p class="note">No open claims or helper requests.</p>';
}
function taskMarkup(task) {
  const blockers = taskBlockers(task), mine = task.owner === actor?.id;
  const helpers = task.helper_slots || [], joined = helpers.includes(actor?.id);
  const buttons = [];
  const button = (operation,label) => `<button class="small" data-action="task" data-operation="${operation}" data-id="${esc(task.id)}" data-command>${label}</button>`;
  if (task.status === "available") buttons.push(button("claim","Claim task"));
  if (mine) {
    buttons.push(button("release","Release"));
    if (task.type !== "food_run") buttons.push(button("complete","Complete"));
    if (task.type === "food_run" && !blockers.length && task.dish_ids.some(id=>state.dishes[id]?.stage === "ready")) buttons.push(`<button class="small primary" data-action="pickup" data-id="${esc(task.id)}" data-command>Confirm pickup</button>`);
    buttons.push(button("helpers","Ask 1 additional helper"),button("split","Split delivery / clear helper need"),button("block","Block"),button("cancel","Cancel"));
  }
  if (task.owner && !mine && helpers.some(h=>!h)) buttons.push(button("join","Join as helper"));
  if (joined) buttons.push(button("leave","Leave helper slot"));
  if (actor?.role === "lead") buttons.push(button("urgent","Shift-lead urgency"));
  const names = helpers.map(h=>h ? state.actors[h]?.name || h : "Open slot").join(" · ");
  return `<article class="task"><div class="task-head"><h3>Table ${esc(task.table_id)} · ${human(task.type)}</h3><span class="status">${esc(task.status)}</span></div><p>${esc(task.priority_reason)} · ${esc(task.section)}</p><p>${task.owner ? `Claimed by ${esc(state.actors[task.owner]?.name || task.owner)}` : "Available to staff"} · ${Math.max(0,Math.floor((Date.now()-Date.parse(task.created_at))/60000))}m waiting</p>${helpers.length ? `<p>Additional helpers: ${esc(names)}</p>` : ""}${blockers.length ? `<p class="blocker">Waiting: ${esc(blockers.join("; "))}</p>` : ""}<div class="actions">${buttons.join("")}</div></article>`;
}
function renderServerOrders() {
  const orders = Object.values(state.orders).filter(o=>o.status !== "draft" && (o.owner === actor?.id || actor?.role === "lead"));
  $("server-orders").innerHTML = orders.length ? orders.map(o=>`<article class="ticket"><div class="ticket-heading"><h3>Table ${esc(o.table_id)} · ${esc(state.computed?.ticket_stages?.[o.id] || o.status)}</h3><small>${esc(o.id)} · ${o.acknowledged ? "Kitchen acknowledged" : "Awaiting kitchen acknowledgment"}</small></div>${orderDishes(o.id).map(d=>dishMarkup(d,false)).join("")}</article>`).join("") : '<p class="empty">Your submitted tickets will appear here. Served needs an explicit staff confirmation.</p>';
}
function dishMarkup(d,kitchen) {
  const stages = {queued:"preparing",preparing:"partially_plated",partially_plated:"plated",plated:"ready"};
  let controls = "";
  if (kitchen && ["cook","lead"].includes(actor?.role) && stages[d.stage]) controls = `<button class="small" data-action="advance" data-id="${esc(d.id)}" data-stage="${stages[d.stage]}" data-command>${d.stage === "plated" ? "Mark ready" : `Mark ${human(stages[d.stage])}`}</button>`;
  if (!kitchen && d.stage === "picked_up" && ["server","lead"].includes(actor?.role)) controls = `<button class="small primary" data-action="advance" data-id="${esc(d.id)}" data-stage="served" data-command>Confirm served</button>`;
  return `<div class="dish"><div><p><strong>${esc(state.menu[d.menu_id]?.name || d.menu_id)}</strong> · seat ${d.seat}</p><small>${esc(d.id)} · ${esc(d.course)} · ${d.bay_id ? `Bay ${esc(d.bay_id)}` : "Waiting for bay"}${d.modifiers.length ? ` · ${esc(d.modifiers.join(", "))}` : ""}</small>${d.requests ? `<small>Guest request: <strong>${esc(d.requests)}</strong></small>` : ""}<span class="status">${human(d.stage)}</span></div><div class="actions">${controls}</div></div>`;
}
function renderTickets() {
  const orders = Object.values(state.orders).filter(o=>o.status === "submitted");
  $("tickets").innerHTML = orders.length ? orders.map(o=>`<article class="ticket"><div class="ticket-heading"><h3>Table ${esc(o.table_id)} · ${esc(state.computed?.ticket_stages?.[o.id] || "submitted")}</h3><small>${esc(o.id)} · revision ${o.revision}</small></div><p class="note">${o.acknowledged ? "Acknowledged; preparation is tracked per dish." : "Awaiting acknowledgment. This does not start preparation."}</p>${!o.acknowledged ? `<button data-action="ack" data-id="${esc(o.id)}" data-command>Acknowledge ticket</button>` : `<button data-action="select-prep" data-id="${esc(o.id)}" data-command>Select active prep ticket</button><span class="note"> ${state.active_prep?.[actor?.id] === o.id ? "Active for this cook" : "Sets the visible inventory attribution default; review before accepting"}</span>`}${o.amendments?.some(a=>!a.acknowledged) ? `<div class="proposal"><p>Pending amendment: ${esc(o.amendments.filter(a=>!a.acknowledged).map(a=>`${a.line_id} quantity ${a.quantity}`).join(", "))}</p><button data-action="ack-amendment" data-id="${esc(o.id)}" data-command>Acknowledge amendment</button></div>` : ""}${orderDishes(o.id).map(d=>dishMarkup(d,true)).join("")}</article>`).join("") : '<p class="empty">No submitted tickets. A server must review and send an order first.</p>';
}
function renderBays() {
  $("bays").innerHTML = Object.values(state.bays).map(b=> {
    const o = state.orders[b.order_id];
    const labels = b.dish_ids.map(id=>{ const d=state.dishes[id]; return d ? `${state.menu[d.menu_id]?.name || d.menu_id} · seat ${d.seat} · ${human(d.stage)}` : id; });
    return `<article class="bay"><h3>Bay ${esc(b.id)} <span class="tag">v${b.assignment_version}</span></h3><div class="table-number">${o ? `Table ${esc(o.table_id)}` : "Available"}</div><p>${b.order_id ? `${esc(b.order_id)} · ${esc(b.course)} · ${b.dish_ids.length}/${b.capacity} dishes` : `Capacity ${b.capacity} dish units`}</p>${labels.map(l=>`<p>${esc(l)}</p>`).join("")}<p><strong>${b.occupied ? "Food present" : "No food observed"}${b.unresolved_pickup ? " · UNRESOLVED PICKUP" : ""}</strong></p><div class="actions">${b.order_id ? `<button class="small" data-action="bay-observe" data-kind="plate_arrival" data-id="${esc(b.id)}" data-command>Mock plate arrival</button><button class="small" data-action="bay-observe" data-kind="plate_removal" data-id="${esc(b.id)}" data-command>Mock plate removal</button><button class="small" data-action="bay-observe" data-kind="plate_return" data-id="${esc(b.id)}" data-command>Mock plate return</button><button class="small" data-action="reconcile-bay" data-occupied="true" data-id="${esc(b.id)}" data-command>Confirm food still present</button><button class="small" data-action="reconcile-bay" data-occupied="false" data-id="${esc(b.id)}" data-command>Confirm bay empty after pickup</button><button class="small" data-action="release-bay" data-id="${esc(b.id)}" data-command>Review & release bay</button>` : ""}<button class="small" data-action="bay-observe" data-kind="obstruction" data-id="${esc(b.id)}" data-command>Mock obstruction</button></div></article>`;
  }).join("");
}
function renderOverview() {
  const tasks=Object.values(state.tasks), dishes=Object.values(state.dishes), observations=Object.values(state.observations);
  $("overview-summary").innerHTML = `<p><strong>${dishes.filter(d=>d.stage === "ready").length}</strong>ready dish units</p><p><strong>${tasks.filter(t=>t.status === "claimed").length}</strong>claimed tasks</p><p><strong>${observations.filter(o=>["unresolved","needs_staff_review","clarify_removed_dish_and_runner","clarify_staged_dish","return_needs_reconciliation"].includes(o.disposition)).length}</strong>unresolved observations</p><p><strong>${dishes.filter(d=>!d.bay_id && !["served","picked_up"].includes(d.stage)).length}</strong>waiting for bay</p>`;
  $("inventory").innerHTML = Object.values(state.zones).map(z=>`<div class="inventory-row"><p><strong>${esc(z.ingredient)}</strong><small>Accepted balance: ${esc(state.computed?.balances?.[z.id] ?? z.initial)} ${esc(z.unit)} · recipe expectation: ${esc(state.computed?.expected_consumption?.[z.id] ?? 0)}</small></p><button class="small" data-action="ingredient-observe" data-id="${esc(z.id)}" data-command>Mock stable change</button></div>`).join("");
  $("adapters").innerHTML = Object.entries(state.adapter_status).map(([key,status])=>`<div class="adapter"><strong>${human(key)}</strong><p>${esc(status)}</p></div>`).join("") + `<p class="note">Automatic ready is ${state.auto_ready_enabled ? 'EXPERIMENTAL: complete-batch convention, single observed plate only' : 'disabled'}. No real positioning, camera inference, payment or POS integration is claimed.</p>`;
  $("observations").innerHTML = observations.slice(-8).reverse().map(o=>`<div class="observation"><strong>${human(o.kind)} · ${esc(o.target_id)}</strong><br>${esc(o.disposition)} · ${esc(o.source)}<br><small>${esc(o.id)}</small></div>`).join("") || '<p class="empty">No observations yet.</p>';
  $("events").innerHTML = state.events.slice(-6).reverse().map(e=>`<div class="event">${esc(e.action || e.payload?.action || e.type || e.id)} · ${esc(e.actor_id || e.actor || "unknown actor")} · ${esc(e.source || "")}<br><small>${esc(e.id || "")}</small></div>`).join("") || '<p class="empty">No accepted commands yet.</p>';
  if (!$("stock-order").matches(":focus")) fillSelect("stock-order",Object.values(state.orders).filter(o=>o.status==="submitted").map(o=>[o.id,`Table ${o.table_id} · ${o.id}`]),"Unassigned");
  if (!$("stock-observation").matches(":focus")) fillSelect("stock-observation",observations.filter(o=>o.kind==="ingredient_change" && o.disposition !== "accepted").map(o=>[o.id,`${o.target_id} · ${o.id}`]),"Manual movement / no observation");
}

$("connect").addEventListener("click",async()=> {
  if (busy || uncertain) { feedback("Resolve the pending command before switching sessions.",true); return; }
  try {
    const data=await request("/api/v1/sessions",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({actor_id:$("actor").value})});
    session=data.session_id; actor=data.actor; draftId=""; draftSignature="";
    $("identity").textContent=`${actor.name} · ${actor.role} · ${actor.section} · simulated sign-in`;
    showView(actor.role==="cook" ? "kitchen" : actor.role==="lead" ? "overview" : "server");
    await refresh(); feedback("Demo session active. Other tabs share backend state, with their own staff sessions.");
  } catch(error) { feedback(`Cannot enter session: ${error.message}`,true); }
});
function showView(name) {
  currentView=name;
  document.querySelectorAll(".view").forEach(el=>el.hidden=el.id!==`${name}-view`);
  document.querySelectorAll("[data-view]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.view===name)));
  document.title=`Dig In · ${name === "overview" ? "Shift overview" : human(name)}`;
}
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>showView(button.dataset.view)));
$("retry").addEventListener("click",()=>uncertain && dispatch(uncertain.payload,uncertain.source,uncertain));
$("section-only").addEventListener("change",refresh);
$("draft-select").addEventListener("change",()=>{draftId=$("draft-select").value;draftSignature="";renderDraft();setBusy(busy);});
$("menu").addEventListener("change",refreshModifiers);
$("draft-table").addEventListener("change",refreshSeats);
$("edit-line").addEventListener("change",loadLine);
$("start-form").addEventListener("submit",event=>{event.preventDefault();dispatch({action:"start_order",table_id:$("start-table").value,use_positioning:$("positioning").checked});});
$("table-form").addEventListener("submit",event=>{event.preventDefault();const o=state.orders[draftId]; if(!o.lines.length){feedback("Add the first dish line to save this table correction.",true);return;}dispatch({action:"edit_draft",order_id:o.id,revision:o.revision,table_id:$("draft-table").value,lines:o.lines});});
$("line-form").addEventListener("submit",async event=> {
  event.preventDefault(); const o=state.orders[draftId]; if(!o) return;
  const selected=$("edit-line").value;
  const old=o.lines.find(l=>l.id===selected);
  const line={id:selected || `line-${uid()}`,seat:Number($("seat").value),menu_id:$("menu").value,quantity:Number($("quantity").value),modifiers:[...$("modifier").selectedOptions].map(o=>o.value).filter(Boolean),requests:$("requests").value.trim(),course:$("course").value.trim()};
  // Fields outside this editor remain unchanged when correcting one selected line.
  const lines=old ? o.lines.map(l=>l.id===selected ? line : l) : [...o.lines,line];
  const data=await dispatch({action:"edit_draft",order_id:o.id,revision:o.revision,table_id:$("draft-table").value,lines});
  if(data){$("edit-line").value="";loadLine();}
});
$("remove-line").addEventListener("click",()=>{const o=state.orders[draftId], id=$("edit-line").value;if(!id){feedback("Select a saved line to remove.",true);return;}if(o.lines.length===1){feedback("A draft must retain at least one line. Edit this line instead.",true);return;}dispatch({action:"edit_draft",order_id:o.id,revision:o.revision,table_id:o.table_id,lines:o.lines.filter(l=>l.id!==id)});});
$("readback-form").addEventListener("submit",event=>{event.preventDefault();const o=state.orders[draftId];dispatch({action:"readback",order_id:o.id,revision:o.revision,transcript:$("transcript").value},"voice");});
$("confirm-send").addEventListener("click",()=>{const o=state.orders[draftId];dispatch({action:"confirm_send",order_id:o.id,revision:o.revision,human_confirmed:true});});
$("request-form").addEventListener("submit",event=>{event.preventDefault();dispatch({action:"create_task",table_id:$("request-table").value,type:$("request-type").value,reason:$("request-reason").value.trim()});});
$("stock-form").addEventListener("submit",event=>{event.preventDefault();dispatch({action:"accept_movement",zone_id:$("stock-zone").value,kind:$("stock-kind").value,quantity:Number($("stock-quantity").value),observation_id:$("stock-observation").value || null,order_id:$("stock-order").value || null,reason:$("stock-reason").value.trim()});});
document.addEventListener("click",async event=> {
  const button=event.target.closest("[data-action]"); if(!button || button.disabled || busy)return;
  const {action,id,operation,stage,kind}=button.dataset;
  if(action==="accept"){const o=state.orders[draftId];dispatch({action:"accept_correction",order_id:o.id,revision:o.revision,proposal_id:id});}
  if(action==="keep-draft"){const o=state.orders[draftId];dispatch({action:"edit_draft",order_id:o.id,revision:o.revision,table_id:o.table_id,lines:o.lines});}
  if(action==="select-prep"){const data=await dispatch({action:"select_prep",order_id:id});if(data)$("stock-order").value=id;}
  if(action==="reconcile-bay"){const bay=state.bays[id];dispatch({action:"reconcile_bay",bay_id:id,assignment_version:bay.assignment_version,occupied:button.dataset.occupied==="true",reason:button.dataset.occupied==="true"?"Cook explicitly reviewed food still physically present":"Cook explicitly reviewed bay empty after claimed pickup"});}
  if(action==="ack")dispatch({action:"acknowledge",order_id:id});
  if(action==="ack-amendment")dispatch({action:"ack_amendment",order_id:id,revision:state.orders[id].revision});
  if(action==="advance")dispatch({action:"advance_dish",dish_id:id,stage,reason:stage==="served" ? "Staff explicitly confirmed delivery to the guest" : "Cook confirmed stage by tap"});
  if(action==="task")dispatch({action:"task_action",task_id:id,operation,additional_helpers:operation==="helpers"?1:0,reason:operation==="block"?"Staff requested a pause; review this task":operation==="urgent"?"Explicit shift-lead urgency override":"Staff task action"});
  if(action==="pickup") {
    const task=state.tasks[id];
    for(const dishId of task.dish_ids){if(state.dishes[dishId]?.stage==="ready"){const result=await dispatch({action:"advance_dish",dish_id:dishId,stage:"picked_up",reason:"Claimed runner explicitly confirmed pickup"});if(!result)break;}}
  }
  if(action==="bay-observe"){const bay=state.bays[id];dispatch({action:"observe",kind,target_id:id,assignment_version:bay.assignment_version,quantity:1,order_id:bay.order_id},"mock_camera");}
  if(action==="release-bay"){const bay=state.bays[id];dispatch({action:"release_bay",bay_id:id,assignment_version:bay.assignment_version,reason:"Staff reviewed bay state and requested release; backend validates food and unresolved pickup"});}
  if(action==="ingredient-observe")dispatch({action:"observe",kind:"ingredient_change",target_id:id,quantity:1,order_id:null},"mock_camera");
});
$("api-link").href=`${API}/docs`;
refresh();
setInterval(refresh,2500);
