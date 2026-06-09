/**
 * sketch-layout-panel.js — Island tree + inspector for the Layout activity.
 *
 * Renders the 2-level geo-row tree (island → shape children) and a detail
 * inspector for the selected shape. All per-item actions (toggle op, toggle
 * override, toggle mirrors, delete) are surfaced via a context menu on
 * right-click.
 *
 * The panel is pure DOM — it does not talk to the API directly. The activity
 * owns persistence.
 */

import { svgEl } from "../canvas/transform.js";
import { simplifyVW } from "../algorithms/simplify.js";

// Icon names per shape type (Lucide)
const TYPE_ICON = {
  rectangle: "rectangle-horizontal",
  circle:    "circle",
  polygon:   "pentagon",
  lasso:     "lasso",
};

export class SketchLayoutPanel {
  #shapes    = [];   // ordered array (same order as sidebar)
  #islands   = [];   // from latest computeIslands result
  #selectedId       = null;
  #selectedIslandId = null;

  // element refs
  #treeEl;
  #inspectorEl;
  #collapseState = new Map(); // island id → boolean collapsed

  // callbacks
  #onShapeDelete;
  #onShapeOpToggle;
  #onShapeOverrideToggle;
  #onIslandMirrorsToggle;
  #onIslandRename;
  #onShapeSelect;
  #onIslandSelect;
  #onSimplify;

  constructor(treeEl, inspectorEl, callbacks = {}) {
    this.#treeEl      = treeEl;
    this.#inspectorEl = inspectorEl;

    this.#onShapeDelete          = callbacks.onShapeDelete;
    this.#onShapeOpToggle        = callbacks.onShapeOpToggle;
    this.#onShapeOverrideToggle  = callbacks.onShapeOverrideToggle;
    this.#onIslandMirrorsToggle  = callbacks.onIslandMirrorsToggle;
    this.#onIslandRename         = callbacks.onIslandRename;
    this.#onShapeSelect          = callbacks.onShapeSelect;
    this.#onIslandSelect         = callbacks.onIslandSelect;
    this.#onSimplify             = callbacks.onSimplify;

    this.#wireContextMenu();
  }

  // ── Public API ────────────────────────────────────────────────────────────────

  setShapes(shapes) {
    this.#shapes = shapes ?? [];
  }

  setIslands(islands) {
    this.#islands = islands ?? [];
    this.#rebuildTree();
  }

  setSelected(id) {
    this.#selectedId = id;
    this.#highlightSelected();
    this.#rebuildInspector();
  }

  setSelectedIsland(id) {
    this.#selectedIslandId = id;
    this.#highlightSelectedIsland();
    this.#rebuildInspector();
  }

  // ── Tree rendering ────────────────────────────────────────────────────────────

