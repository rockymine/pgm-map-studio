/**
 * ObjectivesActivity — workspace for the Objectives (wool) activity.
 * Renders wool room regions on the map canvas and wires up ObjectivesPanel.
 */

import { EditorCanvas }      from "../canvas/editor-canvas.js";
import { ObjectivesPanel }   from "../panels/objectives-panel.js";
import { RegionRegistry }    from "../region/region-registry.js";
import {
  applyRegionPatchToNode,
  findRegionNode,
  getRegionGroups,
  registerRegionGroups,
  WOOL_CATEGORIES,
} from "../region/region-tree.js";
import { ToolManager }       from "../shared/tool-manager.js";
import * as api              from "../api.js";
import { showToast }         from "../shared/ui-helpers.js";
import { normalizeIslands,
         drawResultToPayload,
         makeBoundsHandlers } from "../shared/canvas-helpers.js";

export class ObjectivesActivity {
  #el         = null;
  #canvas     = null;
  #panel      = null;
  #registry   = null;
  #toolMgr    = null;
  #mapName    = null;
  #coordsEl   = null;
  #zoomEl     = null;
  #woolNodes  = [];

  constructor({ onStatusChange } = {}) {
    this.#el       = document.getElementById("po-workspace");
    this.#coordsEl = document.getElementById("po-cursor-coords");
    this.#zoomEl   = document.getElementById("po-zoom-level");

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

    this.#panel = new ObjectivesPanel({
      onStatusChange,
      onRegionRowClick: (regionId) => this.#registry.select(regionId),
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
    const svgEl  = document.getElementById("po-map-svg");
    const wrapEl = document.getElementById("po-svg-area");

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

    this.#toolMgr = new ToolManager(this.#canvas, {
      move:      document.getElementById("po-tool-move"),
      select:    document.getElementById("po-tool-select"),
      rectangle: document.getElementById("po-tool-rectangle"),
      cuboid:    document.getElementById("po-tool-cuboid"),
      cylinder:  document.getElementById("po-tool-cylinder"),
      circle:    document.getElementById("po-tool-circle"),
      block:     document.getElementById("po-tool-block"),
      point:     document.getElementById("po-tool-point"),
    });

    for (const [id, tool] of [
      ["po-tool-move",      "move"],
      ["po-tool-select",    "select"],
      ["po-tool-rectangle", "rectangle"],
      ["po-tool-cuboid",    "cuboid"],
      ["po-tool-cylinder",  "cylinder"],
      ["po-tool-circle",    "circle"],
      ["po-tool-block",     "block"],
      ["po-tool-point",     "point"],
    ]) {
      document.getElementById(id)?.addEventListener("click", () => this.#toolMgr.setTool(tool));
    }

    this.#toolMgr.setTool("move");

    this.#canvas.connectBlocksToggle(
      document.getElementById("po-toggle-blocks"),
      document.getElementById("po-blocks-label"),
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
      if (!treeData.bounding_box) return;
      const groups = getRegionGroups(treeData, WOOL_CATEGORIES);
      const nodes = groups.flatMap(group => group.regions);
      this.#canvas.render({
        bounding_box: treeData.bounding_box,
        islands: normalizeIslands(islands || []),
      }, groups);
      this.#registry.clear();
      this.#woolNodes = nodes;
      registerRegionGroups(this.#registry, groups);
      this.#panel.setWoolRegions(nodes);
      this.#canvas.autoLoadBlocks();
    } catch (err) {
      console.error("ObjectivesActivity: failed to load map:", err);
    }
  }

  async #reloadRegions(selectId = null) {
    if (!selectId) this.#registry.deselect();
    const treeData = await api.fetchRegionsTree(this.#mapName);
    const groups = getRegionGroups(treeData, WOOL_CATEGORIES);
    const nodes = groups.flatMap(group => group.regions);
    this.#canvas.refreshRegions(groups);
    this.#registry.clear();
    this.#woolNodes = nodes;
    registerRegionGroups(this.#registry, groups);
    this.#panel.setWoolRegions(nodes);
    if (selectId) {
      const node = findRegionNode(groups, selectId);
      if (node) this.#registry.select(selectId);
    }
  }

  async #onRegionDraw(drawResult) {
    if (!this.#mapName) return;
    if (!["rectangle", "cuboid", "cylinder", "circle", "block", "point"].includes(drawResult.type)) return;

    const payload = drawResultToPayload(drawResult, "wool_room");

    try {
      const result = await api.createRegion(this.#mapName, payload);
      await this.#reloadRegions();
      this.#toolMgr.setTool("select");
      if (result?.id) {
        const node = this.#woolNodes.find(n => n.id === result.id);
        if (node) this.#registry.select(result.id);
      }
    } catch (err) {
      showToast(`Failed to create wool room region: ${err.message}`, "error");
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
