/**
 * RegionsActivity — read-only spatial registry audit (editor step 2.7).
 *
 * Left sidebar: geo tree of all regions grouped by category.
 * Canvas: map with island footprints; Blocks toggle for top-surface view.
 * Right inspector: type, bounds, and coords for the selected region.
 */

import { EditorCanvas }     from "../canvas/editor-canvas.js";
import { RegionsPanel }     from "../panels/regions-panel.js";
import { RegionInspector }  from "../panels/region-inspector.js";
import { RegionRegistry }   from "../region/region-registry.js";
import { ToolManager }      from "../shared/tool-manager.js";
import * as api             from "../api.js";

export class RegionsActivity {
  #el         = null;
  #canvas     = null;
  #panel      = null;
  #inspector  = null;
  #registry   = null;
  #toolMgr    = null;
  #mapName    = null;
  #coordsEl   = null;
  #zoomEl     = null;
  #blockCache = null;

  constructor() {
    this.#el         = document.getElementById("rg-workspace");
    this.#coordsEl   = document.getElementById("rg-cursor-coords");
    this.#zoomEl     = document.getElementById("rg-zoom-level");
    this.#blockCache = new Map();

    this.#registry = new RegionRegistry({
      onSelectionChange: (node, selectedIds) => {
        this.#canvas.setSelectedRegions(selectedIds);
        this.#panel.setSelected(node?.id ?? null, selectedIds);
        if (node) {
          this.#canvas.showAnchors(node);
          this.#inspector.show(node);
        } else {
          this.#canvas.clearAnchors();
          this.#inspector.clear();
        }
      },
    });

    this.#panel = new RegionsPanel(
      document.getElementById("rg-region-list"),
      { onSelect: (node) => this.#registry.select(node.id) },
    );

    this.#inspector = new RegionInspector(
      document.getElementById("rg-region-detail"),
      { onSelect: (node) => this.#registry.select(node.id) },
    );

    this.#initCanvas();
    this.#initBlocksToggle();
  }

  activate({ mapName } = {}) {
    this.#el.hidden = false;
    if (mapName && mapName !== this.#mapName) {
      this.#mapName = mapName;
      this.#loadMap(mapName);
    }
  }

  deactivate() { this.#el.hidden = true; }

  resize() { this.#canvas?.resize(); }

  // ── canvas ────────────────────────────────────────────────────────────────

  #initCanvas() {
    const svgEl  = document.getElementById("rg-map-svg");
    const wrapEl = document.getElementById("rg-svg-area");

    this.#canvas = new EditorCanvas(svgEl, wrapEl, {
      onCoords: (x, z) => {
        if (this.#coordsEl)
          this.#coordsEl.textContent = x !== null ? `X ${x}  Z ${z}` : "";
      },
      onZoom: (scale) => {
        if (this.#zoomEl)
          this.#zoomEl.textContent = `${Math.round(scale * 100)}%`;
      },
      onCanvasClick: (node) => {
        if (node) this.#registry.select(node.id);
        else      this.#registry.deselect();
      },
    });

    this.#toolMgr = new ToolManager(this.#canvas, {
      move:   document.getElementById("rg-tool-move"),
      select: document.getElementById("rg-tool-select"),
    });

    document.getElementById("rg-tool-move")
      ?.addEventListener("click", () => this.#toolMgr.setTool("move"));
    document.getElementById("rg-tool-select")
      ?.addEventListener("click", () => this.#toolMgr.setTool("select"));

    this.#toolMgr.setTool("move");

    document.addEventListener("keydown", (e) => {
      if (this.#el.hidden) return;
      if (e.target.matches("input,select,textarea")) return;
      if (e.key === "m" || e.key === "M") this.#toolMgr.setTool("move");
      if (e.key === "s" || e.key === "S") this.#toolMgr.setTool("select");
      if (e.key === "Escape")             this.#toolMgr.setTool("move");
    });
  }

  #initBlocksToggle() {
    const cb    = document.getElementById("rg-toggle-blocks");
    const label = document.getElementById("rg-blocks-label");
    cb?.addEventListener("change", async (e) => {
      if (!e.target.checked) {
        this.#canvas.setBlocksVisible(false);
        label?.classList.remove("filter-chip--active");
        return;
      }
      if (!this.#mapName) { e.target.checked = false; return; }
      try {
        if (!this.#blockCache.has(this.#mapName)) {
          const data = await api.fetchTopSurface(this.#mapName);
          this.#blockCache.set(this.#mapName, data);
        }
        this.#canvas.loadBlockLayer(this.#blockCache.get(this.#mapName));
        this.#canvas.setBlocksVisible(true);
        label?.classList.add("filter-chip--active");
      } catch {
        e.target.checked = false;
        label?.classList.remove("filter-chip--active");
      }
    });
  }

  // ── map load ──────────────────────────────────────────────────────────────

  async #loadMap(mapName) {
    this.#registry.clear();
    this.#panel.build([]);
    this.#inspector.clear();

    try {
      const [treeData, islands] = await Promise.all([
        api.fetchRegionsTree(mapName),
        api.fetchIslands(mapName).catch(() => null),
      ]);

      const treeGroups = treeData.groups;

      // render() resets the canvas and fits to the bounding box / islands
      this.#canvas.render(
        {
          bounding_box: treeData.bounding_box,
          islands: _normalizeIslands(islands ?? []),
        },
        _colorizeGroups(treeGroups),
      );

      // Register root nodes so canvas hit-test can fire onCanvasClick
      for (const group of treeGroups) {
        for (const node of group.regions) {
          if (node.id) this.#registry.register(node, null);
        }
      }

      this.#panel.build(treeGroups);

      // Load block layer by default — Regions activity always opens in block view.
      this.#loadBlockLayer(mapName);
    } catch (err) {
      console.error("RegionsActivity load failed:", err);
    }
  }

  async #loadBlockLayer(mapName) {
    try {
      if (!this.#blockCache.has(mapName)) {
        const data = await api.fetchTopSurface(mapName);
        this.#blockCache.set(mapName, data);
      }
      this.#canvas.loadBlockLayer(this.#blockCache.get(mapName));
      this.#canvas.setBlocksVisible(true);
      const cb    = document.getElementById("rg-toggle-blocks");
      const label = document.getElementById("rg-blocks-label");
      if (cb)    cb.checked = true;
      label?.classList.add("filter-chip--active");
    } catch {
      // top-surface not available — stay in island view
    }
  }
}

const REGION_COLOR = "var(--canvas-region)";

function _colorizeGroups(groups) {
  function _colorNode(node) {
    node.color = REGION_COLOR;
    (node.children ?? []).forEach(_colorNode);
    if (node.source) _colorNode(node.source);
  }
  return groups.map(g => ({ ...g, regions: g.regions.map(n => { _colorNode(n); return n; }) }));
}

function _normalizeIslands(islands) {
  return (islands ?? []).map(isl => ({
    ...isl,
    simplified_polygon: isl.simplified_polygon ?? _geojsonToSimplified(isl.polygon),
  }));
}

function _geojsonToSimplified(polygon) {
  if (!polygon?.coordinates?.length) return null;
  return { exterior: polygon.coordinates[0] || [], holes: polygon.coordinates.slice(1) };
}