  #rebuildTree() {
    if (!this.#treeEl) return;
    const prev      = this.#selectedId;
    const prevIsl   = this.#selectedIslandId;
    while (this.#treeEl.firstChild) this.#treeEl.removeChild(this.#treeEl.firstChild);

    for (const isl of this.#islands) {
      const collapsed = this.#collapseState.get(isl.id) ?? false;
      this.#treeEl.appendChild(this.#makeIslandRow(isl, collapsed));
      if (!collapsed) {
        for (const shapeId of isl.shapeIds) {
          const shape = this.#shapes.find(s => s.id === shapeId);
          if (shape) this.#treeEl.appendChild(this.#makeShapeRow(shape));
        }
      }
    }

    // Shapes not assigned to any island (shouldn't happen but defensive)
    const assignedIds = new Set(this.#islands.flatMap(i => i.shapeIds));
    for (const shape of this.#shapes) {
      if (!assignedIds.has(shape.id)) {
        this.#treeEl.appendChild(this.#makeShapeRow(shape));
      }
    }

    this.#selectedId       = prev;
    this.#selectedIslandId = prevIsl;
    this.#highlightSelected();
    this.#highlightSelectedIsland();
    if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "14", height: "14" } });
  }

  #makeIslandRow(isl, collapsed) {
    const row = document.createElement("div");
    row.className = "geo-row";
    row.dataset.islId = isl.id;

    // Collapse toggle
    const indentEl = document.createElement("span");
    indentEl.className = "geo-indent";
    const colBtn = document.createElement("button");
    colBtn.className = "collapse-btn";
    colBtn.innerHTML = `<i data-lucide="${collapsed ? "chevron-right" : "chevron-down"}"></i>`;
    colBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this.#collapseState.set(isl.id, !collapsed);
      this.#rebuildTree();
    });
    indentEl.appendChild(colBtn);
    row.appendChild(indentEl);

    // Island icon (dimmed if not participating in mirror)
    const iconEl = document.createElement("span");
    iconEl.className = "geo-type-icon";
    if (!isl.mirrors) iconEl.style.color = "var(--text-muted)";
    iconEl.innerHTML = `<i data-lucide="layers"></i>`;
    row.appendChild(iconEl);

    // Name — span by default; swaps to input on double-click
    const nameEl = document.createElement("span");
    nameEl.className = "geo-label";
    nameEl.textContent = isl.name;
    nameEl.title = "Double-click to rename";
    row.appendChild(nameEl);

    // Shape count tag
    const tag = document.createElement("span");
    tag.className = "list-tag";
    tag.textContent = `${isl.shapeIds.length} shape${isl.shapeIds.length !== 1 ? "s" : ""}`;
    row.appendChild(tag);

    row.addEventListener("click", (e) => {
      if (e.target.closest(".collapse-btn")) return;
      this.#onIslandSelect?.(isl.id);
    });

    row.addEventListener("dblclick", (e) => {
      if (e.target.closest(".collapse-btn")) return;
      e.stopPropagation();
      const input = document.createElement("input");
      input.className = "geo-label geo-label-input";
      input.value = isl.name;
      nameEl.replaceWith(input);
      input.focus();
      input.select();
      const finish = (save) => {
        const next = save ? (input.value.trim() || isl.name) : isl.name;
        nameEl.textContent = next;
        input.replaceWith(nameEl);
        if (save && next !== isl.name) this.#onIslandRename?.(isl.id, next);
      };
      input.addEventListener("blur", () => finish(true));
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter")  { ev.preventDefault(); input.blur(); }
        if (ev.key === "Escape") { finish(false); }
      });
      input.addEventListener("click", (ev) => ev.stopPropagation());
    });

    row.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.#showIslandMenu(e, isl);
    });

    return row;
  }

  #makeShapeRow(shape) {
    const row = document.createElement("div");
    row.className = "geo-row";
    row.dataset.shapeId = shape.id;

    // Indent pipe
    const indentEl = document.createElement("span");
    indentEl.className = "geo-indent";
    const pipe = document.createElement("span");
    pipe.className = "indent-pipe";
    indentEl.appendChild(pipe);
    row.appendChild(indentEl);

    // Type icon (coloured for subtract)
    const iconEl = document.createElement("span");
    iconEl.className = "geo-type-icon";
    if (shape.operation === "subtract") iconEl.style.color = "var(--canvas-sub-fill)";
    iconEl.innerHTML = `<i data-lucide="${TYPE_ICON[shape.type] ?? "square"}"></i>`;
    row.appendChild(iconEl);

    // Label
    const labelEl = document.createElement("span");
    labelEl.className = "geo-label";
    labelEl.textContent = shape.type;
    row.appendChild(labelEl);

    // Dimension tag
    const tag = document.createElement("span");
    tag.className = "list-tag";
    tag.textContent = this.#shapeDimLabel(shape);
    row.appendChild(tag);

    // Override indicator
    if (shape.override) {
      const shieldEl = document.createElement("span");
      shieldEl.className = "geo-type-icon geo-type-icon--warning geo-type-icon--flush";
      shieldEl.title = "Override";
      shieldEl.innerHTML = `<i data-lucide="shield"></i>`;
      row.appendChild(shieldEl);
    }

    row.addEventListener("click", () => this.#onShapeSelect?.(shape.id));
    row.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.#showShapeMenu(e, shape);
    });

    return row;
  }

  #shapeDimLabel(shape) {
    if (shape.type === "rectangle") {
      return `${shape.max_x - shape.min_x}×${shape.max_z - shape.min_z}`;
    }
    if (shape.type === "circle") return `r=${shape.radius}`;
    if (shape.type === "polygon" || shape.type === "lasso") {
      return `${shape.vertices?.length ?? 0} v`;
    }
    return "";
  }

  #highlightSelected() {
    if (!this.#treeEl) return;
    for (const row of this.#treeEl.querySelectorAll(".geo-row[data-shape-id]")) {
      row.classList.toggle("geo-row--selected", row.dataset.shapeId === this.#selectedId);
    }
  }

  #highlightSelectedIsland() {
    if (!this.#treeEl) return;
    for (const row of this.#treeEl.querySelectorAll(".geo-row[data-isl-id]")) {
      row.classList.toggle("geo-row--selected", row.dataset.islId === this.#selectedIslandId);
    }
  }

  // ── Inspector ─────────────────────────────────────────────────────────────────

  #rebuildInspector() {
    if (!this.#inspectorEl) return;
    while (this.#inspectorEl.firstChild) this.#inspectorEl.removeChild(this.#inspectorEl.firstChild);

    if (!this.#selectedId) {
      if (this.#selectedIslandId) {
        this.#buildIslandInspector();
      } else {
        const hint = document.createElement("p");
        hint.className = "section-desc";
        hint.textContent = "Select a shape to inspect.";
        this.#inspectorEl.appendChild(hint);
      }
      return;
    }

    const shape = this.#shapes.find(s => s.id === this.#selectedId);
    if (!shape) return;

    // Row 1: icon + label + type badge (right-aligned via flex:1 on label)
    const header = document.createElement("div");
    header.className = "detail-header";
    const iconEl = document.createElement("span");
    iconEl.className = "geo-type-icon";
    iconEl.innerHTML = `<i data-lucide="${TYPE_ICON[shape.type] ?? 'square'}"></i>`;
    const labelEl = document.createElement("span");
    labelEl.className = "detail-label";
    labelEl.textContent = `s${shape.id.split("_").pop() ?? "?"}`;
    const badges = document.createElement("span");
    badges.className = "detail-header-badges";
    const opTag = document.createElement("span");
    opTag.className = `badge ${shape.operation === "subtract" ? "badge--error" : "badge--success"}`;
    opTag.textContent = shape.operation;
    badges.appendChild(opTag);
    if (shape.override) {
      const ovTag = document.createElement("span");
      ovTag.className = "badge badge--warning";
      ovTag.textContent = "override";
      badges.appendChild(ovTag);
    }
    const typeTag = document.createElement("span");
    typeTag.className = "badge badge--neutral";
    typeTag.textContent = shape.type[0].toUpperCase() + shape.type.slice(1);
    badges.appendChild(typeTag);
    header.append(iconEl, labelEl, badges);
    this.#inspectorEl.appendChild(header);

    // Coordinate table
    if (shape.type === "rectangle") {
      this.#inspectorEl.appendChild(this.#makeRectTable(shape));
    } else if (shape.type === "circle") {
      this.#inspectorEl.appendChild(this.#makeCircleTable(shape));
    } else if (shape.type === "polygon" || shape.type === "lasso") {
      const info = document.createElement("p");
      info.className = "section-desc";
      info.textContent = `${shape.vertices?.length ?? 0} vertices`;
      this.#inspectorEl.appendChild(info);
      if (shape.type === "lasso") {
        this.#inspectorEl.appendChild(this.#makeSimplifySection(shape));
      }
    }
    const moveHint = document.createElement("p");
    moveHint.className = "section-desc";
    moveHint.textContent = "Move: Arrow keys · Shift+Arrow for 1 chunk (16 blocks)";
    this.#inspectorEl.appendChild(moveHint);

    if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "14", height: "14" } });
  }

  #buildIslandInspector() {
    const isl = this.#islands.find(i => i.id === this.#selectedIslandId);
    if (!isl) return;

    const section = document.createElement("section");
    section.className = "panel-section";

    // detail-header: layers icon + name label + shapes count badge
    const header = document.createElement("div");
    header.className = "detail-header";
    const headerIcon = document.createElement("span");
    headerIcon.className = "geo-type-icon";
    headerIcon.innerHTML = `<i data-lucide="layers"></i>`;
    const headerName = document.createElement("span");
    headerName.className = "detail-label";
    headerName.textContent = isl.name;
    const countTag = document.createElement("span");
    countTag.className = "badge badge--neutral";
    countTag.textContent = `${isl.shapeIds.length} shape${isl.shapeIds.length !== 1 ? "s" : ""}`;
    header.append(headerIcon, headerName, countTag);
    section.appendChild(header);

    // Name field
    const nameField = document.createElement("div");
    nameField.className = "field";
    const nameLabel = document.createElement("label");
    nameLabel.className = "field-label";
    nameLabel.textContent = "Name";
    const nameInput = document.createElement("input");
    nameInput.className = "field-input";
    nameInput.type = "text";
    nameInput.value = isl.name;
    nameField.append(nameLabel, nameInput);
    section.appendChild(nameField);

    const commitRename = () => {
      const next = nameInput.value.trim() || isl.name;
      if (next !== isl.name) {
        headerName.textContent = next;
        const treeSpan = this.#treeEl?.querySelector(`[data-isl-id="${isl.id}"] .geo-label`);
        if (treeSpan) treeSpan.textContent = next;
        this.#onIslandRename?.(isl.id, next);
      }
    };
    nameInput.addEventListener("blur", commitRename);
    nameInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter")  { e.preventDefault(); nameInput.blur(); }
      if (e.key === "Escape") { nameInput.value = isl.name; nameInput.blur(); }
    });

    // Shapes section header
    const shapesHeader = document.createElement("div");
    shapesHeader.className = "section-header section-header--ruled";
    const shapesTitle = document.createElement("h2");
    shapesTitle.className = "section-title";
    shapesTitle.textContent = "Shapes";
    shapesHeader.appendChild(shapesTitle);
    section.appendChild(shapesHeader);

    // Shape list
    const list = document.createElement("div");
    list.className = "panel-list";
    for (const shapeId of isl.shapeIds) {
      const shape = this.#shapes.find(s => s.id === shapeId);
      if (!shape) continue;
      const row = document.createElement("div");
      row.className = "list-row list-row--compact";

      const typeIcon = document.createElement("span");
      typeIcon.className = "geo-type-icon";
      if (shape.operation === "subtract") typeIcon.style.color = "var(--canvas-sub-fill)";
      typeIcon.innerHTML = `<i data-lucide="${TYPE_ICON[shape.type] ?? "square"}"></i>`;

      const labelEl = document.createElement("span");
      labelEl.className = "list-label";
      labelEl.textContent = shape.type;

      const dimTag = document.createElement("span");
      dimTag.className = "list-tag";
      dimTag.textContent = this.#shapeDimLabel(shape);

      row.append(typeIcon, labelEl, dimTag);
      row.addEventListener("click", () => this.#onShapeSelect?.(shape.id));
      list.appendChild(row);
    }
    section.appendChild(list);

    const hint = document.createElement("p");
    hint.className = "section-desc";
    hint.textContent = "Move: Arrow keys · Shift+Arrow for 1 chunk (16 blocks)";
    section.appendChild(hint);

    this.#inspectorEl.appendChild(section);
    if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "14", height: "14" } });
  }

  #makeRectTable(shape) {
    const table = document.createElement("table");
    table.className = "detail-table";
    const { min_x, max_x, min_z, max_z } = shape;
    table.innerHTML = `
      <thead><tr><th></th><th>Min</th><th>Max</th><th class="detail-size-head">Size</th></tr></thead>
      <tbody>
        <tr>
          <td class="detail-axis">X</td>
          <td class="detail-val"><span class="detail-size">${min_x}</span></td>
          <td class="detail-val"><span class="detail-size">${max_x}</span></td>
          <td class="detail-size">${max_x - min_x}</td>
        </tr>
        <tr>
          <td class="detail-axis">Z</td>
          <td class="detail-val"><span class="detail-size">${min_z}</span></td>
          <td class="detail-val"><span class="detail-size">${max_z}</span></td>
          <td class="detail-size">${max_z - min_z}</td>
        </tr>
      </tbody>`;
    return table;
  }

  #makeCircleTable(shape) {
    const wrap = document.createElement("div");
    wrap.className = "coord-summary";
    wrap.innerHTML = `
      <div class="ctrl-row"><span class="coord-prefix">CX</span><span>${shape.center_x}</span></div>
      <div class="ctrl-row"><span class="coord-prefix">CZ</span><span>${shape.center_z}</span></div>
      <div class="ctrl-row"><span class="coord-prefix">R</span><span>${shape.radius}</span></div>`;
    return wrap;
  }

  #makeSimplifySection(shape) {
    const sec = document.createElement("div");
    sec.className = "simplify-section simplify-section--separated";

    const countRow = document.createElement("div");
    countRow.className = "simplify-row";
    countRow.innerHTML = `<span class="simplify-label">Vertices</span><span class="simplify-value" id="sk-simplify-count">${shape.vertices?.length ?? 0}</span>`;
    sec.appendChild(countRow);

    const tolRow = document.createElement("div");
    tolRow.className = "simplify-row";
    const tolInput = document.createElement("input");
    tolInput.className = "coord-input";
    tolInput.type = "number";
    tolInput.value = "50";
    tolInput.min = "1";
    tolInput.classList.add("coord-input--compact");
    const tolUnit = document.createElement("span");
    tolUnit.className = "simplify-unit";
    tolUnit.textContent = "blocks²";
    const tolInputRow = document.createElement("div");
    tolInputRow.className = "simplify-input-row";
    tolInputRow.appendChild(tolInput);
    tolInputRow.appendChild(tolUnit);
    tolRow.innerHTML = `<span class="simplify-label">Tolerance</span>`;
    tolRow.appendChild(tolInputRow);
    sec.appendChild(tolRow);

    const btn = document.createElement("button");
    btn.className = "action-btn action-btn--full action-btn--separated";
    btn.textContent = "Generalize";
    btn.addEventListener("click", () => {
      const tol = parseFloat(tolInput.value) || 50;
      const simplified = simplifyVW(shape.vertices, tol);
      if (simplified.length >= 3) {
        this.#onSimplify?.(shape.id, simplified);
        sec.querySelector("#sk-simplify-count").textContent = simplified.length;
      }
    });
    sec.appendChild(btn);

    return sec;
  }

  // ── Context menus ─────────────────────────────────────────────────────────────

  #wireContextMenu() {
    document.addEventListener("click", () => this.#closeContextMenu());
    document.addEventListener("contextmenu", (e) => {
      if (!e.target.closest("[data-ctx-menu]")) this.#closeContextMenu();
    });
  }

  #closeContextMenu() {
    document.querySelector(".sk-ctx-menu")?.remove();
  }

  #showShapeMenu(e, shape) {
    this.#closeContextMenu();
    const menu = document.createElement("div");
    menu.className = "sk-ctx-menu ctx-menu";
    menu.dataset.ctxMenu = "1";

    const opLabel = shape.operation === "subtract" ? "Make add" : "Make subtract";
    const ovrLabel = shape.override ? "Remove override" : "Set override";

    this.#ctxItem(menu, opLabel, () => this.#onShapeOpToggle?.(shape.id));
    this.#ctxItem(menu, ovrLabel, () => this.#onShapeOverrideToggle?.(shape.id));
    this.#ctxSep(menu);
    this.#ctxItem(menu, "Delete", () => this.#onShapeDelete?.(shape.id), true);

    this.#positionMenu(menu, e);
    document.body.appendChild(menu);
    if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "14", height: "14" } });
  }

  #showIslandMenu(e, isl) {
    this.#closeContextMenu();
    const menu = document.createElement("div");
    menu.className = "sk-ctx-menu ctx-menu";
    menu.dataset.ctxMenu = "1";

    const mirLabel = isl.mirrors ? "Exclude from mirror" : "Include in mirror";
    this.#ctxItem(menu, mirLabel, () => this.#onIslandMirrorsToggle?.(isl.id));

    this.#positionMenu(menu, e);
    document.body.appendChild(menu);
    if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "14", height: "14" } });
  }

  #ctxItem(menu, label, action, danger = false) {
    const item = document.createElement("button");
    item.className = `ctx-item${danger ? " ctx-item--danger" : ""}`;
    item.textContent = label;
    item.addEventListener("click", () => { this.#closeContextMenu(); action(); });
    menu.appendChild(item);
  }

  #ctxSep(menu) {
    const sep = document.createElement("div");
    sep.className = "ctx-sep";
    menu.appendChild(sep);
  }

  #positionMenu(menu, e) {
    menu.style.cssText = `position:fixed;left:${e.clientX}px;top:${e.clientY}px;z-index:9999`;
  }
}
