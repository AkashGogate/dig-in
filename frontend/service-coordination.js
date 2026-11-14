/* Service integration seam: views project canonical order/dish state. Updates
 * are explicit operational messages, never food lifecycle transitions. Summary
 * text comes from the role-scoped backend and is never generated from captures.
 */
"use strict";
window.createServiceCoordination = function ({request, dispatch, getContext, esc}) {
  const el = id => document.getElementById(id);
  const human = value => String(value || "").replaceAll("_", " ");
  let previousSession = null, previousView = null, previousSignature = "";
  let renderSignature = "", requestGeneration = 0, speaking = false, speechGeneration = 0;
  const summaries = {server:null, kitchen:null}, loading = {server:false, kitchen:false};
  const synthesis = window.speechSynthesis;
  const speechAvailable = Boolean(synthesis && window.SpeechSynthesisUtterance);
  const allowed = (audience, context) => Boolean(context.session && (context.actor?.role === "lead" || context.actor?.role === (audience === "server" ? "server" : "cook")));
  function signature(state) {
    return JSON.stringify([state?.orders, state?.dishes, state?.service_updates, state?.zones, state?.cameras]);
  }
  function stopSpeech() {
    speechGeneration++;
    if (speechAvailable) synthesis.cancel();
    speaking = false;
    for (const audience of ["server","kitchen"]) el(`service-${audience}-stop`).disabled = true;
  }
  function clearSummaries() {
    requestGeneration++;
    el("service-print-title").textContent = ""; el("service-print-text").textContent = "";
    stopSpeech();
    for (const audience of ["server","kitchen"]) {
      summaries[audience] = null; loading[audience] = false;
      el(`service-${audience}-summary`).textContent = "Ask for a summary when you want a fresh service snapshot.";
      el(`service-${audience}-summary-meta`).textContent = "No summary requested in this session.";
    }
  }
  function sync() {
    const context = getContext(), currentSignature = signature(context.state);
    if (previousSession !== context.session) {
      previousSession = context.session; clearSummaries(); renderSignature = "";
    }
    if (previousView !== context.view) { previousView = context.view; requestGeneration++; loading.server = loading.kitchen = false; stopSpeech(); }
    if (!context.online) stopSpeech();
    if (previousSignature && previousSignature !== currentSignature) {
      stopSpeech();
      el("service-print-title").textContent = ""; el("service-print-text").textContent = "";
      for (const audience of ["server","kitchen"]) if (summaries[audience]) summaries[audience].stale = true;
    }
    previousSignature = currentSignature;
    const locked = context.busy || Boolean(context.uncertain) || !context.online;
    for (const audience of ["server","kitchen"]) {
      const ready = allowed(audience, context), summary = summaries[audience];
      el(`service-${audience}-ask`).disabled = !ready || locked || loading[audience];
      el(`service-${audience}-ask`).textContent = loading[audience] ? "Getting summary…" : "Ask for a summary";
      el(`service-${audience}-print`).disabled = !ready || !summary || summary.stale || locked || typeof window.print !== "function";
      el(`service-${audience}-speak`).disabled = !ready || !summary || summary.stale || locked || !speechAvailable;
      el(`service-${audience}-stop`).disabled = !speaking;
      el(`service-${audience}-permissions`).hidden = ready;
      if (summary) el(`service-${audience}-summary-meta`).textContent = `${summary.stale ? "STALE — service changed; ask again." : "Snapshot"} · ${new Date(summary.generated_at).toLocaleString()}${context.online ? "" : " · OFFLINE"}`;
      el(`service-${audience}-speech-note`).textContent = speechAvailable ? "Speak uses your browser/device voice only after you choose it. Select headphones in device settings; this app cannot guarantee earpiece routing or voice-provider retention." : "Spoken output is unavailable in this browser. The displayed summary and browser Print remain available.";
    }
    el("service-update-fields").disabled = !allowed("kitchen", context) || locked;
    el("service-update-submit").disabled = !allowed("kitchen", context) || locked || !el("service-update-order").value;
    if (context.state && renderSignature !== `${currentSignature}:${context.actor?.id}:${locked}`) {
      renderSignature = `${currentSignature}:${context.actor?.id}:${locked}`;
      renderUpdates(context, locked); renderLineup(context, locked); fillOrders(context);
      el("service-update-submit").disabled = !allowed("kitchen", context) || locked || !el("service-update-order").value;
    }
    refreshElapsedTimes();
  }
  function fillOrders(context) {
    const select = el("service-update-order"), before = select.value;
    const orders = Object.values(context.state.orders || {}).filter(order => !["draft","picked_up","delivered"].includes(order.status));
    select.innerHTML = '<option value="">Choose the exact ticket</option>' + orders.map(order => `<option value="${esc(order.id)}">Table ${esc(order.table_id)} · ${esc(order.id)} · ${esc(human(order.status))}</option>`).join("");
    if (orders.some(order => order.id === before)) select.value = before;
  }
  function replacePreservingFocus(id, markup) {
    const container=el(id), focused=document.activeElement;
    const owned=focused && container.contains?.(focused);
    const target=owned && focused !== container && focused.dataset ? {...focused.dataset} : null;
    container.innerHTML=markup;
    if (!owned) return;
    const buttons=[...container.querySelectorAll("button")];
    const replacement=target && buttons.find(button => !button.disabled && Object.entries(target).every(([key,value]) => button.dataset[key]===value));
    if (replacement) replacement.focus({preventScroll:true});
    else {container.setAttribute("tabindex","-1");container.focus({preventScroll:true});}
  }
  function renderUpdates(context, locked) {
    const updates = Object.values(context.state.service_updates || {});
    for (const audience of ["server","kitchen"]) {
      const visible = updates.filter(update => audience === "kitchen" ? allowed("kitchen", context) : update.recipient_id === context.actor?.id || context.actor?.role === "lead");
      replacePreservingFocus(`service-${audience}-updates`, visible.length ? visible.slice().reverse().map(update => {
        const order = context.state.orders[update.order_id];
        const actionable = audience === "server" && allowed("server",context) && (context.actor?.role === "lead" || update.recipient_id === context.actor?.id);
        const readyCount = Object.values(context.state.dishes || {}).filter(dish => dish.order_id === update.order_id && dish.stage === "ready").length;
        return `<article class="service-update"><div class="panel-heading"><h3>Table ${esc(order?.table_id || "unknown")} · ${esc(human(update.kind))}</h3><span class="status">${esc(human(update.status))}</span></div><p>${esc(update.note || "No additional staff note.")}</p>${update.kind === "pickup_request" ? `<p><strong>Current pickup state:</strong> ${readyCount ? `${readyCount} ready unit(s); check the current ticket below.` : "No ready units now. This earlier request is not proof a plate is ready."}</p>` : ""}<p class="note">Ticket ${esc(update.order_id)} · recipient ${esc(update.recipient_id)} · ${esc(update.created_at || "Time unknown")}</p>${actionable && update.status !== "resolved" ? `<button type="button" data-service-action="${update.status === "unread" ? "acknowledge_service_update" : "resolve_service_update"}" data-update-id="${esc(update.id)}" data-revision="${esc(update.revision)}" ${locked ? "disabled" : ""}>${update.status === "unread" ? "Acknowledge update" : "Mark coordination handled"}</button>` : ""}</article>`;
      }).join("") : `<p class="empty">${audience === "server" ? "No kitchen updates for your orders. Ready plates remain visible in your order list." : "No staff updates sent yet. Choose a ticket to contact its server."}</p>`);
    }
  }
  function elapsedText(timestamp) {
    return timestamp ? `${Math.max(0,Math.floor((Date.now()-Date.parse(timestamp))/60000))} min elapsed` : "Start time unknown";
  }
  function refreshElapsedTimes() {
    // Time changes without an event; update only text, never replace controls.
    for (const timer of el("service-kitchen-lineup").querySelectorAll?.("[data-service-elapsed]") || []) timer.textContent=elapsedText(timer.dataset.serviceElapsed);
  }
  function renderLineup(context, locked) {
    const orders = context.state.orders || {};
    const dishes = Object.values(context.state.dishes || {}).filter(dish => dish.stage !== "picked_up" && !["draft","delivered"].includes(orders[dish.order_id]?.status));
    replacePreservingFocus("service-kitchen-lineup", dishes.length ? dishes.map(dish => {
      const order = orders[dish.order_id];
      const editable = allowed("kitchen",context) && !locked;
      const zoneNeedsReview = Boolean(context.state.zones?.[dish.zone_id]?.needs_review);
      const next = order.status === "submitted" ? "Acknowledge the ticket below" : dish.stage === "queued" ? "Start this unit deliberately" : dish.stage === "started" ? "Cooking; mark ready only when finished and a zone is assigned" : "Ready for server pickup";
      const action = order.status !== "submitted" && (dish.stage === "queued" || dish.stage === "started" && dish.zone_id && !zoneNeedsReview) ? `<button type="button" data-service-dish-action="${dish.stage === "queued" ? "start_dish" : "ready_dish"}" data-dish-id="${esc(dish.id)}" ${editable ? "" : "disabled"}>${dish.stage === "queued" ? "Start dish" : "Tap ready"}</button>` : "";
      const modifiers=dish.modifier_names?.length ? dish.modifier_names : dish.modifiers || [];
      const elapsed=elapsedText(dish.started_at);
      return `<article class="service-lineup-unit"><div><h3>${esc(dish.item_name)} · table ${esc(order.table_id)}${dish.seat ? ` · seat ${esc(dish.seat)}` : ""}</h3><p><strong>Modifiers:</strong> ${esc(modifiers.join(", ") || "None configured")}</p>${dish.requests ? `<p class="service-guest-request"><strong>Guest request:</strong> ${esc(dish.requests)}</p>` : ""}<p><span data-service-elapsed="${esc(dish.started_at || "")}">${esc(elapsed)}</span> · ${dish.typical_minutes == null ? "Typical time unknown" : `Typical ${esc(dish.typical_minutes)} min`}</p><p>${esc(human(dish.stage))} · ${esc(dish.station || "Station unknown")} · ${dish.zone_id ? `Zone ${esc(dish.zone_id)}` : "No assigned zone"}</p><p class="note">${esc(next)}.${zoneNeedsReview ? " Review the unexpected/returned plate in the zone panel before marking ready." : ""}${!dish.zone_id && order.status !== "submitted" ? " Waiting for zone reservation; cooking and allocation are separate." : ""} Unit ${esc(dish.id)}</p></div>${action}</article>`;
    }).join("") : '<p class="empty">No active dish units. Submitted orders enter this lineup without inventing a cooking start.</p>');
  }
  async function ask(audience) {
    const context = getContext();
    if (!allowed(audience,context) || !context.online || context.busy || context.uncertain || loading[audience]) return;
    stopSpeech();
    const generation = requestGeneration, session = context.session, fingerprint = signature(context.state);
    loading[audience] = true; sync();
    try {
      const data = await request(`/api/v2/service/summary?audience=${audience}`, {headers:{"X-Demo-Session":session}});
      if (generation !== requestGeneration || session !== getContext().session) return;
      summaries[audience] = {...data, stale:fingerprint !== signature(getContext().state)};
      el(`service-${audience}-summary`).textContent = data.text;
      el(`service-${audience}-summary`).focus();
    } catch(error) {
      if (generation === requestGeneration) {
        summaries[audience] = null;
        el(`service-${audience}-summary`).textContent = `Summary unavailable. ${error.detail || "Reconnect and ask again; no service action was taken."}`;
        el(`service-${audience}-summary-meta`).textContent = "No current summary.";
      }
    } finally { if(generation === requestGeneration) loading[audience] = false; sync(); }
  }
  function speak(audience) {
    const context = getContext(), summary = summaries[audience];
    if (!speechAvailable || !allowed(audience,context) || !context.online || !summary || summary.stale || context.view !== audience) return;
    stopSpeech();
    const utterance = new window.SpeechSynthesisUtterance(summary.text);
    const speechToken = speechGeneration;
    utterance.onend = utterance.onerror = () => {if (speechToken === speechGeneration) {speaking=false;sync();}};
    speaking=true; synthesis.speak(utterance); sync();
  }
  function printSummary(audience) {
    const context = getContext(), summary = summaries[audience];
    if (!allowed(audience,context) || !context.online || !summary || summary.stale || typeof window.print !== "function") return;
    el("service-print-title").textContent = `${audience === "server" ? "Server" : "Kitchen"} service summary · ${summary.generated_at}`;
    el("service-print-text").textContent = summary.text;
    window.print();
  }
  for (const audience of ["server","kitchen"]) {
    el(`service-${audience}-ask`).addEventListener("click", () => ask(audience));
    el(`service-${audience}-speak`).addEventListener("click", () => speak(audience));
    el(`service-${audience}-stop`).addEventListener("click", stopSpeech);
    el(`service-${audience}-print`).addEventListener("click", () => printSummary(audience));
    el(`service-${audience}-updates`).addEventListener("click", event => {
      const button = event.target.closest("[data-service-action]");
      if (!button || button.disabled) return;
      const context=getContext();
      if (!allowed("server",context) || context.busy || context.uncertain || !context.online) return;
      dispatch({action:button.dataset.serviceAction,update_id:button.dataset.updateId,revision:Number(button.dataset.revision)});
    });
  }
  el("service-kitchen-lineup").addEventListener("click", event => {
    const button = event.target.closest("[data-service-dish-action]"), context = getContext();
    if (!button || button.disabled || !allowed("kitchen",context) || !context.online || context.busy || context.uncertain) return;
    const dish=context.state.dishes[button.dataset.dishId];
    if (!dish) return;
    const payload={action:button.dataset.serviceDishAction,dish_id:dish.id};
    if(payload.action === "ready_dish") {
      const camera=context.state.cameras?.[context.state.zones?.[dish.zone_id]?.camera_id];
      payload.fallback_reason=camera && camera.status!=="ok" ? `Camera ${camera.status}; staff used the tap alternative` : null;
    }
    dispatch(payload);
  });
  el("service-update-order").addEventListener("change", sync);
  el("service-update-form").addEventListener("submit", async event => {
    event.preventDefault();
    const context = getContext();
    if (!allowed("kitchen",context) || context.busy || context.uncertain || !context.online || !el("service-update-order").value) return;
    const result = await dispatch({action:"publish_service_update",order_id:el("service-update-order").value,kind:el("service-update-kind").value,note:el("service-update-note").value.trim()});
    if (result) el("service-update-note").value="";
  });
  window.addEventListener("pagehide", stopSpeech);
  sync();
  return {sync,stopSpeech};
};
