/* MVP client. Contracts are owned by backend/app/mvp; no localStorage authority.
 * Text simulators never claim microphone/camera processing or live Databricks.
 */
"use strict";
const API = (window.DIG_IN_API ?? "http://localhost:8000").replace(/\/$/, "");
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const uid = () => globalThis.crypto?.randomUUID?.() || `web-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const human = value => String(value || "").replaceAll("_", " ");
let state = null, actor = null, session = null, busy = false, uncertain = null;
let menuSetup = null, serviceCoordination = null, backendOnline = false;
let suggested = new Set();
let draftId = "", draftSignature = "", menuSignature = "", editorMenuSignature = "", view = "server", holding = false;

function feedback(message, error = false) {
  $("feedback").textContent = message;
  $("feedback").classList.toggle("error", error);
}
function connected(ok) {
  backendOnline = ok;
  menuSetup?.sync();
  serviceCoordination?.sync();
  $("connection").textContent = ok ? "Shared backend connected" : "Backend unavailable · UNSYNCED";
  $("connection").style.color = ok ? "var(--green)" : "var(--danger)";
}
async function request(path, {timeoutMs = 10000, ...options} = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API}${path}`, {...options, headers:{...(voice.auth?{Authorization:`Basic ${voice.auth}`} : {}),...options.headers}, signal: controller.signal});
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(`${response.status}: ${typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data)}`);
      error.rejected = true;
      error.status = response.status;
      error.detail = typeof data.detail === "string" ? data.detail : "Check the input fields and try again";
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
  menuSetup?.sync();
  serviceCoordination?.sync();
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
    menuSetup?.accepted(data, payload);
    const flags = data.result?.flags;
    if (Array.isArray(flags) && flags.length) {
      const message = flags.map(flag => typeof flag === "string" ? flag : flag.message || flag.code).join(" ");
      feedback(`Clarification needed: ${message}`, true);
      if (payload.action === "kitchen_voice") $("kitchen-clarification").textContent = message;
    } else {
      feedback(payload.action === "confirm_send" ? "Order submitted. Kitchen acknowledgment is a separate next step." : payload.action === "activate_menu" ? "Menu activated for new orders. Open drafts and tickets keep their original menu." : "Change accepted by the shared backend.");
      if (payload.action === "kitchen_voice") $("kitchen-clarification").textContent = "Kitchen phrase accepted. Check the exact ticket and dish below.";
    }
    return data;
  } catch (error) {
    if (error.rejected) menuSetup?.rejected(payload, error);
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
function menuForOrder(orderId = draftId) {
  return state?.menus?.[state?.orders?.[orderId]?.menu_revision] || state?.menu;
}
function items() { return menuForOrder()?.items || []; }
function menuItem(id) { return items().find(item => item.id === id); }
function modifierNames(menuId, ids = [], orderId = draftId) {
  const modifiers = menuForOrder(orderId)?.items.find(item => item.id === menuId)?.modifiers || [];
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
  if(capture && !currentCapture(capture))cancelLive();
  const currentMenuSignature = JSON.stringify(state.menu);
  if (menuSignature !== currentMenuSignature) {
    menuSignature = currentMenuSignature;
    const tables = Object.values(state.tables).map(table => [table.id, `Table ${table.id}`]);
    fillSelect("start-table", tables);
    fillSelect("draft-table", tables);
    fillSelect("actor", Object.values(state.actors).map(person => [person.id, `${person.name} · ${person.role}`]));
    $("menu-summary").innerHTML = state.menu.items.map(item => `<div class="menu-item"><strong>${esc(item.name)}</strong>${item.description ? `<p>${esc(item.description)}</p>` : ""}<p>${item.price_cents == null ? "Price unknown" : new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"}).format(item.price_cents / 100)}</p><p class="note">${item.station ? esc(item.station) : "Station unknown"} · ${item.typical_minutes == null ? "Typical time unknown" : `Typical ${esc(item.typical_minutes)} min`}</p></div>`).join("");
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
  const editorSignature = order.menu_revision || state.menu_revision;
  if (editorMenuSignature !== editorSignature) {
    editorMenuSignature = editorSignature;
    fillSelect("menu", items().map(item => [item.id, item.name]));
    refreshModifiers();
    const examples = items().slice(0, 2).map(item => `one ${item.aliases?.[0] || item.name}`).join(" and ");
    $("transcript").placeholder = `Table ${order.table_id}: ${examples || "one configured menu item"}`;
  }
  const signature = JSON.stringify([order, state.menu_revision]);
  if (signature === draftSignature) return;
  draftSignature = signature;
  $("draft-summary").innerHTML = `<div class="draft-title"><strong>Table ${esc(order.table_id)}</strong><span class="status">Draft · revision ${order.revision}</span></div>${lineList(order)}<p class="note">Ticket ${esc(order.id)} · corrections measured at submission${order.menu_revision !== state.menu_revision ? " · This draft keeps its original menu; new orders use the current menu." : ""}</p>`;
  $("draft-table").value = order.table_id || "";
  fillSelect("edit-line", order.lines.map(line => [line.id, `${line.quantity} × ${line.item_name || menuItem(line.menu_id)?.name || line.menu_id}`]), "New dish line");
  $("draft-flags").innerHTML = (order.flags || []).map(flagMarkup).join("");
  const count = order.lines.reduce((total, line) => total + line.quantity, 0);
  $("send-note").textContent = `Review table ${order.table_id}, ${count} physical dish units, modifiers and requests. Your tap approves revision ${order.revision}.`;
  $("confirmation-blocker").textContent = order.flags?.length ? "Submission blocked: resolve each table/menu flag above, then review the draft." : !count ? "Add at least one dish before sending." : "Ready for human review. Voice never submits.";
}
function lineList(order) {
  return order.lines.length ? order.lines.map(line => `<div class="order-line"><div><strong>${line.quantity} × ${esc(line.item_name || menuItem(line.menu_id)?.name || line.menu_id)}</strong><small>${line.seat ? `Seat ${line.seat} · ` : ""}${esc((line.modifier_names || modifierNames(line.menu_id, line.modifiers, order.id)).join(", ") || "No modifiers")}</small>${line.requests ? `<small><strong>Guest request:</strong> ${esc(line.requests)}</small>` : ""}</div></div>`).join("") : '<p class="empty">No dishes entered. Nothing has been sent.</p>';
}
function flagMarkup(flag) {
  const resolve = (resolution, label) => `<button data-action="resolve-flag" data-id="${esc(flag.id)}" data-resolution="${resolution}" data-command>${label}</button>`;
  if (flag.code === "dietary_check_required") return `<article class="review-flag" role="alert"><strong>Ask the table about allergies or dietary needs</strong><p>Record the answer before sending. If anyone has a need, say it after the dish (for example "one bulldozer, seat 2, allergy to gluten") or type it in that dish's request field.</p><div class="actions">${resolve("asked_none_reported", "Asked: none")}</div></article>`;
  if (flag.code === "dietary_review" || flag.code === "dietary_unattached") return `<article class="review-flag"><strong>${flag.code === "dietary_review" ? "Check the dietary note" : "Attach this dietary note to a dish"}</strong><p>${esc(flag.message)}</p><div class="actions">${resolve("reviewed_keep_note", flag.code === "dietary_review" ? "Note is correct" : "Attach to selected saved dish")}</div><p class="note">Speech-to-text can mishear. For an unattached note, select its saved dish under “Add or edit line” below before attaching; this preserves the note on that dish. Correct an attached dish request manually before confirming.</p></article>`;
  const mismatch = flag.code === "table_mismatch";
  const tableRequired = flag.code === "table_required";
  const candidates = flag.candidates?.map(id => menuItem(id)?.name || (typeof id === "string" ? id : JSON.stringify(id))) || [];
  return `<article class="review-flag"><strong>${mismatch ? "Resolve the table mismatch" : tableRequired ? "Confirm the selected table" : "Review an uncertain draft"}</strong><p>${esc(flag.message || human(flag.code))}</p>${candidates.length ? `<p>Candidates: ${esc(candidates.join(", "))}</p>` : ""}${["unknown_item", "ambiguous_item"].includes(flag.code) ? (flag.candidates || []).filter(id => menuItem(id)).map(id => `<button type="button" data-action="use-candidate" data-menu="${esc(id)}" data-command>Use ${esc(menuItem(id).name)}</button>`).join("") : ""}<div class="actions">${mismatch || tableRequired ? `<button data-action="resolve-flag" data-id="${esc(flag.id)}" data-resolution="keep_selected_table" data-command>Keep selected table</button>${mismatch ? `<button data-action="resolve-flag" data-id="${esc(flag.id)}" data-resolution="use_spoken_table" data-command>Use spoken table</button>` : ""}` : `<button data-action="resolve-flag" data-id="${esc(flag.id)}" data-resolution="reviewed_remove_unknown" data-command>Reviewed — omit uncertain words</button>`}</div><p class="note">Use manual entries below for the intended item. No candidate is chosen automatically.</p></article>`;
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
  return `<div class="dish${mark ? " suggested" : ""}"><div>${mark ? '<span class="suggested-tag">Suggested by voice, tap to confirm</span>' : ""}<p><strong>${esc(dish.item_name || menuItem(dish.menu_id)?.name || dish.menu_id)}</strong>${dish.seat ? ` · seat ${dish.seat}` : ""}</p><small>Unit ${esc(dish.id)} · ${dish.zone_id ? `Zone ${esc(dish.zone_id)}` : "No zone assigned"}${dish.station ? ` · ${esc(dish.station)}` : " · station unknown"}</small><p class="dish-timer">${esc(elapsed(dish.started_at))} · ${dish.typical_minutes == null ? "typical time unknown" : `typical ${esc(dish.typical_minutes)} min`}</p>${dish.modifiers?.length ? `<small>${esc((dish.modifier_names || modifierNames(dish.menu_id, dish.modifiers, dish.order_id)).join(", "))}</small>` : ""}${dish.requests ? `<small><strong>Guest request:</strong> ${esc(dish.requests)}</small>` : ""}<span class="dish-stage">${esc(human(dish.stage))}</span></div><div class="actions">${controls}</div></div>`;
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
  if(capture && name!==view)cancelLive();
  if (holding) endHold(null, true);
  view = name;
  document.querySelectorAll(".view").forEach(element => element.hidden = element.id !== `${name}-view`);
  document.querySelectorAll(".view-nav [data-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === name)));
  document.title = `Dig In · ${name === "menu-setup" ? "Menu setup" : name}`;
  if (name === "menu-setup") $("menu-setup-title").focus();
  serviceCoordination?.sync();
}
async function captureText(captureMode = "mock_voice") {
  const order = state?.orders[draftId];
  if (!order) { feedback("Start an order before capturing a read-back.", true); return; }
  const text = $("transcript").value.trim();
  if (!text) { feedback("Enter a mock transcript first. No microphone is connected.", true); return; }
  const data = await dispatch({action: "capture_voice", order_id: order.id, revision: order.revision, text, capture_mode: captureMode}, "voice");
  if (data) $("transcript").value = "";
}
let voice = {live: false, authRequired: false, auth: null}, capture = null, captureEpoch = 0;
async function loadVoiceStatus() {
  try {
    const status = await request("/api/v2/voice/status");
    voice.live = Boolean(status.live_capture_available);
    voice.authRequired = Boolean(status.auth_required);
  } catch { voice.live = false; }
  $("voice-mode-tag").textContent = voice.live ? "LIVE MIC CONFIGURED · DEEPGRAM" : "SIMULATED TRANSCRIPTION";
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
  $("kitchen-voice-mode").textContent = voice.live ? "LIVE MIC CONFIGURED · DEEPGRAM" : "TEXT SIMULATOR";
}
const captureUi = target => target === "kitchen"
  ? {field: $("kitchen-transcript"), status: $("kitchen-capture-status"), button: $("kitchen-hold")}
  : {field: $("transcript"), status: $("capture-status"), button: $("hold-talk")};
const voiceContext = () => ({session,actorId:actor?.id,role:actor?.role,view,order:state?.orders?.[draftId],menuRevision:state?.menu_revision});
const currentCapture = cap => capture === cap && !cap.cancelled && window.DigInVoiceAudio.matches(cap.pin,voiceContext());
function stopInput(cap) {
  cap.processor?.disconnect(); cap.source?.disconnect(); cap.silence?.disconnect();
  cap.media?.getTracks().forEach(track => track.stop());
  if (cap.audio && cap.audio.state !== "closed") cap.audio.close().catch(()=>{});
}
function stopMedia(cap) {
  stopInput(cap);
  if (cap.ws && cap.ws.readyState <= 1) cap.ws.close();
}
function cancelLive() {
  if (!capture) return;
  captureEpoch++;
  const cap=capture; cap.cancelled=true; cap.stopped=true; holding=false;
  cap.ui.button.classList.remove("holding");cap.ui.button.setAttribute("aria-pressed","false");
  stopMedia(cap);cap.ui.field.value="";cap.ui.status.textContent="Capture cancelled because the draft, session or screen changed. Nothing was applied.";
  capture=null;
}
async function startLive(target) {
  const ui=captureUi(target), Audio=window.AudioContext || window.webkitAudioContext;
  if (voice.authRequired && !voice.auth) {
    $("voice-login").hidden=false;$("voice-user").focus();ui.status.textContent="Enter the demo login above to unlock the live mic.";return false;
  }
  if (!Audio || !navigator.mediaDevices?.getUserMedia) {
    ui.status.textContent="Live voice needs a secure browser with microphone and AudioContext support. Use typed text or manual entry.";return false;
  }
  const cap=capture={target,ui,pin:window.DigInVoiceAudio.pin(target,voiceContext()),text:"",stopped:false,cancelled:false};
  const abandoned=()=>!currentCapture(cap) || cap.stopped;
  try {
    const ticket=await request("/api/v2/voice/ticket",{method:"POST",headers:{"Content-Type":"application/json","X-Demo-Session":cap.pin.session,...(voice.auth?{Authorization:`Basic ${voice.auth}`}:{})},body:JSON.stringify({order_id:cap.pin.orderId,menu_revision:cap.pin.menuRevision})});
    if(abandoned()){stopMedia(cap);if(capture===cap)capture=null;return false;}
    cap.media=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true}});
    if(abandoned()){stopMedia(cap);if(capture===cap)capture=null;return false;}
    const endpoint=window.DIG_IN_VOICE_WS || `${(API || location.origin).replace(/^http/,"ws")}/api/v2/voice/stream`;
    const ws=cap.ws=new WebSocket(`${endpoint}?ticket=${encodeURIComponent(ticket.ticket)}&session_id=${encodeURIComponent(cap.pin.session)}`);
    cap.done=new Promise(resolve=>{
      ws.addEventListener("message",event=>{
        let message;try{message=JSON.parse(event.data);}catch{return;}
        if(!currentCapture(cap)) return;
        if(message.type==="interim" || message.type==="final")ui.field.value=message.text;
        if(["limit","error","done"].includes(message.type)) {
          stopInput(cap);cap.stopped=true;holding=false;ui.button.classList.remove("holding");ui.button.setAttribute("aria-pressed","false");
          if(message.type==="error")cap.error=message.message;
          if(message.type==="done")cap.text=message.text || "";
          if(message.message)ui.status.textContent=message.message;
          if(message.type==="done" || message.type==="error") {resolve();queueMicrotask(()=>finishLive(cap));}
          else if(ws.readyState===1)ws.send(JSON.stringify({type:"stop"}));
        }
      });
      ws.addEventListener("close",()=>{stopInput(cap);cap.stopped=true;holding=false;resolve();queueMicrotask(()=>finishLive(cap));});
    });
    await new Promise((resolve,reject)=>{ws.addEventListener("open",resolve,{once:true});ws.addEventListener("error",()=>reject(new Error("Live stream unavailable")),{once:true});ws.addEventListener("close",()=>reject(new Error("Live stream refused")),{once:true});});
    if(abandoned()){stopMedia(cap);if(capture===cap)capture=null;return false;}
    cap.audio=new Audio();await cap.audio.resume();
    if(abandoned()){stopMedia(cap);if(capture===cap)capture=null;return false;}
    cap.source=cap.audio.createMediaStreamSource(cap.media);
    // Replaceable browser producer seam: PCM16 samples, 16kHz mono. A future
    // AudioWorklet can replace ScriptProcessor without changing server limits.
    cap.processor=cap.audio.createScriptProcessor(4096,1,1);cap.silence=cap.audio.createGain();cap.silence.gain.value=0;
    cap.processor.onaudioprocess=event=>{
      if(!currentCapture(cap) || cap.stopped || ws.readyState!==1)return;
      ws.send(window.DigInVoiceAudio.pcm16(event.inputBuffer.getChannelData(0),cap.audio.sampleRate));
    };
    cap.source.connect(cap.processor);cap.processor.connect(cap.silence);cap.silence.connect(cap.audio.destination);
    cap.timer=setTimeout(()=>{if(currentCapture(cap)){cap.stopped=true;holding=false;finishLive(cap);}},ticket.max_stream_seconds*1000);
    ui.status.textContent=`Listening (max ${Math.round(ticket.max_stream_seconds)}s). Release to stop.`;
    return true;
  } catch(error) {
    if(error.status===401 && capture===cap && !cap.cancelled){voice.auth=null;$("voice-login").hidden=false;}
    stopMedia(cap);if(capture===cap)capture=null;
    if(!cap.cancelled && !capture)ui.status.textContent=`Live mic unavailable: ${error.message}. Type the order or use manual entry.`;
    return false;
  }
}
async function finishLive(cap) {
  if(cap.finishing || cap.cancelled)return;
  cap.finishing=true;cap.stopped=true;clearTimeout(cap.timer);stopInput(cap);
  cap.ui.button.classList.remove("holding");cap.ui.button.setAttribute("aria-pressed","false");
  if(cap.ws?.readyState===1)cap.ws.send(JSON.stringify({type:"stop"}));
  cap.ui.status.textContent="Finishing transcription…";
  await Promise.race([cap.done || Promise.resolve(),new Promise(resolve=>setTimeout(resolve,10000))]);
  if(!currentCapture(cap)){stopMedia(cap);return;}
  stopMedia(cap);capture=null;
  const text=cap.text.trim();
  if(cap.error || !text){cap.ui.field.value="";cap.ui.status.textContent=cap.error || "Nothing was heard. Try again or use manual entry.";return;}
  const payload=cap.target==="kitchen"?{action:"kitchen_voice",text}:{action:"capture_voice",order_id:cap.pin.orderId,revision:cap.pin.revision,text,capture_mode:"live_voice"};
  const data=await dispatch(payload,"voice");
  if(data)cap.ui.field.value="";
  cap.ui.status.textContent=cap.target==="order"?"Review the draft and tap Confirm and send when correct.":"Review the exact ticket/unit result below.";
}
function beginHold(event, target = "order") {
  if (busy || uncertain || !session || holding) return;
  if (target === "kitchen" && !kitchenRole()) { feedback("Kitchen voice is for cook or lead sessions. Enter a kitchen session first.", true); return; }
  if (target === "order" && !state?.orders[draftId]) { feedback("Start an order before capturing a read-back.", true); return; }
  event?.preventDefault();
  serviceCoordination?.stopSpeech();
  holding = true;
  const ui = captureUi(target);
  ui.button.classList.add("holding");
  ui.button.setAttribute("aria-pressed", "true");
  const attempt = ++captureEpoch;
  if (voice.live) { ui.status.textContent = "Starting live mic…"; startLive(target).then(ok => { if (!ok && attempt === captureEpoch) { holding = false; ui.button.classList.remove("holding"); ui.button.setAttribute("aria-pressed", "false"); } }); }
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
    if(cancelled){cancelLive();return;}
    finishLive(capture);
    return;
  }
  if (voice.live) return;
  $("capture-status").textContent = cancelled ? "Capture cancelled. Nothing was sent." : "Released. The draft still needs human review and Confirm and send.";
  if (!cancelled) captureText();
}
$("connect").addEventListener("click", async () => {
  if (busy || uncertain) { feedback("Resolve the pending event before switching sessions.", true); return; }
  cancelLive();
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
$("draft-select").addEventListener("change", () => { cancelLive(); draftId = $("draft-select").value; draftSignature = ""; renderDraft(); setBusy(busy); });
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
  if (action === "use-candidate") {
    $("manual-editor").open = true;
    $("edit-line").value = "";
    $("menu").value = button.dataset.menu;
    refreshModifiers();
    $("quantity").value = 1;
    $("quantity").focus();
    feedback(`Filled in ${menuItem(button.dataset.menu)?.name}. Check the quantity and modifiers, save the line, then dismiss the uncertain words.`);
  }
  if (action === "resolve-flag") { const order = state.orders[draftId], flag=order.flags.find(flag=>flag.id===id); dispatch({action: "resolve_flag", order_id: order.id, revision: order.revision, flag_id: id, resolution: button.dataset.resolution,...(flag?.code === "dietary_unattached" ? {line_id:$("edit-line").value || null} : {})}); }
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
menuSetup = window.createMenuSetup({request, dispatch, esc, getContext: () => ({state, actor, session, busy, uncertain, online: backendOnline})});
serviceCoordination = window.createServiceCoordination({request, dispatch, esc, getContext: () => ({state, actor, session, busy, uncertain, online: backendOnline, view})});
$("api-link").href = `${API}/api/v2/contracts`;
refresh();
loadVoiceStatus();
window.addEventListener("pagehide",cancelLive);
setInterval(refresh, 2000);
