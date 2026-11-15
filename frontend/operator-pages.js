/* Real operator pages for the teammate UI. data.js is the transport/authority
 * seam; this file owns presentation only. Full live voice, OCR and recovery
 * controls remain in index.html, preserving their reviewed integration paths.
 */
(function () {
  'use strict';
  const {createClient,escape:e,editableLine,menuFor,ownOrders,unitsFor} = DigInOperator;
  const client = createClient(), page = document.body.dataset.operatorPage;
  const kitchen = page === 'kitchen', composer = page === 'order';
  const $ = id => document.getElementById(id);
  let editor = null, selectedDraft = '', localDirty = false, search = '', category = '', station = '', kitchenTab = 'tickets', kitchenSummaryOpen = false;
  let summary = null, summaryPending = false, signature = '', renderPending = false;
  const unitDetails = new Map();
  const updateForms = new Map(); // Unsaved explicit staff notes only; never browser storage.
  const uid = () => crypto.randomUUID();
  const canOperate = ctx => Boolean(ctx.session && ctx.online && !ctx.needsAuth && !ctx.busy && !ctx.uncertain && (kitchen ? ['cook','lead'].includes(ctx.actor?.role) : ['server','lead'].includes(ctx.actor?.role)));
  const feedback = (message,error=false) => { $('operatorFeedback').textContent = message; $('operatorFeedback').classList.toggle('error',error); };
  const human = value => String(value || '').replaceAll('_',' ');
  const action = (label, name, id, extra='') => `<button class="operator-action" data-action="${name}" data-id="${e(id)}" ${extra}>${e(label)}</button>`;
  const ticketLabel = order => `Table ${order.table_id} · ticket ${order.id}`;
  function safeRender(html) {
    const focused = document.activeElement, container = $('operatorMain');
    if (container.contains(focused) && ['INPUT','TEXTAREA','SELECT'].includes(focused.tagName)) {renderPending=true;return;}
    const id = container.contains(focused) ? focused.id : null;
    const attrs = container.contains(focused) && focused.tagName === 'BUTTON' ? {...focused.dataset} : null;
    container.innerHTML = html;
    if (id) document.getElementById(id)?.focus({preventScroll:true});
    else if (attrs) [...container.querySelectorAll('button')].find(b => Object.entries(attrs).every(([k,v]) => b.dataset[k] === v))?.focus({preventScroll:true});
    renderPending=false;
  }
  function syncLocks(ctx) {
    $('operatorLogin').hidden = !ctx.needsAuth;
    $('operatorLoginSubmit').disabled = ctx.busy;
    $('enterSession').disabled = ctx.needsAuth || ctx.busy || Boolean(ctx.uncertain);
    $('operatorActor').disabled = ctx.busy || Boolean(ctx.uncertain);
    $('operatorRetryBar').hidden = !ctx.uncertain;
    $('operatorRetry').disabled = ctx.busy || !ctx.online || ctx.needsAuth;
    $('operatorIdentity').textContent = ctx.actor ? `${ctx.actor.name} · ${ctx.actor.role} · simulated session` : 'Select a staff member to enter a simulated session.';
    $('operatorConnection').textContent = ctx.needsAuth ? 'Demo sign-in required' : ctx.online ? 'Shared backend connected' : 'UNSYNCED · backend unavailable';
    document.querySelectorAll('#operatorMain button[data-action]').forEach(b => {
      b.disabled = !canOperate(ctx) || b.dataset.disabled === 'true';
      if (b.dataset.action === 'confirm') b.disabled ||= localDirty || !editor || !editor.lines.length || Boolean(editor.flags.length) || ctx.state.orders[editor.id]?.revision !== editor.revision;
      if (b.dataset.action === 'summary') b.disabled ||= summaryPending;
      if (b.dataset.action === 'save') b.disabled ||= !editor || ctx.state.orders[editor.id]?.revision !== editor.revision;
      if (b.dataset.action === 'flag') b.disabled ||= localDirty;
    });
    document.querySelectorAll('#operatorMain input,#operatorMain select,#operatorMain textarea').forEach(el => {el.disabled = !canOperate(ctx);});
  }
  function elapsed() {
    document.querySelectorAll('[data-started]').forEach(el => {
      const seconds = Math.max(0,Math.floor((Date.now()-Date.parse(el.dataset.started))/1000));
      el.textContent = `${Math.floor(seconds/60)} min elapsed`;
    });
  }
    // Ticket age is explicitly since submission, never a cooking estimate.
  function ticketAge() {
    document.querySelectorAll('[data-submitted]').forEach(el=>{
      const minutes=Math.max(0,Math.floor((Date.now()-Date.parse(el.dataset.submitted))/60000));
      el.textContent=`${minutes}m since sent`;
      el.classList.toggle('warn',minutes>=10&&minutes<15);el.classList.toggle('crit',minutes>=15);
    });
  }
  function openEditor(order) {
    if (!order) {editor=null;return;}
    editor = {...order, lines:order.lines.map(editableLine),flags:[...order.flags]};
    selectedDraft=order.id;localDirty=false;
  }
  function menuMarkup(ctx) {
    const menu = menuFor(ctx.state,editor), items = menu?.items || [];
    const categories = [...new Set(items.map(i=>i.category).filter(Boolean))];
    const filtered=items.filter(i=>(!search || i.name.toLowerCase().includes(search.toLowerCase())) && (!category || i.category===category));
    return `<section class="operator-card"><h2>${e(menu?.name || 'Menu unavailable')}</h2>
      <p class="operator-hint">${editor ? `Pinned menu ${e(editor.menu_revision)}. Imported menus apply to new drafts.` : 'Start or select a draft to add dishes.'} Prices and preparation times are unknown when not supplied.</p>
      <div class="operator-controls"><label>Search <input id="operatorSearch" type="search" value="${e(search)}" autocomplete="off"></label><label>Category <select id="operatorCategory"><option value="">All</option>${categories.map(c=>`<option ${category===c?'selected':''} value="${e(c)}">${e(c)}</option>`).join('')}</select></label></div>
      <div class="operator-menu">${filtered.map(i=>`<button class="item-card" data-action="add" data-id="${e(i.id)}" ${!editor?'data-disabled="true"':''}><div class="item-name">${e(i.name)}</div><div class="item-price">${i.price_cents==null?'Price unknown':`$${(i.price_cents/100).toFixed(2)}`}</div><p class="operator-label">${e(i.description || '')}</p></button>`).join('') || '<p>No matching dishes.</p>'}</div></section>`;
  }
  function flagsMarkup() {
    return editor.flags.map(flag=>`<div class="operator-flag"><strong>Review required: ${e(human(flag.code))}</strong><p>${e(flag.message)}</p>
      ${['table_mismatch','table_required'].includes(flag.code)?action('Keep selected table','flag',flag.id,'data-resolution="keep_selected_table"')+(flag.code==='table_mismatch'?' '+action('Use spoken table','flag',flag.id,'data-resolution="use_spoken_table"'):''):
        flag.code==='low_confidence'?action('Reviewed speech against this draft','flag',flag.id,'data-resolution="reviewed_speech"'):
        flag.code==='dietary_check_required'?action('Asked guest: none reported','flag',flag.id,'data-resolution="asked_none_reported"'):
        flag.code==='dietary_review'?action('Reviewed: keep this guest note','flag',flag.id,'data-resolution="reviewed_keep_note"'):
        flag.code==='dietary_unattached'?`<label>Attach note to dish <select id="attach-${e(flag.id)}">${editor.lines.map(line=>`<option value="${e(line.id)}">${e(menuFor(client.context().state,editor)?.items.find(i=>i.id===line.menu_id)?.name || line.menu_id)} · ${e(line.id)}</option>`).join('')}</select></label>${action('Attach and keep guest note','flag',flag.id,'data-resolution="reviewed_keep_note"')}`:
        action('Reviewed: remove unknown phrase','flag',flag.id,'data-resolution="reviewed_remove_unknown"')}
      <p class="operator-label">Save local edits before resolving. The workbench provides the complete voice/correction flow.</p></div>`).join('');
  }
  function editorMarkup(ctx) {
    if (!editor) return '<section class="operator-card"><h2>Start an order</h2><p>Choose a configured table, then start a draft. Nothing is sent to Kitchen until you review and press Confirm and send.</p></section>';
    const menu=menuFor(ctx.state,editor), latest=ctx.state.orders[editor.id];
    const stale=latest?.revision!==editor.revision;
    return `<section class="operator-card"><h2>Review order</h2><p class="operator-label">${e(editor.id)} · saved revision ${editor.revision} · ${e(editor.capture_mode)}</p>
      <label>Table <select id="editorTable">${Object.values(ctx.state.tables).map(t=>`<option value="${e(t.id)}" ${t.id===editor.table_id?'selected':''}>Table ${e(t.id)}</option>`).join('')}</select></label>
      <p class="operator-hint">${editor.lines.reduce((n,l)=>n+l.quantity,0)} physical dishes · each requires its own kitchen zone. Submit, acknowledgment, cooking, ready and pickup are separate milestones.</p>
      <div class="operator-form">${editor.lines.map(line=>{
        const item=menu?.items.find(i=>i.id===line.menu_id), seats=ctx.state.tables[editor.table_id]?.seats || [];
        return `<div class="operator-unit" data-line="${e(line.id)}"><strong>${e(item?.name || line.menu_id)}</strong><p class="operator-label">Line ${e(line.id)}</p>
          <div class="operator-controls"><label>Quantity <input type="number" min="1" max="12" data-field="quantity" data-line-id="${e(line.id)}" value="${line.quantity}"></label><label>Seat <select data-field="seat" data-line-id="${e(line.id)}"><option value="">Unassigned</option>${seats.map(s=>`<option value="${s}" ${s===line.seat?'selected':''}>Seat ${s}</option>`).join('')}</select></label></div>
          <div class="operator-modifiers">${(item?.modifiers || []).map(m=>`<label><input type="checkbox" data-field="modifier" data-modifier="${e(m.id)}" data-line-id="${e(line.id)}" ${line.modifiers.includes(m.id)?'checked':''}>${e(m.name)}</label>`).join('')}</div>
          <label>Guest requests / allergies <textarea rows="2" maxlength="500" data-field="requests" data-line-id="${e(line.id)}">${e(line.requests)}</textarea></label>
          ${action('Remove dish','remove',line.id)}</div>`;
      }).join('') || '<p>Add at least one dish from the menu.</p>'}</div>
      ${flagsMarkup()}
      <p id="editorSaveState" class="operator-hint">${stale?'Shared draft changed. Local text is preserved. Discard local edits to load its current revision.':localDirty?'Unsaved edits. Save and review the accepted revision before confirming.':'Saved revision ready for review.'}</p>
      <div class="operator-controls">${action('Save draft','save',editor.id,stale?'data-disabled="true"':'')}${action('Discard local edits / reload','reload',editor.id)}${action('Confirm and send','confirm',editor.id)}</div>
      <p class="operator-hint">Voice capture and menu PDF/photo upload: <a href="index.html">open the full workbench</a>, enter this staff member again and select this draft.</p>
      <button disabled title="The canonical MVP does not yet store delivery mode">Delivery preference · future integration</button></section>`;
  }
  function composerMarkup(ctx) {
    const drafts=ownOrders(ctx.state,ctx.actor).filter(o=>o.status==='draft');
    if (!editor && drafts.length) openEditor(drafts.find(o=>o.id===selectedDraft) || drafts[0]);
    if (editor && ctx.state.orders[editor.id]?.status!=='draft') {editor=null;selectedDraft='';localDirty=false;}
    if (editor && !localDirty && ctx.state.orders[editor.id]?.revision!==editor.revision) openEditor(ctx.state.orders[editor.id]);
    return `<div class="operator-controls"><label>Configured table <select id="newTable">${Object.values(ctx.state.tables).map(t=>`<option value="${e(t.id)}">Table ${e(t.id)}</option>`).join('')}</select></label>${action('Start new draft','start','')}
      <label>Saved draft <select id="draftPicker"><option value="">Choose draft</option>${drafts.map(o=>`<option value="${e(o.id)}" ${o.id===selectedDraft?'selected':''}>${e(ticketLabel(o))}</option>`).join('')}</select></label></div>
      <div class="operator-layout">${menuMarkup(ctx)}${editorMarkup(ctx)}</div>`;
  }
  function unitMarkup(ctx,order,dish) {
    const zone=ctx.state.zones[dish.zone_id];
    const startAllowed=['acknowledged','cooking'].includes(order.status) && dish.stage==='queued';
    const readyAllowed=['queued','started'].includes(dish.stage) && Boolean(order.acknowledged_at) && zone?.dish_id===dish.id && !zone.needs_review;
    const pickupAllowed=dish.stage==='ready' && zone?.dish_id===dish.id && !zone.needs_review;
    const operations=kitchen ? (startAllowed?action('Start unit','start_dish',dish.id):'')+' '+(readyAllowed?action('Tap ready · finished plate verified','ready_dish',dish.id):'') : (pickupAllowed?action('Pick up this unit','pickup_dish',dish.id):'');
    if(kitchen) return `<div class="dish" data-unit="${e(dish.id)}"><div class="dish-main"><div class="dish-name">${e(dish.item_name)}</div>
      <div class="dish-meta">${dish.seat==null?'Seat unassigned':`Seat ${dish.seat}`} · ${dish.stage==='picked_up'?`Last zone ${e(dish.zone_id || 'unknown')} · released`:dish.zone_id?`Physical zone ${e(dish.zone_id)}`:'Waiting for a physical zone'} · ${e(dish.station || 'Station unknown')} · ${e(dish.modifier_names?.join(', ') || 'No modifiers')}</div>
      <p class="dish-requests">Guest requests: ${e(dish.requests || 'None recorded')}</p>
      <div class="dish-meta">${dish.started_at?`<span data-started="${e(dish.started_at)}"></span>`:dish.stage==='queued'?'Not started':'Start time unknown'} · ${dish.typical_minutes==null?'Usual time unknown':`Usually ${dish.typical_minutes} min`}</div>
      ${zone?.needs_review?'<p class="operator-warning">Zone requires staff review in the full workbench before ready/pickup.</p>':''}
      <details class="dish-provenance" data-unit-details="${e(dish.id)}" ${unitDetails.get(dish.id)?'open':''}><summary id="unit-details-${e(dish.id)}">Unit details</summary><p class="operator-label">Unit ${e(dish.id)} · ${e(dish.line_id)}</p></details>
      <div class="dish-actions">${operations}</div></div><div class="dish-right"><span class="d-status ${e(dish.stage)}"><span class="dot" aria-hidden="true"></span>${e(human(dish.stage))}</span></div></div>`;
    return `<div class="operator-unit"><strong>${e(dish.item_name)}</strong> <span class="operator-pill">${e(human(dish.stage))}</span>
      <p>${dish.seat==null?'Seat unassigned':`Seat ${dish.seat}`} · ${e(dish.station || 'Station unknown')} · ${dish.stage==='picked_up'?`Last zone ${e(dish.zone_id || 'unknown')} · released`:dish.zone_id?`Physical zone ${e(dish.zone_id)}`:'Waiting for a physical zone'}</p>
      <p>Modifiers: ${e(dish.modifier_names?.join(', ') || 'None')}</p><p class="operator-notes">Guest requests: ${e(dish.requests || 'None recorded')}</p>
      <p>${dish.started_at?`<span data-started="${e(dish.started_at)}"></span>`:dish.stage==='queued'?'Not started':'Start time unknown'} · ${dish.typical_minutes==null?'Usual time unknown':`Usually ${dish.typical_minutes} min`}</p>
      ${zone?.needs_review?'<p class="operator-warning">Zone requires staff review in the full workbench before ready/pickup.</p>':''}
      <p class="operator-label">Unit ${e(dish.id)} · ${e(dish.line_id)}</p><div class="operator-controls">${operations}</div></div>`;
  }
  function updatesMarkup(ctx) {
    const updates=Object.values(ctx.state.service_updates || {}).filter(u=>u.recipient_id===ctx.actor.id && u.status!=='resolved');
    return `<section class="operator-section"><h2>Kitchen → your service inbox</h2><p class="operator-hint">Message acknowledgment does not mark food ready. Current physical dish state remains authoritative.</p>${updates.map(u=>{
      const order=ctx.state.orders[u.order_id],ready=unitsFor(ctx.state,u.order_id).filter(d=>d.stage==='ready').length;
      return `<article class="operator-card"><h3>${e(order?ticketLabel(order):u.order_id)}</h3><p>${e(human(u.kind))} · ${e(u.status)} · from ${e(ctx.state.actors[u.sender_id]?.name || u.sender_id)}</p><p class="operator-notes">${e(u.note)}</p>
      <p>${ready} units currently ready for pickup.${u.kind==='pickup_request'&&!ready?' Earlier pickup request has no ready units now.':''}</p>
      ${action(u.status==='unread'?'Acknowledge update':'Resolve update',u.status==='unread'?'acknowledge_service_update':'resolve_service_update',u.id)}</article>`;
    }).join('') || '<p>No open updates addressed to this staff member.</p>'}</section>`;
  }
  function kitchenUpdateMarkup(ctx,order) {
    if(['picked_up','delivered'].includes(order.status))return '';
    return `<details data-update-form="${e(order.id)}" ${updateForms.get(order.id)?.open?'open':''}><summary>Send update to ${e(ctx.state.actors[order.owner]?.name || order.owner)}</summary><div class="operator-form"><label>Update kind <select id="kind-${e(order.id)}">${['delay','needs_attention','pickup_request','availability'].map(kind=>`<option value="${kind}" ${kind===(updateForms.get(order.id)?.kind || 'delay')?'selected':''}>${e(human(kind))}</option>`).join('')}</select></label><label>Staff-authored note <textarea id="note-${e(order.id)}" maxlength="300" rows="2">${e(updateForms.get(order.id)?.note || '')}</textarea></label>${action('Send kitchen update','publish',order.id)}${action('Discard unsent note','discard-update',order.id)}</div></details>`;
  }
  function ordersMarkup(ctx) {
    let orders=ownOrders(ctx.state,ctx.actor,kitchen).filter(o=>!['draft','delivered'].includes(o.status) && (!kitchen || o.status!=='picked_up'));
    if(kitchen) orders.sort((a,b)=>{const sent=o=>Number.isFinite(Date.parse(o.submitted_at))?Date.parse(o.submitted_at):Infinity;return sent(a)-sent(b)||a.id.localeCompare(b.id);});
    const stations=[...new Set(Object.values(ctx.state.dishes).map(d=>d.station).filter(Boolean))];
    return `<div class="operator-controls"><h2>${kitchen?'Kitchen ticket lineup':'Your active tickets'}</h2>${kitchen?`<label>Station <select id="stationFilter"><option value="">All</option>${stations.map(s=>`<option ${s===station?'selected':''} value="${e(s)}">${e(s)}</option>`).join('')}</select></label>`:''}</div>
      <p class="operator-hint kitchen-lineup-hint">${kitchen?'Only submitted orders appear here. Acknowledge reserves physical zones atomically; queued cooking can start while waiting for zones. Only finished plates enter assigned zones.':'This view contains your tickets only. Pickup changes a physical unit; Delivered closes an entire picked-up ticket.'}</p>
      <div class="${kitchen?'kds-tickets':'operator-tickets'}" ${kitchen?'aria-label="Kitchen tickets, oldest sent first" tabindex="0"':''}>${orders.map(order=>{
        const allUnits=unitsFor(ctx.state,order.id), units=allUnits.filter(d=>!station || !kitchen || d.station===station);
        if (station && kitchen && !units.length) return '';
        const ready=allUnits.filter(d=>d.stage==='ready').length;
        const fullyReady=allUnits.length>0&&allUnits.every(d=>d.stage==='ready'&&ctx.state.zones[d.zone_id]?.dish_id===d.id&&!ctx.state.zones[d.zone_id].needs_review);
        if(kitchen) return `<article class="ticket ${fullyReady?'allready':''}" data-ticket="${e(order.id)}"><header class="ticket-head"><div class="ticket-head-top"><h3 class="ticket-table">Table ${e(order.table_id)}</h3>${order.submitted_at?`<span class="ticket-timer" data-submitted="${e(order.submitted_at)}"></span>`:'<span class="ticket-timer">Sent time unknown</span>'}</div>
          <div class="ticket-head-sub"><span class="ticket-mode">${e(human(order.status))} · ${allUnits.length} dishes</span><span class="ticket-ready-pill ${fullyReady?'done':''}">${ready}/${allUnits.length} ready</span></div>
          <p class="operator-label">Ticket ${e(order.id)} · ${e(ctx.state.actors[order.owner]?.name || order.owner)} · zones ${e(order.zone_status)}</p>${station?'<p class="operator-label">Station filter shows matching units; ready count covers the full ticket.</p>':''}
          ${order.status==='submitted'?action('Acknowledge ticket','acknowledge',order.id):''}</header><div class="ticket-dishes">${units.map(d=>unitMarkup(ctx,order,d)).join('') || '<p>No physical units yet.</p>'}</div><footer class="ticket-coordination">${kitchenUpdateMarkup(ctx,order)}</footer></article>`;
        return `<article class="operator-card"><h3>Table ${e(order.table_id)}</h3><p class="operator-label">Ticket ${e(order.id)} · ${e(ctx.state.actors[order.owner]?.name || order.owner)}</p><p><span class="operator-pill">${e(human(order.status))}</span> · zones ${e(order.zone_status)} · ${ready}/${allUnits.length} currently ready</p>
        ${kitchen&&order.status==='submitted'?action('Acknowledge ticket','acknowledge',order.id):''}
        ${units.map(d=>unitMarkup(ctx,order,d)).join('') || '<p>No physical units yet.</p>'}
        ${!kitchen&&order.status==='picked_up'?action('Mark entire ticket delivered','deliver_order',order.id):''}
        ${kitchen ? kitchenUpdateMarkup(ctx,order) : ''}</article>`;
      }).join('') || '<p>No active tickets in this view.</p>'}</div>${kitchen?kitchenCountsMarkup(ctx,orders):updatesMarkup(ctx)}`;
  }
  function kitchenCountsMarkup(ctx,orders) {
    const ids=new Set(orders.map(o=>o.id));
    const units=Object.values(ctx.state.dishes).filter(d=>ids.has(d.order_id)&&d.stage!=='picked_up'&&(!station||d.station===station));
    return `<aside class="allday-bar" aria-label="Current active physical units"><div class="allday-stat"><span class="allday-num">${units.length}</span><span class="allday-lbl">Active units${station?' · filtered station':''}</span></div>${[['ready','Ready'],['started','Started'],['queued','Queued']].map(([stage,label])=>`<div class="allday-stat"><span class="allday-num">${units.filter(d=>d.stage===stage).length}</span><span class="allday-lbl">${label}</span></div>`).join('')}</aside>`;
  }
  function zonesMarkup(ctx) {
    return `<h2>Physical plating zones</h2><p class="operator-hint">Actual backend zones, independent of table/seat numbering. Occupancy is not food identity or doneness. Camera status below is the adapter-reported state, not a claim that this browser has a live feed. Review unexpected/returned plates in the workbench.</p><div class="operator-zones">${Object.values(ctx.state.zones).map(zone=>{
      const dish=ctx.state.dishes[zone.dish_id],camera=ctx.state.cameras[zone.camera_id];
      return `<article class="operator-card"><h3>Zone ${e(zone.id)}</h3><p>${e(zone.occupancy)} · assignment v${zone.assignment_version}</p><p>${dish?e(dish.item_name):'No assigned unit'}</p><p class="operator-label">${e(zone.order_id || '')} ${e(zone.dish_id || '')}</p><p>Camera: ${e(camera?.status || 'unknown')} · ${e(camera?.mode || 'unknown')}</p><p class="operator-label">${e(camera?.reason || '')}</p>${zone.needs_review?'<strong class="operator-warning">Requires review</strong>':''}</article>`;
    }).join('')}</div><p><a href="index.html">Open camera/zone reconciliation and ingredient observation controls in the workbench</a></p>`;
  }
  function ingredientsMarkup(ctx) {
    const expected=ctx.state.computed?.expected_consumption || {},balances=ctx.state.computed?.balances || {};
    const names=[...new Set([...Object.keys(expected),...Object.keys(balances)])];
    return `<h2>Ingredient reference</h2><p class="operator-hint">Recipe expectations and accepted stock balances are separate. Missing values are unknown. No camera count or automatic stock deduction is inferred here.</p><table><thead><tr><th>Ingredient</th><th>Recipe expected</th><th>Accepted balance</th></tr></thead><tbody>${names.map(name=>`<tr><td>${e(name)}</td><td>${expected[name]==null?'Unknown':e(expected[name])}</td><td>${balances[name]==null?'Unknown':e(balances[name])}</td></tr>`).join('')}</tbody></table><p><a href="index.html">Review countable observations and accept stock in the workbench</a></p>`;
  }
  function summaryMarkup(ctx) {
    return `<section class="operator-section operator-card"><h2>Ask for a ${kitchen?'kitchen':'server'} summary</h2>${action(summaryPending?'Loading summary…':'Ask for summary','summary','')}<p class="operator-hint">Generated on request for this actor. Refresh explicitly as work changes. <a href="index.html">Print or explicitly speak a summary in the full workbench</a>; device audio routing depends on your browser.</p>
      ${summary?`<p>Generated ${e(summary.data.generated_at)} ${summary.signature===serviceSignature(ctx)?'':'· STALE — ask again for current actions'}</p><pre class="operator-summary">${e(summary.data.text)}</pre>`:''}</section>`;
  }
  function serviceSignature(ctx) {return JSON.stringify([ctx.actor?.id,ctx.state?.orders,ctx.state?.dishes,ctx.state?.service_updates,ctx.state?.zones]);}
  function render(ctx=client.context(),force=false) {
    if (!ctx.state) {syncLocks(ctx);return;}
    const actors=Object.values(ctx.state.actors).filter(a=>kitchen?['cook','lead'].includes(a.role):['server','lead'].includes(a.role));
    if (!$('operatorActor').options.length) $('operatorActor').innerHTML=actors.map(a=>`<option value="${e(a.id)}">${e(a.name)} · ${e(a.role)}</option>`).join('');
    if (ctx.actor && !actors.some(a=>a.id===ctx.actor.id)) {feedback('This session cannot operate this screen.',true);syncLocks(ctx);return;}
    if (!ctx.session) {safeRender('<section class="operator-card"><h2>Enter a staff session</h2><p>Orders live in the shared backend. Page navigation asks you to select a staff session again; it does not clear saved orders.</p></section>');syncLocks(ctx);return;}
    const nextSignature=JSON.stringify([ctx.actor.id,ctx.state.menu_revision,ctx.state.orders,ctx.state.dishes,ctx.state.zones,ctx.state.service_updates,ctx.state.computed?.balances,ctx.state.computed?.expected_consumption,kitchenTab,station,selectedDraft,search,category,summary,summaryPending]);
    if(force || signature!==nextSignature) {
      let html = composer?composerMarkup(ctx):kitchen?(kitchenTab==='zones'?zonesMarkup(ctx):kitchenTab==='ingredients'?ingredientsMarkup(ctx):ordersMarkup(ctx)):ordersMarkup(ctx);
      if(kitchen) html=`<div class="operator-controls">${['tickets','zones','ingredients'].map(tab=>`<button class="operator-action" data-action="tab" data-id="${tab}" aria-pressed="${tab===kitchenTab}">${human(tab)}</button>`).join('')}</div>`+html;
      if(!composer) html+=kitchen?`<details class="kitchen-summary" data-kitchen-summary="true" ${kitchenSummaryOpen?'open':''}><summary id="kitchen-summary-toggle">Service summary · on request</summary>${summaryMarkup(ctx)}</details>`:summaryMarkup(ctx);
      safeRender(html); if(!renderPending) signature=nextSignature;
    }
    syncLocks(ctx);elapsed();ticketAge();
  }
  async function run(payload,success='Change accepted by the shared backend.') {
    try {
      const data=await client.command(payload);
      feedback(success);
      if (composer && ['start_order','edit_draft','resolve_flag','confirm_send'].includes(payload.action)) {
        openEditor(data.state.orders[data.result.order_id || payload.order_id]);
        if(editor?.status!=='draft') {editor=null;localDirty=false;selectedDraft='';}
      }
      render(client.context(),true);return data;
    } catch(error) {feedback(error.rejected?`${error.message}. Refresh and review before making a new change.`:'Connection interrupted. The event may have arrived. Reconnect, then Retry the exact pending event.',true);render();return null;}
  }
  $('operatorLogin').addEventListener('submit',async event=>{event.preventDefault();try{await client.authenticate($('operatorUsername').value,$('operatorPassword').value);$('operatorPassword').value='';feedback('Demo access verified for this tab. Select a staff session below.');render(client.context(),true);}catch(error){$('operatorPassword').value='';feedback(`Demo access not verified: ${error.message}`,true);}});
  $('enterSession').addEventListener('click',async()=>{
    if(localDirty && !confirm('Discard unsaved local edits before switching staff?')) return;
    try {await client.enter($('operatorActor').value);editor=null;selectedDraft='';localDirty=false;summary=null;kitchenSummaryOpen=false;signature='';updateForms.clear();unitDetails.clear();feedback('Session entered. Saved orders remain in the shared backend.');render(client.context(),true);}catch(error){feedback(error.message,true);}
  });
  $('operatorRefresh').addEventListener('click',()=>client.refresh().catch(error=>feedback(error.message,true)));
  $('operatorRetry').addEventListener('click',async()=>{
    try {const data=await client.retry();localDirty=false;editor=null;feedback(data.replayed?'Original event confirmed; no duplicate change.':'Pending event accepted.');await client.refresh();render(client.context(),true);}catch(error){feedback(error.message,true);}
  });
  $('operatorMain').addEventListener('toggle',event=>{if(event.target.dataset.unitDetails)unitDetails.set(event.target.dataset.unitDetails,event.target.open);if(event.target.dataset.kitchenSummary)kitchenSummaryOpen=event.target.open;const id=event.target.dataset.updateForm;if(id)updateForms.set(id,{...updateForms.get(id),open:event.target.open});},true);
  $('operatorMain').addEventListener('focusout',()=>setTimeout(()=>{if(renderPending)render(client.context(),true);},0));
  $('operatorMain').addEventListener('input',event=>{
    const el=event.target;
    if(el.id.startsWith('note-')) {const id=el.id.slice(5);updateForms.set(id,{...updateForms.get(id),kind:$(`kind-${id}`).value,note:el.value});return;}
    if(el.id==='operatorSearch'){search=el.value; const start=el.selectionStart;el.blur();render(client.context(),true);$('operatorSearch')?.focus();$('operatorSearch')?.setSelectionRange(start,start);return;}
    if(!editor || !el.dataset.lineId)return;
    const line=editor.lines.find(l=>l.id===el.dataset.lineId);if(!line)return;
    if(el.dataset.field==='requests')line.requests=el.value;
    if(el.dataset.field==='quantity')line.quantity=Number(el.value);
    if(el.dataset.field==='seat')line.seat=el.value?Number(el.value):null;
    if(el.dataset.field==='modifier')line.modifiers=el.checked?[...new Set([...line.modifiers,el.dataset.modifier])]:line.modifiers.filter(id=>id!==el.dataset.modifier);
    localDirty=true;syncLocks(client.context());$('editorSaveState').textContent='Unsaved edits. Save and review the accepted revision before confirming.';
  });
  $('operatorMain').addEventListener('change',event=>{
    const el=event.target,ctx=client.context();
    if(el.id.startsWith('kind-')) {const id=el.id.slice(5);updateForms.set(id,{...updateForms.get(id),kind:el.value,note:$(`note-${id}`).value});}
    if(el.id==='draftPicker'){if(localDirty&&!confirm('Discard unsaved local edits and load the selected draft?')){el.value=selectedDraft;return;}openEditor(ctx.state.orders[el.value]);el.blur();render(ctx,true);}
    if(el.id==='editorTable'&&editor){editor.table_id=el.value;editor.lines.forEach(l=>{if(!ctx.state.tables[el.value].seats.includes(l.seat))l.seat=null;});localDirty=true;el.blur();render(ctx,true);}
    if(el.id==='operatorCategory'){category=el.value;el.blur();render(ctx,true);}
    if(el.id==='stationFilter'){station=el.value;el.blur();render(ctx,true);}
  });
  $('operatorMain').addEventListener('click',async event=>{
    const button=event.target.closest('button[data-action]');if(!button || button.disabled)return;
    const ctx=client.context(),name=button.dataset.action,id=button.dataset.id;
    if(!canOperate(ctx))return;
    if(name==='tab'){kitchenTab=id;render(ctx,true);return;}
    if(name==='summary') {
      kitchenSummaryOpen=true;
      summaryPending=true;render(ctx,true);const before=serviceSignature(ctx);
      try {const data=await client.summary(kitchen?'kitchen':'server');if(data)summary={data,signature:before};else feedback('Session changed while summary loaded. Ask again.',true);}catch(error){feedback(`Summary unavailable: ${error.message}`,true);}finally{summaryPending=false;render(client.context(),true);}return;
    }
    if(name==='start'){if(localDirty&&!confirm('Discard unsaved edits and start another draft?'))return;await run({action:'start_order',table_id:$('newTable').value},'Draft created. Review and save changes before sending.');return;}
    if(name==='add'&&editor){if(editor.lines.length>=24){feedback('Maximum 24 lines. Increase quantity on an existing line where appropriate.',true);return;}editor.lines.push({id:uid(),menu_id:id,quantity:1,modifiers:[],seat:null,requests:''});localDirty=true;render(ctx,true);return;}
    if(name==='remove'&&editor){editor.lines=editor.lines.filter(l=>l.id!==id);localDirty=true;render(ctx,true);return;}
    if(name==='reload'){if(localDirty&&!confirm('Discard local edits and reload the saved draft?'))return;openEditor(ctx.state.orders[id]);render(ctx,true);return;}
    if(name==='save'&&editor){await run({action:'edit_draft',order_id:editor.id,revision:editor.revision,table_id:editor.table_id,lines:editor.lines},'Draft saved. Review the saved revision, then Confirm and send.');return;}
    if(name==='confirm'&&editor&&!localDirty&&!editor.flags.length){await run({action:'confirm_send',order_id:editor.id,revision:editor.revision,human_confirmed:true},'Order submitted. Kitchen acknowledgment is a separate next step.');return;}
    if(name==='flag'&&editor){if(localDirty){feedback('Save your local edits before resolving this flag.',true);return;}const flag=editor.flags.find(f=>f.id===id);await run({action:'resolve_flag',order_id:editor.id,revision:editor.revision,flag_id:id,resolution:button.dataset.resolution,...(flag?.code==='dietary_unattached'?{line_id:$(`attach-${id}`)?.value || null}:{})});return;}
    if(name==='discard-update'){updateForms.delete(id);render(ctx,true);return;}
    if(name==='publish'){const data=await run({action:'publish_service_update',order_id:id,kind:$(`kind-${id}`).value,note:$(`note-${id}`).value},'Kitchen update sent to this ticket’s owning server.');if(data){updateForms.delete(id);render(client.context(),true);}return;}
    if(['acknowledge_service_update','resolve_service_update'].includes(name)){const update=ctx.state.service_updates[id];if(update)await run({action:name,update_id:id,revision:update.revision});return;}
    if(['acknowledge','retry_zones','deliver_order'].includes(name)){await run({action:name,order_id:id});return;}
    if(['start_dish','ready_dish','pickup_dish'].includes(name)){await run({action:name,dish_id:id,...(name==='start_dish'?{}:{fallback_reason:name==='ready_dish'?'Staff verified a finished plate in its assigned physical zone':'Staff verified pickup of this exact physical unit'})});}
  });
  window.addEventListener('beforeunload',event=>{if(localDirty||client.context().uncertain){event.preventDefault();event.returnValue='';}});
  client.subscribe(ctx=>render(ctx));
  client.refresh().catch(error=>feedback(`Cannot load shared backend: ${error.message}`,true));
  setInterval(()=>{if(!document.hidden&&!client.context().busy)client.refresh().catch(()=>feedback('Backend unavailable · UNSYNCED. No offline action is completed.',true));},3000);
  setInterval(()=>{elapsed();ticketAge();},1000);
})();
