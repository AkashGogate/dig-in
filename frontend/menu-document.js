/* Editable extraction evidence, separate from canonical encoding/activation.
 * No uploaded binary, OCR text or provisional dish is saved in localStorage.
 */
"use strict";
window.createMenuDocumentEditor = function ({esc, changed}) {
  const el = id => document.getElementById(id);
  let items = [], writing = false;
  function publish() {
    writing = true;
    el("menu-content").value = JSON.stringify({items}, null, 2);
    el("menu-format").value = "application/json";
    changed(); writing = false;
  }
  function render() {
    el("menu-extracted-items").innerHTML = items.map((item,n) => `<fieldset class="menu-review-item"><legend>Extracted dish ${n+1}</legend><label>Name<input data-extract-field="name" data-row="${n}" value="${esc(item.name)}" maxlength="200"></label><label>Description<textarea data-extract-field="description" data-row="${n}" maxlength="1000" rows="2">${esc(item.description || "")}</textarea></label><label>Price in cents (leave blank if unknown)<input type="number" min="0" step="1" data-extract-field="price_cents" data-row="${n}" value="${item.price_cents ?? ""}"></label><button type="button" data-remove-extracted="${n}">Remove dish ${n+1}</button></fieldset>`).join("");
  }
  el("menu-extracted-items").addEventListener("input", event => {
    const {extractField, row} = event.target.dataset;
    if (!extractField) return;
    if (extractField === "price_cents") {
      if (event.target.value === "") delete items[row].price_cents;
      else items[row].price_cents = Number(event.target.value);
    } else items[row][extractField] = event.target.value;
    publish();
  });
  el("menu-extracted-items").addEventListener("click", event => {
    const index = event.target.dataset.removeExtracted;
    if (index === undefined) return;
    items.splice(Number(index),1); render(); publish();
  });
  el("menu-add-extracted").addEventListener("click", () => {items.push({name:"",description:""});render();publish();});
  el("menu-content").addEventListener("input", () => {if (!writing) el("menu-extracted-editor").hidden = true;});
  return {
    load(result) {items = result.items; el("menu-ocr-source").textContent = result.source_text; el("menu-extraction-warning").textContent = result.warnings.join(" "); el("menu-extracted-editor").hidden = false; render();publish();},
    clear() {items=[];el("menu-extracted-editor").hidden=true;el("menu-ocr-source").textContent="";el("menu-extracted-items").innerHTML="";}
  };
};
