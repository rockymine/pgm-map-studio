/**
 * TeamsActivity — workspace for the Teams activity.
 * Shows spawn regions on the map canvas and wires up the TeamsPanel.
 */

import { EditorCanvas }   from "../canvas/editor-canvas.js";
import { TeamsPanel }     from "../panels/teams-panel.js";
import { RegionRegistry } from "../region/region-registry.js";
import { ToolManager }    from "../shared/tool-manager.js";
import * as api           from "../api.js";
import { chatColorHex }   from "../shared/game-colors.js";
import { showToast }      from "../shared/ui-helpers.js";

// Use CSS token values so they match the design system
const SPAWN_COLOR = getComputedStyle(document.documentElement).getPropertyValue("--cat-spawn").trim() || "#3b82f6";
const POINT_COLOR = getComputedStyle(document.documentElement).getPropertyValue("--accent-light").trim() || "#60a5fa";

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
      onDeleteRegion:   (regionId) => this.#deleteSpawnRegion(regionId),
      onRegionPatched:  (regionId, newId) => this.#reloadRegions(newId ?? regionId),
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
    });

    // Wire draw tool buttons via ToolManager
    this.#toolMgr = new ToolManager(this.#canvas, {
      move:     document.getElementById("pt-tool-move"),
      select:   document.getElementById("pt-tool-select"),
      cylinder: document.getElementById("pt-tool-cylinder"),
      point:    document.getElementById("pt-tool-point"),
    });

    document.getElementById("pt-tool-move")?.addEventListener("click",     () => this.#toolMgr.setTool("move"));
    document.getElementById("pt-tool-select")?.addEventListener("click",   () => this.#toolMgr.setTool("select"));
    document.getElementById("pt-tool-cylinder")?.addEventListener("click", () => this.#toolMgr.setTool("cylinder"));
    document.getElementById("pt-tool-point")?.addEventListener("click",    () => this.#toolMgr.setTool("point"));

    this.#toolMgr.setTool("move");

    document.addEventListener("keydown", (e) => {
      if (this.#el.hidden) return;
      if (e.target.matches("input,select,textarea")) return;
      if (e.key === "m" || e.key === "M") this.#toolMgr.setTool("move");
      if (e.key === "s" || e.key === "S") this.#toolMgr.setTool("select");
      if (e.key === "y" || e.key === "Y") this.#toolMgr.setTool("cylinder");
      if (e.key === "p" || e.key === "P") this.#toolMgr.setTool("point");
      if (e.key === "Escape")             this.#toolMgr.setTool("move");
    });
  }

  async #loadMap(mapName) {
    try {
      const [regionsData, islands] = await Promise.all([
        api.fetchRegions(mapName),
        api.fetchIslands(mapName).catch(() => null),
      ]);
      const groups = _buildSpawnGroups(regionsData.regions, regionsData.categories);
      this.#canvas.render({
        bounding_box: regionsData.bounding_box,
        islands: _normalizeIslands(islands || []),
      }, groups);
      this.#registry.clear();
      this.#spawnNodes = groups.flatMap(g => g.regions);
      for (const node of this.#spawnNodes) this.#registry.register(node, null);
      this.#panel.setSpawnRegions(this.#spawnNodes);
    } catch (err) {
      console.error("TeamsActivity: failed to load map:", err);
    }
  }

  async #reloadRegions(selectId = null) {
    const regionsData = await api.fetchRegions(this.#mapName);
    const groups = _buildSpawnGroups(regionsData.regions, regionsData.categories);
    this.#canvas.refreshRegions(groups);
    this.#registry.clear();
    this.#spawnNodes = groups.flatMap(g => g.regions);
    for (const node of this.#spawnNodes) this.#registry.register(node, null);
    this.#panel.setSpawnRegions(this.#spawnNodes);
    if (selectId) {
      const node = this.#spawnNodes.find(n => n.id === selectId);
      if (node) this.#registry.select(selectId);
    }
  }

  async #onRegionDraw(drawResult) {
    if (!this.#mapName) return;

    let payload = { category: "spawn" };
    if (drawResult.type === "cylinder") {
      payload = { ...payload, type: "cylinder",
        base_x: drawResult.base_x, base_z: drawResult.base_z, radius: drawResult.radius };
    } else if (drawResult.type === "point") {
      payload = { ...payload, type: "point",
        x: drawResult.min_x + 0.5, z: drawResult.min_z + 0.5 };
    } else {
      return;
    }

    this.#toolMgr.setTool("move");

    try {
      const result = await api.createRegion(this.#mapName, payload);
      await this.#reloadRegions();
      if (result?.id) {
        const node = this.#spawnNodes.find(n => n.id === result.id);
        if (node) this.#registry.select(result.id);
      }
    } catch (err) {
      showToast(`Failed to create spawn region: ${err.message}`, "error");
    }
  }

  #deleteSpawnRegion(regionId) {
    this.#canvas.removeRegion(regionId);
    this.#spawnNodes = this.#spawnNodes.filter(n => n.id !== regionId);
    this.#registry.clear();
    for (const node of this.#spawnNodes) this.#registry.register(node, null);
    this.#panel.setSpawnRegions(this.#spawnNodes);
    this.#panel.onRegionDeselect();
    this.#panel.reloadSpawnList(this.#mapName);
  }
}

// ── helpers ───────────────────────────────────────────────────────────────

function _normalizeIslands(islands) {
  return islands.map(isl => ({
    ...isl,
    simplified_polygon: isl.simplified_polygon ?? _geojsonToSimplified(isl.polygon),
  }));
}

function _geojsonToSimplified(polygon) {
  if (!polygon?.coordinates?.length) return null;
  return { exterior: polygon.coordinates[0] || [], holes: polygon.coordinates.slice(1) };
}

function _buildSpawnGroups(regions, categories) {
  const spawnNodes = [];
  for (const [id, region] of Object.entries(regions || {})) {
    if (categories[id] !== "spawn") continue;
    const b = region.bounds_2d;
    const node = {
      id,
      type:   region.type,
      label:  id,
      color:  region.type === "point" ? POINT_COLOR : SPAWN_COLOR,
      bounds: b ? {
        min_x: b.min.x, min_z: b.min.z,
        max_x: b.max.x, max_z: b.max.z,
      } : null,
      children: [],
    };
    if (region.type === "cylinder") {
      node.base_x = region.base?.x ?? 0;
      node.base_y = region.base?.y ?? 0;
      node.base_z = region.base?.z ?? 0;
      node.radius = region.radius ?? 0;
      node.height = region.height ?? 0;
    } else if (region.type === "point") {
      node.pos_x = region.position?.x ?? 0;
      node.pos_y = region.position?.y ?? 0;
      node.pos_z = region.position?.z ?? 0;
    }
    spawnNodes.push(node);
  }
  if (!spawnNodes.length) return [];
  return [{ name: "spawns", label: "Spawn Regions", color: SPAWN_COLOR, regions: spawnNodes }];
}
