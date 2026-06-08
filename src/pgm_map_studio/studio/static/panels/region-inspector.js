/**
 * RegionInspector — read-only right panel for the Regions activity.
 * Follows the same header + field/coord-field pattern as TeamsPanel.
 */

import { typeIcon } from "../region/region-types.js";

function fmt(v) {
  if (v == null) return "—";
  return (typeof v === "number" && !Number.isInteger(v)) ? v.toFixed(2) : String(v);
}

export class RegionInspector {
  #el;
  #onSelect;
  #onDelete;

  constructor(el, { onSelect, onDelete } = {}) {
    this.#el = el;
    this.#onSelect = onSelect ?? null;
    this.#onDelete = onDelete ?? null;
    this.clear();
  }

  show(node) {
    while (this.#el.firstChild) this.#el.removeChild(this.#el.firstChild);

    // ── detail-header: icon + id + type badge ─────────────────────────────
    const header = document.createElement("div");
    header.className = "detail-header";

    const iconSpan = document.createElement("span");
    iconSpan.className = "geo-type-icon";
    iconSpan.style.color = "var(--text-muted)";
    iconSpan.innerHTML = typeIcon(node.type, 14);

    const labelSpan = document.createElement("span");
    labelSpan.className = "detail-label";
    labelSpan.style.fontFamily = "ui-monospace, monospace";
    labelSpan.textContent = node.id ?? node.type;

    const typeBadge = document.createElement("span");
    typeBadge.className = "badge badge--neutral";
    typeBadge.textContent = node.type.charAt(0).toUpperCase() + node.type.slice(1);

    header.append(iconSpan, labelSpan, typeBadge);
    this.#el.appendChild(header);

    // ── coord fields (type-specific, readonly) ────────────────────────────
    const coords = node.coords ?? {};
    const type   = node.type;

    if (type === "cuboid" || type === "rectangle") {
      this.#el.appendChild(_coordField("Min", _coordRow(type === "cuboid"
        ? [["X", coords.min_x], ["Y", coords.min_y], ["Z", coords.min_z]]
        : [["X", coords.min_x], ["Z", coords.min_z]])));
      this.#el.appendChild(_coordField("Max", _coordRow(type === "cuboid"
        ? [["X", coords.max_x], ["Y", coords.max_y], ["Z", coords.max_z]]
        : [["X", coords.max_x], ["Z", coords.max_z]])));

    } else if (type === "cylinder") {
      this.#el.appendChild(_coordField("Base", _coordRow([
        ["X", coords.base_x], ["Y", coords.base_y], ["Z", coords.base_z],
      ])));
      this.#el.appendChild(_coordField("Dimensions", _coordRow([
        ["R", coords.radius], ["H", coords.height],
      ])));

    } else if (type === "circle") {
      this.#el.appendChild(_coordField("Center", _coordRow([
        ["X", coords.center_x], ["Z", coords.center_z],
      ])));
      this.#el.appendChild(_coordField("Radius", _coordRow([["R", coords.radius]])));

    } else if (type === "sphere") {
      this.#el.appendChild(_coordField("Origin", _coordRow([
        ["X", coords.origin_x], ["Y", coords.origin_y], ["Z", coords.origin_z],
      ])));
      this.#el.appendChild(_coordField("Radius", _coordRow([["R", coords.radius]])));

    } else if (type === "point" || type === "block") {
      this.#el.appendChild(_coordField("Position", _coordRow([
        ["X", coords.x ?? coords.pos_x],
        ["Y", coords.y ?? coords.pos_y],
        ["Z", coords.z ?? coords.pos_z],
      ])));

    } else if (node.bounds) {
      // Composite / unknown types: show 2D bounds
      this.#el.appendChild(_coordField("Min", _coordRow([
        ["X", node.bounds.min_x], ["Z", node.bounds.min_z],
      ])));
      this.#el.appendChild(_coordField("Max", _coordRow([
        ["X", node.bounds.max_x], ["Z", node.bounds.max_z],
      ])));
    }

    // ── delete action ──────────────────────────────────────────────────────
    if (this.#onDelete && node.id) {
      const del = document.createElement("button");
      del.className = "action-btn action-btn--danger";
      del.style.width = "100%";
      del.textContent = "Delete Region";
      del.addEventListener("click", () => this.#onDelete(node));
      this.#el.appendChild(del);
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
      list.className = "list-container";
      for (const kid of allKids) {
        const row = document.createElement("div");
        row.className = "list-row list-row--compact";

        const icon = document.createElement("span");
        icon.className = "geo-type-icon";
        icon.style.color = "var(--text-muted)";
        icon.innerHTML = typeIcon(kid.type, 13);

        const id = document.createElement("span");
        id.className = "list-label list-label--mono";
        id.textContent = kid.id || `(${kid.type})`;

        const type = document.createElement("span");
        type.className = "list-tag";
        type.textContent = kid.type;

        row.append(icon, id, type);
        if (this.#onSelect && kid.id) {
          row.style.cursor = "pointer";
          row.addEventListener("click", () => this.#onSelect(kid));
        }
        list.appendChild(row);
      }
      this.#el.appendChild(list);
    }
  }

  clear() {
    while (this.#el.firstChild) this.#el.removeChild(this.#el.firstChild);
    const empty = document.createElement("div");
    empty.className = "section-desc";
    empty.style.padding = "16px 14px";
    empty.textContent = "Select a region to inspect.";
    this.#el.appendChild(empty);
  }
}

// ── helpers ────────────────────────────────────────────────────────────────

function _coordField(label, ctrlRow) {
  const field = document.createElement("div");
  field.className = "field";
  const lbl = document.createElement("label");
  lbl.className = "field-label";
  lbl.textContent = label;
  field.append(lbl, ctrlRow);
  return field;
}

function _coordRow(pairs) {
  const row = document.createElement("div");
  row.className = "ctrl-row";
  for (const [prefix, val] of pairs) {
    const cell = document.createElement("div");
    cell.className = "coord-field";
    const pre = document.createElement("span");
    pre.className = "coord-prefix";
    pre.textContent = prefix;
    const inp = document.createElement("input");
    inp.className = "coord-input";
    inp.type = "number";
    inp.readOnly = true;
    inp.tabIndex = -1;
    inp.value = fmt(val);
    cell.append(pre, inp);
    row.appendChild(cell);
  }
  return row;
}
