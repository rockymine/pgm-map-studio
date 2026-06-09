/**
 * TeamsActivity — workspace for the Teams activity.
 * Shows spawn regions on the map canvas and wires up the TeamsPanel.
 */

import { EditorCanvas }   from "../canvas/editor-canvas.js";
import { TeamsPanel }     from "../panels/teams-panel.js";
import { RegionRegistry } from "../region/region-registry.js";
import {
  applyRegionPatchToNode,
  findRegionNode,
  getRegionGroups,
  registerRegionGroups,
} from "../region/region-tree.js";
import { ToolManager }    from "../shared/tool-manager.js";
import * as api           from "../api.js";
import { showToast }            from "../shared/ui-helpers.js";
import { normalizeIslands,
         drawResultToPayload,
         makeBoundsHandlers }  from "../shared/canvas-helpers.js";

export class TeamsActivity {
  #el         = null;
  #canvas     = null;
  #panel      = null;
  #registry   = null;
  #toolMgr    = null;
  #mapName    = null;
  #coordsEl   = null;
  #zoomEl     = null;
  #spawnNodes = [];

  constructor({ onStatusChange } = {}) {
    this.#el       = document.getElementById("pt-workspace");
    this.#coordsEl = document.getElementById("pt-cursor-coords");
    this.#zoomEl   = document.getElementById("pt-zoom-level");

    this.#registry = new RegionRegistry({
      onSelectionChange: (node, selectedIds) => {
        this.#canvas.setSelectedRegions(selectedIds);
        if (node) {
          this.#canvas.showAnchors(node);
          this.#panel.onRegionSelect(node);
        } else {
          this.#canvas.clearAnchors();
          this.#panel.onRegionDeselect();
        }
      },
    });

    this.#panel = new TeamsPanel({
      onStatusChange,
      onSpawnRowClick:  (regionId) => this.#registry.select(regionId),
      onDeselectRegion: ()         => this.#registry.deselect(),
      onDeleteRegion:   async () => {
        this.#registry.deselect();
        await this.#reloadRegions();
      },
      onRegionPatched:  (regionId, payload, result) => this.#handleRegionPatch(regionId, payload, result),
      validateRegionId: (newId, currentId) =>
        this.#registry.has(newId) && newId !== currentId ? `Region ID "${newId}" is already in use.` : "",
    });

    this.#initCanvas();
  }

  activate({ mapName } = {}) {
    this.#el.hidden = false;
    if (mapName && mapName !== this.#mapName) {
      this.#mapName = mapName;
      this.#panel.load(mapName);
      this.#loadMap(mapName);
    }
  }

  deactivate() { this.#el.hidden = true; }

  resize() { this.#canvas.resize(); }

  // ── canvas ────────────────────────────────────────────────────────────────

  #initCanvas() {
    const svgEl  = document.getElementById("pt-map-svg");
    const wrapEl = document.getElementById("pt-svg-area");

    this.#canvas = new EditorCanvas(svgEl, wrapEl, {
      onCoords: (x, z) => {
        this.#coordsEl.textContent = x !== null ? `X ${x}  Z ${z}` : "";
      },
      onZoom: (scale) => {
        this.#zoomEl.textContent = `${Math.round(scale * 100)}%`;
      },
      onCanvasClick: (node) => {
        if (node) this.#registry.select(node.id);
        else      this.#registry.deselect();
      },
      onRegionDraw: (drawResult) => this.#onRegionDraw(drawResult),
      ...makeBoundsHandlers(
        () => this.#mapName,
        (id) => this.#reloadRegions(id),
        (node, nb) => this.#canvas.refreshRegionBounds(node.id, nb),
      ),
    });

    // Wire draw tool buttons via ToolManager
    this.#toolMgr = new ToolManager(this.#canvas, {
      move:      document.getElementById("pt-tool-move"),
      select:    document.getElementById("pt-tool-select"),
      rectangle: document.getElementById("pt-tool-rectangle"),
      cuboid:    document.getElementById("pt-tool-cuboid"),
      cylinder: document.getElementById("pt-tool-cylinder"),
      circle:    document.getElementById("pt-tool-circle"),
      block:     document.getElementById("pt-tool-block"),
      point:     document.getElementById("pt-tool-point"),
    });

    for (const [id, tool] of [
      ["pt-tool-move",      "move"],
      ["pt-tool-select",    "select"],
      ["pt-tool-rectangle", "rectangle"],
      ["pt-tool-cuboid",    "cuboid"],
      ["pt-tool-cylinder",  "cylinder"],
      ["pt-tool-circle",    "circle"],
      ["pt-tool-block",     "block"],
      ["pt-tool-point",     "point"],
    ]) {
      document.getElementById(id)?.addEventListener("click", () => this.#toolMgr.setTool(tool));
    }

    this.#toolMgr.setTool("move");

    this.#canvas.connectBlocksToggle(
      document.getElementById("pt-toggle-blocks"),
      document.getElementById("pt-blocks-label"),
      () => api.fetchTopSurface(this.#mapName),
    );

    document.addEventListener("keydown", (e) => {
      if (this.#el.hidden) return;
      if (e.target.matches("input,select,textarea")) return;
      const map = { m: "move", M: "move", s: "select", S: "select",
                    r: "rectangle", R: "rectangle", c: "cuboid", C: "cuboid",
                    y: "cylinder", Y: "cylinder", o: "circle", O: "circle",
                    b: "block", B: "block", p: "point", P: "point" };
      if (map[e.key]) this.#toolMgr.setTool(map[e.key]);
      if (e.key === "Escape") this.#toolMgr.setTool("move");
    });
  }

  async #loadMap(mapName) {
    try {
      const [treeData, islands] = await Promise.all([
        api.fetchRegionsTree(mapName),
        api.fetchIslands(mapName).catch(() => null),
      ]);
      const groups = getRegionGroups(treeData, "spawn");
      this.#canvas.render({
        bounding_box: treeData.bounding_box,
        islands: normalizeIslands(islands || []),
      }, groups);
      this.#registry.clear();
      this.#spawnNodes = groups.flatMap(g => g.regions);
      registerRegionGroups(this.#registry, groups);
      this.#panel.setSpawnRegions(this.#spawnNodes);
      this.#canvas.autoLoadBlocks();
    } catch (err) {
      console.error("TeamsActivity: failed to load map:", err);
    }
  }

  async #reloadRegions(selectId = null) {
    if (!selectId) this.#registry.deselect();
    const treeData = await api.fetchRegionsTree(this.#mapName);
    const groups = getRegionGroups(treeData, "spawn");
    this.#canvas.refreshRegions(groups);
    this.#registry.clear();
    this.#spawnNodes = groups.flatMap(g => g.regions);
    registerRegionGroups(this.#registry, groups);
    this.#panel.setSpawnRegions(this.#spawnNodes);
    if (selectId) {
      const node = findRegionNode(groups, selectId);
      if (node) this.#registry.select(selectId);
    }
  }

  async #onRegionDraw(drawResult) {
    if (!this.#mapName) return;
    if (!["rectangle", "cuboid", "cylinder", "circle", "block", "point"].includes(drawResult.type)) return;

    const payload = drawResultToPayload(drawResult, "spawn");

    try {
      const result = await api.createRegion(this.#mapName, payload);
      await this.#reloadRegions();
      this.#toolMgr.setTool("select");
      if (result?.id) {
        const node = this.#spawnNodes.find(n => n.id === result.id);
        if (node) this.#registry.select(result.id);
      }
    } catch (err) {
      showToast(`Failed to create spawn region: ${err.message}`, "error");
    }
  }

  #handleRegionPatch(regionId, payload, result) {
    if (payload.id) {
      this.#reloadRegions(payload.id);
      return;
    }

    const node = this.#registry.getNode(regionId);
    if (!node) return;
    applyRegionPatchToNode(node, payload, result);
    if (result?.bounds) this.#canvas.refreshRegionBounds(regionId, result.bounds);
    this.#canvas.showAnchors(node);
    this.#panel.onRegionSelect(node);
  }

}
