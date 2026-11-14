/* MVP client. Contracts are owned by backend/app/mvp; no localStorage authority.
 * Text simulators never claim microphone/camera processing or live Databricks.
 */
"use strict";
const API = (window.DIG_IN_API || "http://localhost:8000").replace(/\/$/, "");
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const uid = () => globalThis.crypto?.randomUUID?.() || `web-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const human = value => String(value || "").replaceAll("_", " ");
let state = null, actor = null, session = null, busy = false, uncertain = null;
let draftId = "", draftSignature = "", menuSignature = "", view = "server", holding = false;
let suggested = new Set();

function feedback(message, error = false) {
  $("feedback").textContent = message;
  $("feedback").classList.toggle("error", error);
}
function connected(ok) {
  $("connection").textContent = ok ? "Shared backend connected" : "Backend unavailable · UNSYNCED";
  $("connection").style.color = ok ? "var(--green)" : "var(--danger)";
}
async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(`${API}${path}`, {...options, signal: controller.signal});
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(`${response.status}: ${typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data)}`);
      error.rejected = true;
      throw error;
    }
    connected(true);
    return data;
  } catch (error) {
    if (!error.rejected) connected(false);
    throw error;
  } finally { clearTimeout(timer); }
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll("[data-command]").forEach(button => button.disabled = value || !session || Boolean(uncertain));
  $("retry").disabled = value;
  const order = state?.orders[draftId];
  $("confirm-send").disabled = value || !session || Boolean(uncertain) || !order?.lines.length || Boolean(order?.flags?.length);
}
async function dispatch(payload, source = "tap", existing = null) {
  if (!session) { feedback("Enter a simulated staff session first.", true); return null; }
  if (busy || (uncertain && !existing)) { feedback("Resolve the uncertain event with Retry before making another change.", true); return null; }
  const envelope = existing || {event_id: uid(), schema_version: 2, source, time: new Date().toISOString(), run_id: "web-demo", simulated: true, payload};
  setBusy(true);
  feedback("Sending to shared backend…");
  try {
    const data = await request("/api/v2/commands", {method: "POST", headers: {"Content-Type": "application/json", "X-Demo-Session": session}, body: JSON.stringify(envelope)});
    uncertain = null;
    $("retry-bar").hidden = true;
    state = data.state;
    if (payload.action === "start_order") draftId = data.result.order_id;
    suggested = new Set(payload.action === "kitchen_voice" ? (data.result?.flags || []).flatMap(flag => flag.candidates || []) : []);
    render();
    const flags = data.result?.flags;
    if (Array.isArray(flags) && flags.length) {
      const message = flags.map(flag => typeof flag === "string" ? flag : flag.message || flag.code).join(" ");
      feedback(`Clarification needed: ${message}`, true);
      if (payload.action === "kitchen_voice") $("kitchen-clarification").textContent = message;
    } else {
      feedback(payload.action === "confirm_send" ? "Order submitted. Kitchen acknowledgment is a separate next step." : "Change accepted by the shared backend.");
      if (payload.action === "kitchen_voice") $("kitchen-clarification").textContent = "Kitchen phrase accepted. Check the exact ticket and dish below.";
    }
    return data;
  } catch (error) {
    if (!error.rejected) { uncertain = envelope; $("retry-bar").hidden = false; }
    feedback(error.rejected ? `${error.message}. Refresh and review the shared state before trying again.` : "Connection interrupted. The event may have arrived. Reconnect, then Retry reuses its exact ID and timestamp.", true);
    return null;
  } finally { setBusy(false); }
}
async function refresh() {
  if (busy || holding) return;
  try {
    state = await request("/api/v2/state");
    render();
  } catch (error) {
    feedback("Shared backend unavailable · UNSYNCED. Draft text stays visible, but offline orders are not completed. Reconnect before sending.", true);
  }
}
function fillSelect(id, options, placeholder) {
  const element = $(id), before = element.value;
  element.innerHTML = (placeholder === undefined ? "" : `<option value="">${esc(placeholder)}</option>`) + options.map(([value, text]) => `<option value="${esc(value)}">${esc(text)}</option>`).join("");
  if ([...element.options].some(option => option.value === before)) element.value = before;
}
function items() { return state?.menu?.items || []; }
function menuItem(id) { return items().find(item => item.id === id); }
function modifierNames(menuId, ids = []) {
  const modifiers = menuItem(menuId)?.modifiers || [];
  return ids.map(id => modifiers.find(modifier => modifier.id === id)?.name || id);
}
function dishesFor(orderId) { return Object.values(state.dishes).filter(dish => dish.order_id === orderId); }
function progress(order) {
  const supplied = state.computed?.order_progress?.[order.id];
  if (supplied) return supplied;
  const dishes = dishesFor(order.id);
  return {ready: dishes.filter(dish => dish.ready_at).length, total: dishes.length, picked_up: dishes.filter(dish => dish.stage === "picked_up").length};
}
function updateUnlessEditing(id, renderFunction) {
  const container = $(id), focused = document.activeElement;
  if (container.contains(focused) && ["INPUT", "TEXTAREA", "SELECT"].includes(focused.tagName)) return;
  const dataset = container.contains(focused) && focused.matches("button") ? {...focused.dataset} : null;
  renderFunction();
  if (dataset) [...container.querySelectorAll("button")].find(button => Object.entries(dataset).every(([key,value]) => button.dataset[key] === value))?.focus({preventScroll: true});
}
function render() {
  if (!state) return;
  const currentMenuSignature = JSON.stringify(state.menu);
  if (menuSignature !== currentMenuSignature) {
    menuSignature = currentMenuSignature;
    const tables = Object.values(state.tables).map(table => [table.id, `Table ${table.id}`]);
    fillSelect("start-table", tables);
    fillSelect("draft-table", tables);
    fillSelect("actor", Object.values(state.actors).map(person => [person.id, `${person.name} · ${person.role}`]));
    fillSelect("menu", items().map(item => [item.id, item.name]));
    refreshModifiers();
    const examples = items().slice(0, 2).map(item => `one ${item.aliases?.[0] || item.name}`).join(" and ");
    $("transcript").placeholder = `Table ${tables[0]?.[0] || "N"}: ${examples || "one configured menu item"}`;
    $("menu-summary").innerHTML = items().map(item => `<div class="menu-item"><strong>${esc(item.name)}</strong><p>${item.price_cents == null ? "Price unknown" : new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"}).format(item.price_cents / 100)}</p><p class="note">${item.station ? esc(item.station) : "Station unknown"} · ${item.typical_minutes == null ? "Typical time unknown" : `Typical ${esc(item.typical_minutes)} min`}</p></div>`).join("");
  }
  renderDraft();
  updateUnlessEditing("server-orders", renderServerOrders);
  updateUnlessEditing("tickets", renderTickets);
  updateUnlessEditing("zones", renderZones);
  updateUnlessEditing("cameras", renderCameras);
  renderNotifications();
  const health = state.computed?.analytics_health || state.analytics_health;
  $("analytics-health").textContent = health ? Object.entries(health).filter(([,value]) => typeof value !== "object").map(([key,value]) => `${human(key)}: ${value}`).join(" · ") : "Outbox status is available through the API. Cloud export is not connected.";
  setBusy(busy);
}
function renderDraft() {
  const drafts = Object.values(state.orders).filter(order => order.status === "draft" && order.owner === actor?.id);
  fillSelect("draft-select", drafts.map(order => [order.id, `Table ${order.table_id || "—"} · ${order.id.slice(0,8)} · r${order.revision}`]), "Choose a draft");
  if (!drafts.some(order => order.id === draftId)) draftId = drafts[0]?.id || "";
  $("draft-select").value = draftId;
  const order = state.orders[draftId];
  $("editor").hidden = !order;
  if (!order) { $("draft-summary").innerHTML = '<p class="empty">Start with a table, then enter dishes manually or use the read-back simulator.</p>'; draftSignature = ""; return; }
  const signature = JSON.stringify(order);
  if (signature === draftSignature) return;
  draftSignature = signature;
  $("draft-summary").innerHTML = `<div class="draft-title"><strong>Table ${esc(order.table_id)}</strong><span class="status">Draft · revision ${order.revision}</span></div>${lineList(order)}<p class="note">Ticket ${esc(order.id)} · corrections measured at submission</p>`;
  $("draft-table").value = order.table_id || "";
  fillSelect("edit-line", order.lines.map(line => [line.id, `${line.quantity} × ${line.item_name || menuItem(line.menu_id)?.name || line.menu_id}`]), "New dish line");
  $("draft-flags").innerHTML = (order.flags || []).map(flagMarkup).join("");
  const count = order.lines.reduce((total, line) => total + line.quantity, 0);
  $("send-note").textContent = `Review table ${order.table_id}, ${count} physical dish units, modifiers and requests. Your tap approves revision ${order.revision}.`;
  $("confirmation-blocker").textContent = order.flags?.length ? "Submission blocked: resolve each table/menu flag above, then review the draft." : !count ? "Add at least one dish before sending." : "Ready for human review. Voice never submits.";
}
function lineList(order) {
  return order.lines.length ? order.lines.map(line => `<div class="order-line"><div><strong>${line.quantity} × ${esc(line.item_name || menuItem(line.menu_id)?.name || line.menu_id)}</strong><small>${line.seat ? `Seat ${line.seat} · ` : ""}${esc(modifierNames(line.menu_id, line.modifiers).join(", ") || "No modifiers")}</small>${line.requests ? `<small><strong>Guest request:</strong> ${esc(line.requests)}</small>` : ""}</div></div>`).join("") : '<p class="empty">No dishes entered. Nothing has been sent.</p>';
}
function flagMarkup(flag) {
  const resolve = (resolution, label) => `<button data-action="resolve-flag" data-id="${esc(flag.id)}" data-resolution="${resolution}" data-command>${label}</button>`;
  if (flag.code === "dietary_check_required") return `<article class="review-flag" role="alert"><strong>Ask the table about allergies or dietary needs</strong><p>Record the answer before sending. If anyone has a need, say it after the dish (for example "one bulldozer, seat 2, allergy to gluten") or type it in that dish's request field.</p><div class="actions">${resolve("asked_none_reported", "Asked: none")}</div></article>`;
  if (flag.code === "dietary_review" || flag.code === "dietary_unattached") return `<article class="review-flag"><strong>${flag.code === "dietary_review" ? "Check the dietary note" : "Attach this dietary note to a dish"}</strong><p>${esc(flag.message)}</p><div class="actions">${resolve("reviewed_keep_note", flag.code === "dietary_review" ? "Note is correct" : "Added to the dish")}</div><p class="note">Speech-to-text can mishear; edit the dish's request field below if the note is wrong.</p></article>`;
  const mismatch = flag.code === "table_mismatch";
  const tableRequired = flag.code === "table_required";
  const candidates = flag.candidates?.map(id => menuItem(id)?.name || (typeof id === "string" ? id : JSON.stringify(id))) || [];
  return `<article class="review-flag"><strong>${mismatch ? "Resolve the table mismatch" : tableRequired ? "Confirm the selected table" : "Review an uncertain draft"}</strong><p>${esc(flag.message || human(flag.code))}</p>${candidates.length ? `<p>Candidates: ${esc(candidates.join(", "))}</p>` : ""}<div class="actions">${mismatch || tableRequired ? `<button data-action="resolve-flag" data-id="${esc(flag.id)}" data-resolution="keep_selected_table" data-command>Keep selected table</button>${mismatch ? `<button data-action="resolve-flag" data-id="${esc(flag.id)}" data-resolution="use_spoken_table" data-command>Use spoken table</button>` : ""}` : `<button data-action="resolve-flag" data-id="${esc(flag.id)}" data-resolution="reviewed_remove_unknown" data-command>Reviewed — omit uncertain words</button>`}</div><p class="note">Use manual entries below for the intended item. No candidate is chosen automatically.</p></article>`;
}
function refreshModifiers() {
  const modifiers = menuItem($("menu").value)?.modifiers || [];
  fillSelect("modifier", modifiers.map(modifier => [modifier.id, modifier.name]), "No modifier");
}
function loadLine() {
  const line = state.orders[draftId]?.lines.find(entry => entry.id === $("edit-line").value);
  $("menu").value = line?.menu_id || items()[0]?.id || "";
  $("quantity").value = line?.quantity || 1;
  $("seat").value = line?.seat || "";
  $("requests").value = line?.requests || "";
  refreshModifiers();
  [...$("modifier").options].forEach(option => option.selected = Boolean(line?.modifiers?.includes(option.value)));
}
function renderNotifications() {
  const notices = (state.notifications || []).filter(notice => state.orders[notice.order_id]?.owner === actor?.id);
  $("notifications").innerHTML = notices.map(notice => `<article class="ready-notice"><h2>Table ${esc(state.orders[notice.order_id]?.table_id)} · all dishes ready</h2><p>One order-ready notification · ticket ${esc(notice.order_id)}. ${state.orders[notice.order_id]?.status === "delivered" ? "Delivered confirmed." : "Review the dish pickup status below."}</p></article>`).join("");
}
function renderServerOrders() {
  const orders = Object.values(state.orders).filter(order => order.status !== "draft" && order.owner === actor?.id);
  $("server-orders").innerHTML = orders.length ? orders.map(order => {
    const counts = progress(order);
    return `<article class="ticket"><div class="ticket-heading"><h3>Table ${esc(order.table_id)} · ${esc(human(order.status))}</h3><small>Ticket ${esc(order.id)}</small></div><p class="note"><strong>Dietary:</strong> ${order.dietary_check === "requests_recorded" ? "needs recorded on the dishes below" : order.dietary_check === "none_reported" ? "asked, none reported" : "not recorded"}</p><p class="ticket-progress">${counts.ready} of ${counts.total} ready · ${counts.picked_up} picked up</p>${dishesFor(order.id).map(dish => dishMarkup(dish, false)).join("")}${order.status === "picked_up" ? `<button class="primary" data-action="deliver" data-id="${esc(order.id)}" data-command>Confirm delivered (optional)</button>` : ""}</article>`;
  }).join("") : '<p class="empty">Your submitted orders will appear here. Partial readiness never sends an all-ready notification.</p>';
}
function elapsed(timestamp) {
  if (!timestamp) return "Start time unknown";
  const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(timestamp)) / 1000));
  return `Started ${Math.floor(seconds / 60)}m ${seconds % 60}s ago`;
}
function dishMarkup(dish, kitchen) {
  const order = state.orders[dish.order_id];
  let controls = "";
  if (kitchen && order?.status !== "submitted") {
    if (dish.stage === "queued") controls += `<button class="small" data-action="start-dish" data-id="${esc(dish.id)}" data-command>Start dish</button>`;
    if (["queued", "started"].includes(dish.stage) && dish.zone_id) controls += `<button class="small" data-action="ready-dish" data-id="${esc(dish.id)}" data-command>Tap ready</button>`;
  }
  if (!kitchen && dish.stage === "ready") controls += `<button class="small primary" data-action="pickup-dish" data-id="${esc(dish.id)}" data-command>Confirm plate pickup</button>`;
  const mark = kitchen && dish.stage === "queued" && suggested.has(dish.menu_id);
  return `<div class="dish${mark ? " suggested" : ""}"><div>${mark ? '<span class="suggested-tag">Suggested by voice, tap to confirm</span>' : ""}<p><strong>${esc(dish.item_name || menuItem(dish.menu_id)?.name || dish.menu_id)}</strong>${dish.seat ? ` · seat ${dish.seat}` : ""}</p><small>Unit ${esc(dish.id)} · ${dish.zone_id ? `Zone ${esc(dish.zone_id)}` : "No zone assigned"}${dish.station ? ` · ${esc(dish.station)}` : " · station unknown"}</small><p class="dish-timer">${esc(elapsed(dish.started_at))} · ${dish.typical_minutes == null ? "typical time unknown" : `typical ${esc(dish.typical_minutes)} min`}</p>${dish.modifiers?.length ? `<small>${esc(modifierNames(dish.menu_id, dish.modifiers).join(", "))}</small>` : ""}${dish.requests ? `<small><strong>Guest request:</strong> ${esc(dish.requests)}</small>` : ""}<span class="dish-stage">${esc(human(dish.stage))}</span></div><div class="actions">${controls}</div></div>`;
}
function renderTickets() {
  const orders = Object.values(state.orders).filter(order => order.status !== "draft" && order.status !== "delivered");
  $("tickets").innerHTML = orders.length ? orders.map(order => {
    const counts = progress(order);
    return `<article class="ticket"><div class="ticket-heading"><h3>Table ${esc(order.table_id)} · ${esc(human(order.status))}</h3><small>Ticket ${esc(order.id)}</small></div><p class="note"><strong>Dietary:</strong> ${order.dietary_check === "requests_recorded" ? "needs recorded on the dishes below" : order.dietary_check === "none_reported" ? "asked, none reported" : "not recorded"}</p><p class="ticket-progress">${counts.ready} of ${counts.total} ready · ${counts.picked_up} picked up</p>${order.status === "submitted" ? `<button class="primary" data-action="acknowledge" data-id="${esc(order.id)}" data-command>Acknowledge & reserve zones</button>` : ""}${order.zone_status === "waiting" ? `<div class="review-flag"><strong>Waiting for ${counts.total} free zones</strong><p>Nothing is partially allocated. Pickup/recovery frees capacity.</p><button data-action="retry-zones" data-id="${esc(order.id)}" data-command>Retry zone reservation</button></div>` : ""}${dishesFor(order.id).map(dish => dishMarkup(dish, true)).join("")}</article>`;
  }).join("") : '<p class="empty">No active tickets. A server must review and send an order first.</p>';
}
function renderCameras() {
  $("cameras").innerHTML = Object.values(state.cameras || {}).map(camera => `<div class="camera-row"><p><strong>${esc(camera.id)}</strong> · ${esc(human(camera.status))}<br><small>${esc(camera.reason || "Status from simulated device adapter")}</small></p><div class="actions">${["ok", "blocked", "offline"].map(status => `<button class="small" data-action="camera-status" data-id="${esc(camera.id)}" data-status="${status}" data-command>Simulate ${status}</button>`).join("")}</div></div>`).join("") || '<p class="empty">No camera configured. Use tap actions; camera integration is unavailable.</p>';
}
function renderZones() {
  $("zones").innerHTML = Object.values(state.zones).map(zone => {
    const order = state.orders[zone.order_id], dish = state.dishes[zone.dish_id];
    const review = zone.needs_review || zone.blocked_reason;
    return `<article class="mvp-zone${review ? " needs-review" : ""}"><h3>Zone ${esc(zone.id)} <span class="tag">v${zone.assignment_version}</span></h3><div class="zone-label">${order ? `Table ${esc(order.table_id)}` : "Unassigned"}</div><p>${dish ? esc(dish.item_name || menuItem(dish.menu_id)?.name || dish.menu_id) : "One physical plate per assigned zone"}</p>${dish ? `<small>Unit ${esc(dish.id)}</small>` : ""}<p><strong>${esc(human(zone.occupancy))}</strong> · ${esc(zone.camera_id || "camera unknown")}</p>${review ? `<div class="review-flag"><strong>Staff review required</strong><p>${esc(zone.blocked_reason || "Unexpected/uncertain plate. Check the physical zone and assigned ticket.")}</p></div>` : ""}<div class="actions"><button class="small" data-action="zone-observation" data-id="${esc(zone.id)}" data-occupied="true" data-command>Simulate stable plate</button><button class="small" data-action="zone-observation" data-id="${esc(zone.id)}" data-occupied="false" data-command>Simulate stable empty</button><button class="small" data-action="hand-pass" data-id="${esc(zone.id)}" data-command>Simulate hand passing</button>${review || zone.occupancy === "unknown" ? `<button class="small" data-action="reconcile-zone" data-id="${esc(zone.id)}" data-occupied="true" data-command>Reviewed: plate present</button><button class="small" data-action="reconcile-zone" data-id="${esc(zone.id)}" data-occupied="false" data-command>Reviewed: zone empty</button>` : ""}</div><p class="note">Stable simulation: 1.6s, no hand. Camera does not identify food or check doneness.</p></article>`;
  }).join("");
}
function fallbackReason(dish) {
  const zone = state.zones[dish.zone_id];
  const status = state.cameras?.[zone?.camera_id]?.status;
  return status && status !== "ok" ? `Camera ${status}; staff used the tap alternative` : null;
}
function showView(name) {
  view = name;
  document.querySelectorAll(".view").forEach(element => element.hidden = element.id !== `${name}-view`);
  document.querySelectorAll("[data-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === name)));
  document.title = `Dig In · ${name}`;
}
async function captureText(captureMode = "mock_voice") {
  const order = state?.orders[draftId];
  if (!order) { feedback("Start an order before capturing a read-back.", true); return; }
  const text = $("transcript").value.trim();
  if (!text) { feedback("Enter a mock transcript first. No microphone is connected.", true); return; }
  const data = await dispatch({action: "capture_voice", order_id: order.id, revision: order.revision, text, capture_mode: captureMode}, "voice");
  if (data) $("transcript").value = "";
}
let voice = {live: false, authRequired: false, auth: null}, capture = null;
async function loadVoiceStatus() {
  try {
    const status = await request("/api/v2/voice/status");
    voice.live = Boolean(status.live_capture_available);
    voice.authRequired = Boolean(status.auth_required);
  } catch { voice.live = false; }
  $("voice-mode-tag").textContent = voice.live ? "LIVE MIC · DEEPGRAM" : "SIMULATED TRANSCRIPTION";
  updateKitchenMic();
  if (voice.live) {
    $("voice-note").textContent = "Hold to talk: say the table first, then each dish. Audio streams to Deepgram and is discarded after transcription. Release to build an editable draft; nothing is sent until you review and tap Confirm and send.";
    $("hold-talk").textContent = "Hold to talk";
    $("capture-status").textContent = "Live mic ready. Hold with pointer, Space or Enter; release to stop.";
    $("transcript").labels[0].firstChild.textContent = "Transcript (live words appear here; you can also type)";
  }
}
const kitchenRole = () => ["cook", "lead"].includes(actor?.role);
function updateKitchenMic() {
  $("kitchen-hold").hidden = !(voice.live && kitchenRole());
}
const captureUi = target => target === "kitchen"
  ? {field: $("kitchen-transcript"), status: $("kitchen-capture-status"), button: $("kitchen-hold")}
  : {field: $("transcript"), status: $("capture-status"), button: $("hold-talk")};
function stopMedia(cap) {
  cap.media?.getTracks().forEach(track => track.stop());
  if (cap.ws && cap.ws.readyState <= 1) cap.ws.close();
}
async function startLive(target) {
  const ui = captureUi(target);
  if (voice.authRequired && !voice.auth) {
    $("voice-login").hidden = false;
    $("voice-user").focus();
    ui.status.textContent = "Enter the demo login at the top of the page to unlock the live mic.";
    return false;
  }
  const opus = "audio/webm;codecs=opus";
  if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia || !MediaRecorder.isTypeSupported(opus)) {
    ui.status.textContent = "This browser can't stream live audio (use Chrome or Edge). Type the order or use manual entry.";
    return false;
  }
  const cap = capture = {target, ui, text: "", stopped: false, cancelled: false};
  try {
    const ticket = await request("/api/v2/voice/ticket", {method: "POST", headers: voice.auth ? {Authorization: `Basic ${voice.auth}`} : {}});
    cap.media = await navigator.mediaDevices.getUserMedia({audio: true});
    const ws = cap.ws = new WebSocket(`${API.replace(/^http/, "ws")}/api/v2/voice/stream?ticket=${encodeURIComponent(ticket.ticket)}`);
    cap.done = new Promise(resolve => {
      ws.addEventListener("message", event => {
        const message = JSON.parse(event.data);
        if (message.type === "interim" || message.type === "final") ui.field.value = message.text;
        if (message.type === "limit" || message.type === "error") ui.status.textContent = message.message;
        if (message.type === "error") cap.error = message.message;
        if (message.type === "done") { cap.text = message.text; resolve(); }
      });
      ws.addEventListener("close", () => resolve());
    });
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve, {once: true});
      ws.addEventListener("close", () => reject(new Error("Live stream refused")), {once: true});
    });
    const recorder = cap.recorder = new MediaRecorder(cap.media, {mimeType: opus});
    recorder.addEventListener("dataavailable", event => { if (event.data.size && ws.readyState === 1) ws.send(event.data); });
    recorder.addEventListener("stop", () => { if (ws.readyState === 1) ws.send(JSON.stringify({type: "stop"})); });
    recorder.start(250);
    ui.status.textContent = `Listening (max ${Math.round(ticket.max_stream_seconds)}s). Release to stop.`;
    if (cap.stopped) finishLive(cap);
    return true;
  } catch (error) {
    stopMedia(cap);
    capture = null;
    if (String(error.message).startsWith("401")) { voice.auth = null; $("voice-login").hidden = false; }
    ui.status.textContent = `Live mic unavailable: ${error.message}. Type the order or use manual entry.`;
    return false;
  }
}
async function finishLive(cap) {
  if (!cap.recorder || cap.finishing) return;
  cap.finishing = true;
  if (cap.recorder.state !== "inactive") cap.recorder.stop();
  cap.ui.status.textContent = cap.cancelled ? "Capture cancelled. Nothing was sent." : "Finishing transcription…";
  await Promise.race([cap.done, new Promise(resolve => setTimeout(resolve, 10000))]);
  stopMedia(cap);
  if (capture === cap) capture = null;
  const text = cap.text.trim();
  if (cap.cancelled) { cap.ui.field.value = ""; return; }
  if (!text) { cap.ui.status.textContent = cap.error || "Nothing was heard. Try again, type it, or use manual entry."; return; }
  cap.ui.field.value = text;
  if (cap.target === "kitchen") {
    const data = await dispatch({action: "kitchen_voice", text}, "voice");
    if (data) cap.ui.field.value = "";
    cap.ui.status.textContent = "";
  } else {
    cap.ui.status.textContent = "Released. The draft still needs human review and Confirm and send.";
    captureText("live_voice");
  }
}
function beginHold(event, target = "order") {
  if (busy || uncertain || !session || holding) return;
  if (target === "kitchen" && !kitchenRole()) { feedback("Kitchen voice is for cook or lead sessions. Enter a kitchen session first.", true); return; }
  if (target === "order" && !state?.orders[draftId]) { feedback("Start an order before capturing a read-back.", true); return; }
  event?.preventDefault();
  holding = true;
  const ui = captureUi(target);
  ui.button.classList.add("holding");
  ui.button.setAttribute("aria-pressed", "true");
  if (voice.live) { ui.status.textContent = "Starting live mic…"; startLive(target).then(ok => { if (!ok) { holding = false; ui.button.classList.remove("holding"); ui.button.setAttribute("aria-pressed", "false"); } }); }
  else ui.status.textContent = "Holding simulated capture. Release to build an editable menu-constrained draft; no audio is recording.";
}
function endHold(event, cancelled = false, target = "order") {
  if (!holding) return;
  event?.preventDefault();
  holding = false;
  captureUi(target).button.classList.remove("holding");
  captureUi(target).button.setAttribute("aria-pressed", "false");
  if (capture) {
    capture.stopped = true;
    capture.cancelled = cancelled;
    finishLive(capture);
    return;
  }
  if (voice.live) return;
  $("capture-status").textContent = cancelled ? "Capture cancelled. Nothing was sent." : "Released. The draft still needs human review and Confirm and send.";
  if (!cancelled) captureText();
}
$("connect").addEventListener("click", async () => {
  if (busy || uncertain) { feedback("Resolve the pending event before switching sessions.", true); return; }
  try {
    const data = await request("/api/v2/sessions", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({actor_id: $("actor").value})});
    session = data.session_id; actor = data.actor; draftId = ""; draftSignature = "";
    $("identity").textContent = `${actor.name} · ${actor.role} · simulated sign-in`;
    showView(actor.role === "cook" ? "kitchen" : "server");
    updateKitchenMic();
    render();
    feedback("Demo session active. Other devices share this backend, with their own sessions.");
  } catch (error) { feedback(`Cannot enter session: ${error.message}`, true); }
});
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => showView(button.dataset.view)));
$("retry").addEventListener("click", () => uncertain && dispatch(uncertain.payload, uncertain.source, uncertain));
$("draft-select").addEventListener("change", () => { draftId = $("draft-select").value; draftSignature = ""; renderDraft(); setBusy(busy); });
$("menu").addEventListener("change", refreshModifiers);
$("edit-line").addEventListener("change", loadLine);
$("start-form").addEventListener("submit", event => { event.preventDefault(); dispatch({action: "start_order", table_id: $("start-table").value}); });
$("table-form").addEventListener("submit", event => { event.preventDefault(); const order = state.orders[draftId]; dispatch({action: "edit_draft", order_id: order.id, revision: order.revision, table_id: $("draft-table").value, lines: order.lines.map(editableLine)}); });
function editableLine(line) { return {id: line.id, menu_id: line.menu_id, quantity: line.quantity, modifiers: line.modifiers || [], seat: line.seat || null, requests: line.requests || ""}; }
$("line-form").addEventListener("submit", async event => {
  event.preventDefault();
  const order = state.orders[draftId];
  if (!order) return;
  const selected = $("edit-line").value;
  const line = {id: selected || `line-${uid()}`, menu_id: $("menu").value, quantity: Number($("quantity").value), modifiers: [...$("modifier").selectedOptions].map(option => option.value).filter(Boolean), seat: $("seat").value ? Number($("seat").value) : null, requests: $("requests").value.trim()};
  const exists = order.lines.some(entry => entry.id === selected);
  const lines = exists ? order.lines.map(entry => entry.id === selected ? line : editableLine(entry)) : [...order.lines.map(editableLine), line];
  const data = await dispatch({action: "edit_draft", order_id: order.id, revision: order.revision, table_id: $("draft-table").value, lines});
  if (data) { $("edit-line").value = ""; loadLine(); }
});
$("remove-line").addEventListener("click", () => {
  const order = state.orders[draftId], selected = $("edit-line").value;
  if (!selected) { feedback("Select a saved line to remove.", true); return; }
  dispatch({action: "edit_draft", order_id: order.id, revision: order.revision, table_id: order.table_id, lines: order.lines.filter(line => line.id !== selected).map(editableLine)});
});
$("confirm-send").addEventListener("click", () => { const order = state.orders[draftId]; dispatch({action: "confirm_send", order_id: order.id, revision: order.revision, human_confirmed: true}); });
$("use-transcript").addEventListener("click", () => captureText());
for (const [id, target] of [["hold-talk", "order"], ["kitchen-hold", "kitchen"]]) {
  const button = $(id);
  button.addEventListener("pointerdown", event => { beginHold(event, target); if (holding) button.setPointerCapture(event.pointerId); });
  button.addEventListener("pointerup", event => endHold(event, false, target));
  button.addEventListener("pointercancel", event => endHold(event, true, target));
  button.addEventListener("keydown", event => { if ([" ", "Enter"].includes(event.key) && !event.repeat) beginHold(event, target); if (event.key === "Escape") endHold(event, true, target); });
  button.addEventListener("keyup", event => { if ([" ", "Enter"].includes(event.key)) endHold(event, false, target); });
  button.addEventListener("blur", event => endHold(event, true, target));
}
$("voice-login").addEventListener("submit", event => {
  event.preventDefault();
  voice.auth = btoa(`${$("voice-user").value}:${$("voice-pass").value}`);
  $("voice-pass").value = "";
  $("voice-login").hidden = true;
  feedback("Live mic unlocked for this tab. Hold to talk.");
});
$("kitchen-voice-form").addEventListener("submit", async event => { event.preventDefault(); const data = await dispatch({action: "kitchen_voice", text: $("kitchen-transcript").value.trim()}, "voice"); if (data) $("kitchen-transcript").value = ""; });
document.addEventListener("click", event => {
  const button = event.target.closest("[data-action]");
  if (!button || button.disabled || busy) return;
  const {action, id} = button.dataset;
  if (action === "resolve-flag") { const order = state.orders[draftId]; dispatch({action: "resolve_flag", order_id: order.id, revision: order.revision, flag_id: id, resolution: button.dataset.resolution}); }
  if (action === "acknowledge") dispatch({action: "acknowledge", order_id: id});
  if (action === "retry-zones") dispatch({action: "retry_zones", order_id: id});
  if (action === "start-dish") dispatch({action: "start_dish", dish_id: id});
  if (action === "ready-dish") dispatch({action: "ready_dish", dish_id: id, fallback_reason: fallbackReason(state.dishes[id])});
  if (action === "pickup-dish") dispatch({action: "pickup_dish", dish_id: id, fallback_reason: fallbackReason(state.dishes[id])});
  if (action === "deliver") dispatch({action: "deliver_order", order_id: id});
  if (action === "camera-status") dispatch({action: "camera_status", camera_id: id, status: button.dataset.status, reason: `Simulated ${button.dataset.status} camera state`}, "system");
  if (action === "zone-observation" || action === "hand-pass") { const zone = state.zones[id]; dispatch({action: "zone_observation", zone_id: id, assignment_version: zone.assignment_version, occupied: action === "hand-pass" || button.dataset.occupied === "true", stable_ms: action === "hand-pass" ? 200 : Math.max(1600, state.stable_ms_required || 1500), hand_present: action === "hand-pass"}, "camera"); }
  if (action === "reconcile-zone") { const zone = state.zones[id]; dispatch({action: "reconcile_zone", zone_id: id, assignment_version: zone.assignment_version, occupied: button.dataset.occupied === "true", reason: `Staff reviewed physical zone: ${button.dataset.occupied === "true" ? "plate present" : "empty"}`}); }
});
$("api-link").href = `${API}/docs`;
refresh();
loadVoiceStatus();
setInterval(refresh, 2000);
