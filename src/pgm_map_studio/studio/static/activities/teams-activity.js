/**
 * TeamsActivity — workspace for the Teams activity.
 * Shows spawn regions on the map canvas and wires up the TeamsPanel.
 */

import { MapCanvas }      from "../canvas/map-canvas.js";
import { TeamsPanel }     from "../panels/teams-panel.js";
import { RegionRegistry } from "../region/region-registry.js";
import * as api           from "../api.js";
import { chatColorHex }   from "../shared/game-colors.js";

const SPAWN_COLOR  = "#3b82f6";
const POINT_COLOR  = "#60a5fa";

export class TeamsActivity {
  #el      = null;
  #canvas  = null;
  #panel   = null;
  #registry= null;
  #mapName = null;
  #coordsEl= null;
  #zoomEl  = null;

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

    this.#canvas = new MapCanvas(svgEl, wrapEl, {
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
    });

    // Wire draw tool buttons
    const moveBtn     = document.getElementById("pt-tool-move");
    const selectBtn   = document.getElementById("pt-tool-select");
    const cylinderBtn = document.getElementById("pt-tool-cylinder");
    const pointBtn    = document.getElementById("pt-tool-point");

    const setTool = (tool, activeBtn) => {
      this.#canvas.setActiveTool(tool);
      for (const btn of [moveBtn, selectBtn, cylinderBtn, pointBtn]) {
        btn?.classList.toggle("draw-tool-btn--active", btn === activeBtn);
      }
    };

    moveBtn?.addEventListener("click",     () => setTool("move",     moveBtn));
    selectBtn?.addEventListener("click",   () => setTool(null,       selectBtn));
    cylinderBtn?.addEventListener("click", () => setTool("cylinder", cylinderBtn));
    pointBtn?.addEventListener("click",    () => setTool("point",    pointBtn));

    setTool("move", moveBtn);

    document.addEventListener("keydown", (e) => {
      if (this.#el.hidden) return;
      if (e.target.matches("input,select,textarea")) return;
      if (e.key === "m" || e.key === "M") setTool("move",    moveBtn);
      if (e.key === "s" || e.key === "S") setTool(null,      selectBtn);
      if (e.key === "y" || e.key === "Y") setTool("cylinder",cylinderBtn);
      if (e.key === "p" || e.key === "P") setTool("point",   pointBtn);
      if (e.key === "Escape") setTool("move", moveBtn);
    });
  }

  async #loadMap(mapName) {
    try {
      const [regionsData, islands] = await Promise.all([
        api.fetchRegions(mapName),
        api.fetchIslands(mapName).catch(() => null),
      ]);

      const ctx = {
        bounding_box: regionsData.bounding_box,
        islands: _normalizeIslands(islands || []),
      };

      const groups = _buildSpawnGroups(regionsData.regions, regionsData.categories);
      this.#canvas.render(ctx, groups);

      // Register spawn nodes in the registry + inform the panel
      this.#registry.clear();
      const spawnNodes = groups.flatMap(g => g.regions);
      for (const node of spawnNodes) this.#registry.register(node, null);
      this.#panel.setSpawnRegions(spawnNodes);
    } catch (err) {
      console.error("TeamsActivity: failed to load map:", err);
    }
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
    spawnNodes.push({
      id,
      type:   region.type,
      label:  id,
      color:  region.type === "point" ? POINT_COLOR : SPAWN_COLOR,
      bounds: b ? {
        min_x: b.min.x, min_z: b.min.z,
        max_x: b.max.x, max_z: b.max.z,
      } : null,
      children: [],
    });
  }
  if (!spawnNodes.length) return [];
  return [{ name: "spawns", label: "Spawn Regions", color: SPAWN_COLOR, regions: spawnNodes }];
}
