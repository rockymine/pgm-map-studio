/**
 * RegionsPanel — read-only geo tree sidebar for the Regions activity.
 *
 * Renders category headers and a recursive region tree using .geo-row,
 * .cat-header, .cat-divider, .collapse-btn, .geo-type-icon, .geo-label.
 * Selection state is driven externally via setSelected().
 */

import { TYPE_ICON } from "../region/region-types.js";

function _svgIcon(iconData, size = 14) {
  if (!iconData) return null;
  const ns  = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("width",  size);
  svg.setAttribute("height", size);
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.5");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  for (const [tag, attrs] of iconData) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    svg.appendChild(el);
  }
  return svg;
}

export class RegionsPanel {
  #listEl;
  #onSelect;
  #rowMap       = new Map();   // id → rowEl
  #collapsedIds = new Set();   // ids whose children are hidden

  constructor(listEl, { onSelect } = {}) {
    this.#listEl  = listEl;
    this.#onSelect = onSelect ?? null;
  }

  /** Rebuild the tree from a fresh groups array. */
  build(groups) {
    this.#rowMap.clear();
    this.#collapsedIds.clear();
    this.#listEl.innerHTML = "";

    const hasRegions = groups.some(g => g.regions.length > 0);
    if (!hasRegions) {
      const empty = document.createElement("div");
      empty.className = "panel-empty-msg";
      empty.textContent = "No named regions found.";
      this.#listEl.appendChild(empty);
      return;
    }

    const visible = groups.filter(g => g.regions.length > 0);
    for (let i = 0; i < visible.length; i++) {
      const g = visible[i];
      const header = document.createElement("div");
      header.className = "cat-header";
      header.textContent = g.label;
      this.#listEl.appendChild(header);
      this.#appendTree(g.regions, this.#listEl, 0, null, null);
      if (i < visible.length - 1) {
        const div = document.createElement("div");
        div.className = "cat-divider";
        this.#listEl.appendChild(div);
      }
    }
  }

  /**
   * Highlight primary row (full blue) and all ancestor/descendant rows (tint).
   * Pass null to clear all selection.
   */
  setSelected(primaryId, allIds = []) {
    const all = new Set(allIds);
    for (const [id, rowEl] of this.#rowMap) {
      rowEl.classList.toggle("geo-row--selected",       id === primaryId);
      rowEl.classList.toggle("geo-row--selected-child", id !== primaryId && all.has(id));
    }
    if (primaryId) {
      this.#rowMap.get(primaryId)?.scrollIntoView({ block: "nearest" });
    }
  }

  // ── private ───────────────────────────────────────────────────────────────

  #appendTree(nodes, container, depth, parentId, parentType) {
    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const row  = this.#makeRow(node, depth, parentType, i);
      container.appendChild(row);
      if (node.id) this.#rowMap.set(node.id, row);

      const kids = node.children ?? [];
      if (kids.length > 0) {
        this.#appendTree(kids, container, depth + 1, node.id, node.type);
      }
      // transform types encode their source as a single child
      if (node.source) {
        this.#appendTree([node.source], container, depth + 1, node.id, node.type);
      }
    }
  }

  #makeRow(node, depth, parentType, childIndex) {
    const row = document.createElement("div");
    row.className = "geo-row";
    if (node.id) row.dataset.regionId = node.id;

    // indent pipes
    const indent = document.createElement("span");
    indent.className = "geo-indent";
    for (let d = 0; d < depth; d++) {
      const pipe = document.createElement("span");
      pipe.className = "indent-pipe";
      indent.appendChild(pipe);
    }

    const kids = node.children ?? [];
    const hasKids = kids.length > 0 || !!node.source;

    // collapse button (only for composite nodes with children)
    if (hasKids) {
      const btn = document.createElement("button");
      btn.className = "collapse-btn";
      btn.dataset.regionId = node.id;
      btn.appendChild(_svgIcon(lucide.ChevronDown));
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.#toggleCollapse(node.id, btn);
      });
      indent.appendChild(btn);
    }

    row.appendChild(indent);

    // type icon
    const iconSpan = document.createElement("span");
    iconSpan.className = "geo-type-icon";
    const iconData = TYPE_ICON[node.type];
    if (iconData) iconSpan.appendChild(_svgIcon(iconData));
    row.appendChild(iconSpan);

    // label
    const label = document.createElement("span");
    label.className = "geo-label" + (node.synthetic_id ? " geo-label--synthetic" : "");
    label.textContent = node.label || `(${node.type})`;
    label.title = node.label || "";
    row.appendChild(label);

    // "base" tag for first child of complement
    if (parentType === "complement" && childIndex === 0) {
      const tag = document.createElement("span");
      tag.className = "complement-base-tag";
      tag.textContent = "base";
      row.appendChild(tag);
    }

    row.addEventListener("click", () => {
      if (this.#onSelect) this.#onSelect(node);
    });

    return row;
  }

  #toggleCollapse(nodeId, btn) {
    if (!nodeId) return;
    const isCollapsed = this.#collapsedIds.has(nodeId);

    // Collect all descendant rows
    const rowEl = this.#rowMap.get(nodeId);
    if (!rowEl) return;

    // Walk DOM siblings after rowEl to find children by data-depth (depth inference)
    // Simpler: walk #listEl children, hide any .geo-row that comes after this row
    // until we hit one at the same or shallower depth.
    // We track depth by counting .indent-pipe elements in .geo-indent.
    const parentDepth = rowEl.querySelectorAll(".indent-pipe").length;
    let el = rowEl.nextElementSibling;

    while (el && el.classList.contains("geo-row")) {
      const elDepth = el.querySelectorAll(".indent-pipe").length;
      if (elDepth <= parentDepth) break;
      el.hidden = !isCollapsed;
      el = el.nextElementSibling;
    }

    if (isCollapsed) {
      this.#collapsedIds.delete(nodeId);
      btn.innerHTML = "";
      btn.appendChild(_svgIcon(lucide.ChevronDown));
    } else {
      this.#collapsedIds.add(nodeId);
      btn.innerHTML = "";
      btn.appendChild(_svgIcon(lucide.ChevronRight));
    }
  }
}
