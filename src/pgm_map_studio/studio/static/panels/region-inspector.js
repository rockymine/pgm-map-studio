/**
 * RegionInspector — region detail panel used by multiple activities.
 *
 * Read-only by default. Pass `onPatch` to enable ID rename and editable
 * coordinate fields; the callback receives (regionId, payload) where payload
 * is { id } for renames or { coords } for coordinate updates.
 */

import { typeIcon }  from "../region/region-types.js";
import { showToast } from "../shared/ui-helpers.js";

function fmt(v) {
  if (v == null) return "—";
  return (typeof v === "number" && !Number.isInteger(v)) ? v.toFixed(2) : String(v);
}

export class RegionInspector {
  #el;
  #onSelect;
  #onDelete;
  #onPatch;
  #validateId;
  #validationEls = new Map();
  #abort = null;

  constructor(el, { onSelect, onDelete, onPatch, validateId } = {}) {
    this.#el      = el;
    this.#onSelect = onSelect ?? null;
    this.#onDelete = onDelete ?? null;
    this.#onPatch  = onPatch  ?? null;
    this.#validateId = validateId ?? null;
    this.clear();
  }

  show(node) {
    this.#abort?.abort();
    this.#abort = new AbortController();
    const sig = { signal: this.#abort.signal };

    while (this.#el.firstChild) this.#el.removeChild(this.#el.firstChild);

    const editable = !!this.#onPatch;

    // ── detail-header: icon + id label + type badge ───────────────────────
    const header = document.createElement("div");
    header.className = "detail-header";

    const iconSpan = document.createElement("span");
    iconSpan.className = "geo-type-icon detail-icon--muted";
    iconSpan.innerHTML = typeIcon(node.type, 14);

    const labelSpan = document.createElement("span");
    labelSpan.className = "detail-label detail-label--mono";
    labelSpan.textContent = node.id ?? node.type;

    const typeBadge = document.createElement("span");
    typeBadge.className = "badge badge--neutral";
    typeBadge.textContent = node.type.charAt(0).toUpperCase() + node.type.slice(1);

    header.append(iconSpan, labelSpan, typeBadge);
    this.#el.appendChild(header);

    // ── ID field (editable when onPatch provided, read-only otherwise) ───────
    if (node.id) {
      const idField = document.createElement("div");
      idField.className = "field";
      const idLabel = document.createElement("label");
      idLabel.className = "field-label";
      idLabel.textContent = "ID";
      const idInput = document.createElement("input");
      idInput.className = "field-input";
      idInput.type = "text";
      idInput.spellcheck = false;
      idInput.value = node.id;
      const errorEl = _fieldError();
      this.#validationEls.set("id", errorEl);
      if (editable) {
        idInput.addEventListener("input", () => this.#setFieldError("id", idInput, ""), sig);
        idInput.addEventListener("change", async () => {
          const newId = idInput.value.trim();
          if (!newId || newId === node.id) { idInput.value = node.id; return; }
          const validationMessage = this.#validateId?.(newId, node.id) ?? "";
          if (validationMessage) {
            this.#setFieldError("id", idInput, validationMessage);
            idInput.value = node.id;
            return;
          }
          try {
            await this.#onPatch(node.id, { id: newId });
            this.#setFieldError("id", idInput, "");
          } catch (err) {
            this.#setFieldError("id", idInput, err.message || "Rename failed.");
            idInput.value = node.id;
          }
        }, sig);
      } else {
        idInput.readOnly = true;
        idInput.tabIndex = -1;
      }
      idField.append(idLabel, idInput, errorEl);
      this.#el.appendChild(idField);
    }

    // ── coord fields (type-specific) ──────────────────────────────────────
    const coords = node.coords ?? {};
    const type   = node.type;
    const coordInputs = [];  // collected when editable for batch save

    if (type === "cuboid" || type === "rectangle") {
      const minPairs = type === "cuboid"
        ? [["X", coords.min_x, "min_x"], ["Y", coords.min_y, "min_y"], ["Z", coords.min_z, "min_z"]]
        : [["X", coords.min_x, "min_x"], ["Z", coords.min_z, "min_z"]];
      const maxPairs = type === "cuboid"
        ? [["X", coords.max_x, "max_x"], ["Y", coords.max_y, "max_y"], ["Z", coords.max_z, "max_z"]]
        : [["X", coords.max_x, "max_x"], ["Z", coords.max_z, "max_z"]];
      const { el: minEl, inputs: minIns } = _coordRow(minPairs, editable);
      const { el: maxEl, inputs: maxIns } = _coordRow(maxPairs, editable);
      this.#el.appendChild(_field("Min", minEl));
      this.#el.appendChild(_field("Max", maxEl));
      coordInputs.push(...minIns, ...maxIns);

    } else if (type === "cylinder") {
      const basePairs = [
        ["X", coords.base_x, "base_x"], ["Y", coords.base_y, "base_y"], ["Z", coords.base_z, "base_z"],
      ];
      const dimPairs = [
        ["R", coords.radius, "radius", 0.5], ["H", coords.height, "height", 1],
      ];
      const { el: baseEl, inputs: baseIns } = _coordRow(basePairs, editable);
      const { el: dimEl,  inputs: dimIns  } = _coordRow(dimPairs, editable);
      this.#el.appendChild(_field("Base", baseEl));
      this.#el.appendChild(_field("Dimensions", dimEl));
      coordInputs.push(...baseIns, ...dimIns);

    } else if (type === "circle") {
      const centerPairs = [
        ["X", coords.center_x, "center_x"], ["Z", coords.center_z, "center_z"],
      ];
      const { el: cEl, inputs: cIns } = _coordRow(centerPairs, editable);
      const { el: rEl, inputs: rIns } = _coordRow([["R", coords.radius, "radius", 0.5]], editable);
      this.#el.appendChild(_field("Center", cEl));
      this.#el.appendChild(_field("Radius", rEl));
      coordInputs.push(...cIns, ...rIns);

    } else if (type === "sphere") {
      const originPairs = [
        ["X", coords.origin_x, "origin_x"], ["Y", coords.origin_y, "origin_y"], ["Z", coords.origin_z, "origin_z"],
      ];
      const { el: oEl, inputs: oIns } = _coordRow(originPairs, editable);
      const { el: rEl, inputs: rIns } = _coordRow([["R", coords.radius, "radius", 0.5]], editable);
      this.#el.appendChild(_field("Origin", oEl));
      this.#el.appendChild(_field("Radius", rEl));
      coordInputs.push(...oIns, ...rIns);

    } else if (type === "point" || type === "block") {
      const posPairs = [
        ["X", coords.x ?? coords.pos_x, "x"],
        ["Y", coords.y ?? coords.pos_y, "y"],
        ["Z", coords.z ?? coords.pos_z, "z"],
      ];
      const { el: posEl, inputs: posIns } = _coordRow(posPairs, editable);
      this.#el.appendChild(_field("Position", posEl));
      coordInputs.push(...posIns);

    } else if (node.bounds) {
      const { el: minEl } = _coordRow([
        ["X", node.bounds.min_x, "min_x"], ["Z", node.bounds.min_z, "min_z"],
      ], false);
      const { el: maxEl } = _coordRow([
        ["X", node.bounds.max_x, "max_x"], ["Z", node.bounds.max_z, "max_z"],
      ], false);
      this.#el.appendChild(_field("Min", minEl));
      this.#el.appendChild(_field("Max", maxEl));
    }

    // Attach coord save listeners when editable
    if (editable && coordInputs.length) {
      const _saveCoords = async () => {
        const c = {};
        for (const inp of coordInputs) c[inp.dataset.key] = parseFloat(inp.value);
        try {
          await this.#onPatch(node.id, { coords: c });
        } catch (err) {
          showToast(`Coord update failed: ${err.message}`, "error");
        }
      };
      for (const inp of coordInputs) {
        inp.addEventListener("change", _saveCoords, sig);
      }
    }

    // ── delete action ──────────────────────────────────────────────────────
    if (this.#onDelete && node.id) {
      const footer = document.createElement("div");
      footer.className = "section-footer section-footer--separated";
      const del = document.createElement("button");
      del.className = "action-btn action-btn--danger action-btn--fill";
      del.textContent = "Delete Region";
      del.addEventListener("click", () => this.#onDelete(node), sig);
      footer.appendChild(del);
      this.#el.appendChild(footer);
    }

    // ── children list ──────────────────────────────────────────────────────
    const allKids = [...(node.children ?? []), ...(node.source ? [node.source] : [])];
    if (allKids.length > 0) {
      const hdr = document.createElement("div");
      hdr.className = "section-header section-header--ruled";
      const lbl = document.createElement("h2");
      lbl.className = "section-title";
      lbl.textContent = "Children";
      hdr.appendChild(lbl);
      this.#el.appendChild(hdr);

      const list = document.createElement("div");
      list.className = "panel-list";
      for (const kid of allKids) {
        const row = document.createElement("div");
        row.className = "list-row list-row--compact";

        const icon = document.createElement("span");
        icon.className = "geo-type-icon detail-icon--muted";
        icon.innerHTML = typeIcon(kid.type, 13);

        const idEl = document.createElement("span");
        idEl.className = "list-label list-label--mono";
        idEl.textContent = kid.id || `(${kid.type})`;

        const typeEl = document.createElement("span");
        typeEl.className = "list-tag";
        typeEl.textContent = kid.type;

        row.append(icon, idEl, typeEl);
        if (this.#onSelect && kid.id) {
          row.addEventListener("click", () => this.#onSelect(kid));
        }
        list.appendChild(row);
      }
      this.#el.appendChild(list);
    }
  }

  clear() {
    this.#abort?.abort();
    this.#abort = null;
    this.#validationEls.clear();
    while (this.#el.firstChild) this.#el.removeChild(this.#el.firstChild);
    const empty = document.createElement("div");
    empty.className = "panel-empty-msg";
    empty.textContent = "Select a region to inspect.";
    this.#el.appendChild(empty);
  }

  #setFieldError(key, inputEl, message) {
    const errorEl = this.#validationEls.get(key);
    if (!errorEl) return;
    errorEl.hidden = !message;
    errorEl.textContent = message || "";
    inputEl.classList.toggle("field-input--error", !!message);
  }
}

// ── helpers ────────────────────────────────────────────────────────────────

function _field(label, ctrlEl) {
  const field = document.createElement("div");
  field.className = "field";
  const lbl = document.createElement("label");
  lbl.className = "field-label";
  lbl.textContent = label;
  field.append(lbl, ctrlEl);
  return field;
}

/**
 * Build a ctrl-row of coord cells.
 * pairs: [prefix, value, dataKey?, step?]
 * Returns { el, inputs } — inputs is empty when not editable.
 */
function _coordRow(pairs, editable = false) {
  const row = document.createElement("div");
  row.className = "ctrl-row";
  const inputs = [];
  for (const [prefix, val, key, step = 1] of pairs) {
    const cell = document.createElement("div");
    cell.className = "coord-field";
    const pre = document.createElement("span");
    pre.className = "coord-prefix";
    pre.textContent = prefix;
    const inp = document.createElement("input");
    inp.className = "coord-input";
    inp.type = "number";
    if (editable && key) {
      inp.step = step;
      inp.dataset.key = key;
      inputs.push(inp);
    } else {
      inp.readOnly = true;
      inp.tabIndex = -1;
    }
    inp.value = fmt(val);
    cell.append(pre, inp);
    row.appendChild(cell);
  }
  return { el: row, inputs };
}

function _fieldError() {
  const el = document.createElement("div");
  el.className = "field-error";
  el.hidden = true;
  return el;
}
