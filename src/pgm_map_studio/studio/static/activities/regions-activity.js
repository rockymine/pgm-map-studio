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
import { normalizeIslands } from "../shared/canvas-helpers.js";
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

  constructor() {
    this.#el         = document.getElementById("rg-workspace");
    this.#coordsEl = document.getElementById("rg-cursor-coords");
    this.#zoomEl   = document.getElementById("rg-zoom-level");

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

    this.#canvas.connectBlocksToggle(
      document.getElementById("rg-toggle-blocks"),
      document.getElementById("rg-blocks-label"),
      () => api.fetchTopSurface(this.#mapName),
    );

    document.addEventListener("keydown", (e) => {
      if (this.#el.hidden) return;
      if (e.target.matches("input,select,textarea")) return;
      if (e.key === "m" || e.key === "M") this.#toolMgr.setTool("move");
      if (e.key === "s" || e.key === "S") this.#toolMgr.setTool("select");
      if (e.key === "Escape")             this.#toolMgr.setTool("move");
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
          islands: normalizeIslands(islands ?? []),
        },
        treeGroups,
      );

      for (const group of treeGroups) {
        _registerNodes(group.regions, this.#registry);
      }

      this.#panel.build(treeGroups);
      this.#canvas.autoLoadBlocks();
    } catch (err) {
      console.error("RegionsActivity load failed:", err);
    }
  }
}

function _registerNodes(nodes, registry) {
  for (const node of nodes) {
    if (node.id) registry.register(node, null);
    if (node.children?.length) _registerNodes(node.children, registry);
  }
}
