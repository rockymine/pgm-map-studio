/**
 * ObjectivesActivity — workspace for the Objectives (wool) activity.
 * Renders wool room regions on the map canvas and wires up ObjectivesPanel.
 */

import { EditorCanvas }      from "../canvas/editor-canvas.js";
import { ObjectivesPanel }   from "../panels/objectives-panel.js";
import { RegionRegistry }    from "../region/region-registry.js";
import { ToolManager }       from "../shared/tool-manager.js";
import * as api              from "../api.js";
import { showToast }         from "../shared/ui-helpers.js";
import { normalizeIslands,
         drawResultToPayload,
         makeBoundsHandlers } from "../shared/canvas-helpers.js";

const WOOL_REGION_COLOR = "var(--canvas-region)";

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
      onDeleteRegion:   (regionId) => this.#removeRegion(regionId),
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
      const [regionsData, islands] = await Promise.all([
        api.fetchRegions(mapName),
        api.fetchIslands(mapName).catch(() => null),
      ]);
      if (!regionsData.bounding_box) return;
      const nodes  = _buildWoolNodes(regionsData.regions, regionsData.categories);
      const groups = nodes.length ? [{ name: "wool", label: null, regions: nodes }] : [];
      this.#canvas.render({
        bounding_box: regionsData.bounding_box,
        islands: normalizeIslands(islands || []),
      }, groups);
      this.#registry.clear();
      this.#woolNodes = nodes;
      _registerNodes(nodes, this.#registry);
      this.#panel.setWoolRegions(nodes);
      this.#canvas.autoLoadBlocks();
    } catch (err) {
      console.error("ObjectivesActivity: failed to load map:", err);
    }
  }

  async #reloadRegions(selectId = null) {
    const regionsData = await api.fetchRegions(this.#mapName);
    const nodes  = _buildWoolNodes(regionsData.regions, regionsData.categories);
    const groups = nodes.length ? [{ name: "wool", label: null, regions: nodes }] : [];
    this.#canvas.refreshRegions(groups);
    this.#registry.clear();
    this.#woolNodes = nodes;
    _registerNodes(nodes, this.#registry);
    this.#panel.setWoolRegions(nodes);
    if (selectId) {
      const node = this.#woolNodes.find(n => n.id === selectId);
      if (node) this.#registry.select(selectId);
    }
  }

  async #onRegionDraw(drawResult) {
    if (!this.#mapName) return;
    if (!["rectangle", "cuboid", "cylinder", "circle", "block", "point"].includes(drawResult.type)) return;

    this.#toolMgr.setTool("move");
    const payload = drawResultToPayload(drawResult, "wool");

    try {
      const result = await api.createRegion(this.#mapName, payload);
      await this.#reloadRegions();
      if (result?.id) {
        const node = this.#woolNodes.find(n => n.id === result.id);
        if (node) this.#registry.select(result.id);
      }
    } catch (err) {
      showToast(`Failed to create wool room region: ${err.message}`, "error");
    }
  }

  #removeRegion(regionId) {
    this.#canvas.removeRegion(regionId);
    this.#woolNodes = this.#woolNodes.filter(n => n.id !== regionId);
    this.#registry.clear();
    for (const node of this.#woolNodes) this.#registry.register(node, null);
    this.#panel.setWoolRegions(this.#woolNodes);
    this.#panel.onRegionDeselect();
  }
}


const _TYPE_PRIORITY = { block: 0, point: 0, rectangle: 1, cuboid: 1, cylinder: 1, circle: 1, sphere: 1 };
function _typePriority(type) { return _TYPE_PRIORITY[type] ?? 2; }

/** Build tree nodes for all wool-category regions from the flat regions dict. */
function _buildWoolNodes(regions, categories) {
  const nodes = [];
  for (const [id, region] of Object.entries(regions || {})) {
    if (categories[id] !== "wool") continue;
    nodes.push(_encodeNode(id, region, regions));
  }
  nodes.sort((a, b) => {
    const pd = _typePriority(a.type) - _typePriority(b.type);
    return pd !== 0 ? pd : a.id.localeCompare(b.id);
  });
  return nodes;
}

function _encodeNode(id, region, registry) {
  const b = region.bounds_2d;
  const children = [];
  for (const child of region.children || []) {
    if (typeof child === "string") {
      const childRegion = registry?.[child];
      if (childRegion) children.push(_encodeNode(child, childRegion, registry));
    } else if (child && typeof child === "object") {
      children.push(_encodeNode(child.id || "", child, registry));
    }
  }
  return {
    id,
    type:        region.type,
    label:       id || `(${region.type})`,
    color:       WOOL_REGION_COLOR,
    bounds:      b ? { min_x: b.min.x, min_z: b.min.z, max_x: b.max.x, max_z: b.max.z } : null,
    coords:      _buildCoords(region),
    children,
    synthetic_id: !id,
  };
}

function _buildCoords(region) {
  const t = region.type;
  if (t === "rectangle" || t === "cuboid") {
    const mn = region.min || region.bounds_2d?.min || {};
    const mx = region.max || region.bounds_2d?.max || {};
    return { min_x: mn.x, min_y: mn.y, min_z: mn.z, max_x: mx.x, max_y: mx.y, max_z: mx.z };
  }
  if (t === "cylinder") {
    const b = region.base || {};
    return { base_x: b.x, base_y: b.y, base_z: b.z, radius: region.radius, height: region.height };
  }
  if (t === "circle") {
    const c = region.center || {};
    return { center_x: c.x, center_z: c.z, radius: region.radius };
  }
  if (t === "point" || t === "block") {
    const p = region.position || {};
    return { x: p.x, y: p.y, z: p.z };
  }
  return null;
}

function _registerNodes(nodes, registry) {
  for (const n of nodes) {
    if (n.id) registry.register(n, null);
    if (n.children?.length) _registerNodes(n.children, registry);
  }
}
