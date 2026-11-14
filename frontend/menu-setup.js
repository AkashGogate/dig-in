/* Menu/Core setup surface. Canonical validation, encoding and activation stay on
 * the backend. No menu, uploaded file or review state goes into browser storage.
 */
"use strict";
window.createMenuSetup = function ({request, dispatch, getContext, esc}) {
  const el = id => document.getElementById(id);
  let candidate = null, preparing = false, reading = false, reviewed = false;
  let activated = false, blocked = false, generation = 0, lastSession = null;
  let activeSignature = "";
  const documentEditor = window.createMenuDocumentEditor?.({esc, changed: () => invalidate("Extracted dishes changed. Review corrections, then prepare & encode.")});

  function message(text, kind = "info") {
    el("menu-setup-status").textContent = text;
    el("menu-setup-status").classList.toggle("error", kind === "error");
  }
  function invalidate(text = "Menu input changed. Prepare it again before activation.") {
    generation++;
    candidate = null; reviewed = false; activated = false; blocked = false;
    el("menu-reviewed").checked = false;
    renderPreview(); message(text); sync();
  }
  function sync() {
    const context = getContext();
    if (lastSession !== context.session) {
      lastSession = context.session;
      invalidateForSession();
    }
    const isLead = Boolean(context.session && context.actor?.role === "lead");
    const locked = preparing || reading || context.busy || Boolean(context.uncertain);
    const stale = candidate && candidate.expected_menu_revision !== context.state?.menu_revision;
    el("menu-permission").hidden = isLead;
    el("menu-input-fields").disabled = !isLead || locked;
    el("menu-prepare").disabled = !isLead || locked || !context.online;
    el("menu-prepare").textContent = preparing ? "Encoding menu…" : reading ? "Reading file…" : "Prepare & encode menu";
    el("menu-reviewed").disabled = !isLead || locked || !candidate || stale || activated || blocked;
    el("menu-activate").disabled = !isLead || locked || !context.online || !candidate || !reviewed || stale || activated || blocked;
    el("menu-discard").disabled = locked;
    el("menu-input-panel").setAttribute("aria-busy", String(preparing || reading));
    el("menu-review-confirmation").hidden = !candidate || activated;
    el("menu-preview-state").textContent = activated ? "Active for new orders" : "Encoded · awaiting review";
    let gate = "Review the full menu, then check the confirmation below.";
    if (!isLead) gate = "A demo lead session is required to prepare or activate menus.";
    else if (context.uncertain) gate = "A change has an uncertain result. Use Retry last event above before continuing.";
    else if (!context.online) gate = "Backend unavailable. Reconnect before preparing or activating a menu.";
    else if (stale && !activated) gate = "The active menu changed after this preview was prepared. Prepare & encode again, then review the new preview.";
    else if (blocked) gate = "Activation was rejected. Correct the input if needed, then prepare and review again.";
    else if (activated) gate = "New orders use this menu. Existing drafts and tickets keep their original menu.";
    el("menu-activation-gate").textContent = gate;
    el("menu-activation-gate").classList.toggle("error", Boolean((stale && !activated) || blocked));
    if (context.state) {
      const signature = context.state.menu_revision;
      if (activeSignature !== signature) {
        activeSignature = signature;
        el("menu-current-name").textContent = context.state.menu.name;
        el("menu-current-count").textContent = `${context.state.menu.items.length} items · shared by Server and Kitchen`;
      }
    }
  }
  function invalidateForSession() {
    generation++;
    candidate = null; reviewed = false; activated = false; blocked = false;
    documentEditor?.clear();
    el("menu-reviewed").checked = false;
    renderPreview();
    message("Choose a file or paste your menu. Preparing a preview does not change the active menu.");
  }
  function renderPreview() {
    el("menu-preview").hidden = !candidate;
    el("menu-preview-empty").hidden = Boolean(candidate);
    if (!candidate) { el("menu-preview-items").innerHTML = ""; return; }
    const {menu, index, warnings, import_status: status} = candidate;
    const itemNames = Object.fromEntries(menu.items.map(item => [item.id, item.name]));
    el("menu-preview-name").textContent = menu.name;
    el("menu-encoding-summary").textContent = `${index.item_count} items encoded · ${index.semantic ? "semantic vectors" : "local lexical vectors"}. Matching suggestions still require review.`;
    const missing = status.missing_kitchen_fields || {};
    el("menu-review-summary").textContent = `${menu.items.length} items to review · ${Object.keys(missing).length} with unknown kitchen details · ${warnings.length} matching ${warnings.length === 1 ? "warning" : "warnings"}`;
    el("menu-matching-warnings").hidden = !warnings.length;
    el("menu-matching-warnings").innerHTML = warnings.map(warning => `<p><strong>Ambiguous alias: ${esc(warning.alias)}</strong><br>${warning.candidates.map(id => esc(itemNames[id] || id)).join(", ")}. Voice will ask for review.</p>`).join("");
    const fieldNames = {station:"station", call_out_name:"kitchen call-out", typical_minutes:"typical time", recipe:"recipe", ingredient_zone_mapping:"ingredient zone mapping"};
    const price = item => item.price_cents == null ? "Price unknown" : new Intl.NumberFormat("en-US", {style:"currency",currency:"USD"}).format(item.price_cents / 100);
    el("menu-preview-items").innerHTML = menu.items.map((item, n) => `<li class="menu-review-item"><div class="menu-item-heading"><h3><span class="menu-item-number">${n + 1}.</span> ${esc(item.name)}</h3><span>${esc(price(item))}</span></div>${item.category ? `<p class="eyebrow">${esc(item.category)}</p>` : ""}${item.description ? `<p>${esc(item.description)}</p>` : ""}<p><strong>Aliases:</strong> ${esc(item.aliases.join(", ") || "None configured")}</p><p><strong>Modifiers:</strong> ${item.modifiers.length ? item.modifiers.map(modifier => `${esc(modifier.name)}${modifier.aliases.length ? ` (${esc(modifier.aliases.join(", "))})` : ""}`).join("; ") : "None configured"}</p>${missing[item.id]?.length ? `<p class="note menu-unknown"><strong>Still unknown:</strong> ${esc(missing[item.id].map(field => fieldNames[field] || field).join(", "))}.</p>` : ""}<details><summary>Kitchen & recipe details</summary><dl class="menu-kitchen-details"><dt>Station</dt><dd>${esc(item.station || "Unknown")}</dd><dt>Kitchen call-out</dt><dd>${esc(item.call_out_name || "Unknown")}</dd><dt>Typical time</dt><dd>${item.typical_minutes == null ? "Unknown" : `${esc(item.typical_minutes)} min`}</dd><dt>Recipe</dt><dd>${item.recipe == null ? "Unknown" : item.recipe.length ? item.recipe.map(row => `${esc(row.qty)} × ${esc(row.ingredient)} (zone: ${esc(row.zone_id || menu.ingredient_zones[row.ingredient] || "unknown")})`).join("; ") : "No ingredients configured"}</dd></dl></details></li>`).join("");
  }
  async function readFile() {
    const file = el("menu-upload").files?.[0];
    if (!file) return;
    invalidate("Reading menu file…");
    el("menu-content").value = "";
    el("menu-source-name").textContent = `Selected ${file.name}.`;
    documentEditor?.clear();
    const documentType = {pdf:"application/pdf",png:"image/png",jpg:"image/jpeg",jpeg:"image/jpeg"}[file.name.split(".").pop().toLowerCase()];
    if (documentType) {
      if (file.size > 8 * 1024 * 1024) {message("PDF/photo uploads must be at most 8 MiB.", "error");return;}
      const version = generation, token = getContext().session;
      reading = true; sync();message("Extracting dishes locally. This may take a minute…");
      try {
        const result = await request("/api/v2/menu/extract", {method:"POST",timeoutMs:180000,headers:{"Content-Type":documentType,"X-Demo-Session":token},body:await file.arrayBuffer()});
        if (version !== generation || token !== getContext().session) return;
        documentEditor.load(result);
        if (!el("menu-name").value.trim()) el("menu-name").value=file.name.replace(/\.[^.]+$/, "");
        message("Dishes extracted. Compare with the original, correct/add/remove dishes below, then Prepare & encode menu.");
      } catch(error) {if(version===generation) message(error.detail || "Extraction failed. Try a clearer file or paste the menu text.", "error");}
      finally {reading=false;sync();}
      return;
    }
    const format = {json:"application/json", csv:"text/csv", txt:"text/plain"}[file.name.split(".").pop().toLowerCase()];
    if (!format) { message("Choose JSON, CSV, TXT, PDF, PNG or JPEG.", "error"); return; }
    if (file.size > 400_000) { message("This file is too large. Use a menu with at most 100,000 characters.", "error"); return; }
    const version = generation;
    let loaded = false;
    reading = true; sync();
    try {
      const text = (await file.text()).replace(/^\uFEFF/, "");
      if (version !== generation) return;
      if (text.length > 100_000 || !text.trim() || text.includes("\uFFFD")) throw new Error("Use a nonempty UTF-8 text file with at most 100,000 characters.");
      el("menu-content").value = text;
      el("menu-format").value = format;
      if (!el("menu-name").value.trim()) el("menu-name").value = file.name.replace(/\.[^.]+$/, "");
      loaded = true;
      el("menu-source-name").textContent = `Loaded ${file.name}. Edits below need a fresh preview.`;
      message("File loaded. Prepare & encode the menu to see the review preview.");
    } catch (error) {
      if (version === generation) message(error.message || "Could not read the file. Choose it again or paste its content.", "error");
    } finally { reading = false; sync(); }
    if (loaded && version === generation) await prepare();
  }
  async function prepare(event) {
    event?.preventDefault();
    const context = getContext();
    if (preparing || reading || context.busy || context.uncertain || context.actor?.role !== "lead" || !context.session || !context.online) return;
    const content = el("menu-content").value;
    if (!content.trim() || content.length > 100_000) {
      message("Upload or paste a menu with 1–100,000 characters before preparing.", "error");
      el("menu-content").setAttribute("aria-invalid", "true"); el("menu-content").focus(); return;
    }
    el("menu-content").removeAttribute("aria-invalid");
    invalidate("Validating the menu and encoding its items…");
    const version = generation, token = context.session;
    preparing = true; sync();
    try {
      const data = await request("/api/v2/menu/prepare", {method:"POST", timeoutMs:90000, headers:{"Content-Type":"application/json", "X-Demo-Session":token}, body:JSON.stringify({content, media_type:el("menu-format").value, name:el("menu-name").value.trim() || "Imported menu"})});
      if (version !== generation || token !== getContext().session) return;
      candidate = data; renderPreview();
      message("Encoding complete. Review every item and any unknown details before activation.");
      el("menu-preview-heading").focus();
    } catch (error) {
      if (version !== generation) return;
      message(error.rejected ? `${error.detail || error.message}. Correct the menu content or format, then prepare again.` : "Encoding could not be confirmed. Your input is preserved. Reconnect and prepare again; the active menu was not changed by preparation.", "error");
    } finally { preparing = false; sync(); }
  }
  async function activate() {
    const context = getContext();
    if (!candidate || !reviewed || activated || blocked || preparing || reading || context.busy || context.uncertain || !context.online || context.actor?.role !== "lead" || !context.session || candidate.expected_menu_revision !== context.state?.menu_revision) return;
    message("Activating the reviewed menu…");
    await dispatch({action:"activate_menu", candidate_id:candidate.candidate_id, expected_menu_revision:candidate.expected_menu_revision, human_confirmed:true});
    if (getContext().uncertain) message("Activation result is unknown. Use Retry last event above to check the exact same change.", "error");
    sync();
  }
  function accepted(data, payload) {
    if (payload.action !== "activate_menu" || payload.candidate_id !== candidate?.candidate_id) return;
    activated = true; reviewed = false;
    el("menu-reviewed").checked = false;
    message(`${candidate.menu.name} is now active for new orders. Existing drafts and tickets keep their original menu.`, "success");
    sync();
    el("menu-setup-status").focus();
  }
  function rejected(payload, error) {
    if (payload.action !== "activate_menu" || payload.candidate_id !== candidate?.candidate_id) return;
    blocked = true; reviewed = false; el("menu-reviewed").checked = false;
    message(`${error.detail || error.message}. Prepare the menu again before another activation attempt.`, "error"); sync();
  }
  for (const id of ["menu-name", "menu-format", "menu-content"]) el(id).addEventListener("input", () => {
    el("menu-content").removeAttribute("aria-invalid"); invalidate();
  });
  el("menu-upload").addEventListener("change", readFile);
  el("menu-import-form").addEventListener("submit", prepare);
  el("menu-reviewed").addEventListener("change", () => { reviewed = el("menu-reviewed").checked; sync(); });
  el("menu-activate").addEventListener("click", activate);
  el("menu-discard").addEventListener("click", () => { invalidate("Preview discarded. Your input is preserved; prepare it again whenever you are ready."); el("menu-content").focus(); });
  renderPreview(); sync();
  return {sync, accepted, rejected};
};
