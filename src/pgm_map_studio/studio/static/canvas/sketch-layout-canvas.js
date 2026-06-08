/**
 * sketch-layout-canvas.js — Drawing canvas for the Layout activity.
 *
 * Inherits pan/zoom from CanvasBase. Adds four draw tools (rectangle, circle,
 * polygon, lasso), 8-point resize handles for rectangles, vertex drag for
 * polygons, and two optional overlay layers (primitives + mirror preview).
 *
 * World coordinates are used directly as SVG base coordinates — no
 * buildTransform needed. fitToBbox() computes scale/pan to fit the bbox.
 *
 * Callbacks (all optional):
 *   onShapeCreated(partial)    — new shape finished; caller assigns id and triggers recompute
 *   onShapeUpdated(shape)      — shape mutated (resize / vertex drag)
 *   onShapeSelected(id|null)   — shape clicked or canvas clicked to deselect
 *   onShapeDeleted(id)         — Delete/Backspace pressed with a shape selected
 *   onCursorCoords(x, z)       — world block coords under cursor (null, null on leave)
 */

import { CanvasBase } from "./canvas-base.js";
import { svgEl, ringToPath, polyToPath } from "./transform.js";
import { renderShape } from "../shared/shape-render.js";
import { pointInRing } from "../sketch/geometry.js";
import { SketchDrawController } from "./sketch-draw-controller.js";
import { SketchEditController } from "./sketch-edit-controller.js";

// ── Constants ─────────────────────────────────────────────────────────────────

const FIT_MARGIN = 0.85;

// Shape colours — all defined as tokens in tokens.css
const ADD_FILL    = "var(--canvas-add-fill)";
const ADD_STROKE  = "var(--canvas-add-stroke)";
const SUB_FILL    = "var(--canvas-sub-fill)";
const SUB_STROKE  = "var(--canvas-sub-stroke)";

// Island result colour (when no per-island colour is supplied)
const DEFAULT_ISLAND_FILL   = "var(--canvas-result-fill)";
const DEFAULT_ISLAND_STROKE = "var(--canvas-result-stroke)";

// In SketchLayoutCanvas, world coords ARE SVG base coords (no buildTransform needed).
// This identity passes world (x, z) straight through to the SVG coordinate system.
// EditorCanvas uses buildInverseTransform() for the same _clientToSvg() output — do not
// collapse that distinction.
const identityTransform = (x, z) => ({ x, y: z });

// ── SketchLayoutCanvas ────────────────────────────────────────────────────────

export class SketchLayoutCanvas extends CanvasBase {
  // current setup values
  #bbox    = null;   // { min_x, max_x, min_z, max_z }
  #centerX = 0;
  #centerZ = 0;
  #mode    = "rot_180";

  // shapes (primitive overlay)
  #shapes      = new Map();   // id → shape
  #shapeElMap  = new Map();   // id → SVG <g>
  #selectedId  = null;

  // island polygons (computed result)
  #islands     = [];  // [{ exterior, holes }]

  // mirror preview polygons
  #mirrorPolys = [];  // [{ exterior, holes }]

  // visibility toggles
  #shapesVisible = false;
  #mirrorVisible = true;

  // controllers (instantiated in _build)
  #draw = null;
  #edit = null;

  // callbacks
  #callbacks = {};

  // SVG layers
  #bboxLayer    = null;
  #chunkLayer   = null;
  #axisLayer    = null;
  #mirrorLayer  = null;
  #islandLayer  = null;
  #shapesLayer  = null;
  #drawLayer    = null;
  #handlesLayer     = null;   // screen-space, outside viewport
  #centerLayer      = null;   // screen-space, outside viewport
  #drawHandlesLayer = null;   // screen-space, outside viewport

  // cursor element for coordinate display
  #cursorEl = null;
  // zoom element for zoom level display
  #zoomEl = null;

  constructor(svgEl_, wrapEl, { cursorEl, zoomEl, ...callbacks } = {}) {
    super(svgEl_, wrapEl);
    this.#callbacks = callbacks;
    this.#cursorEl  = cursorEl ?? null;
    this.#zoomEl    = zoomEl ?? null;
    this._build();
  }

  // ── Public API ────────────────────────────────────────────────────────────────

  setBbox(bbox) {
    this.#bbox = bbox;
    this._renderBbox();
    this._renderChunkGrid();
    this._renderAxis();
  }

  setCenter(cx, cz) {
    this.#centerX = cx;
    this.#centerZ = cz;
    this._renderAxis();
    this._refreshCenter();
  }

  setMode(mode) {
    this.#mode = mode;
    this._renderAxis();
  }

  fitToBbox() {
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    const { w, h } = this.#canvasSize();
    const bw = max_x - min_x, bh = max_z - min_z;
    if (!bw || !bh) return;
    const scale = Math.min(w / bw, h / bh) * FIT_MARGIN;
    this._scale = scale;
    this._panX  = w / 2 - ((min_x + max_x) / 2) * scale;
    this._panY  = h / 2 - ((min_z + max_z) / 2) * scale;
    this._applyViewportTransform();
  }

  resize() {
    const { w, h } = this.#canvasSize();
    this._svg.setAttribute("width",  w);
    this._svg.setAttribute("height", h);
    this._svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    this.#edit?.refresh();
    this._refreshCenter();
  }

  #canvasSize() {
    const subbar = this._wrap.querySelector(".canvas-subbar");
    const w = this._wrap.clientWidth  || 600;
    const h = (this._wrap.clientHeight || 600) - (subbar?.offsetHeight ?? 0);
    return { w, h };
  }

  // ── Shape management ─────────────────────────────────────────────────────────

  setActiveTool(tool) {
    this.#draw?.cancel();
    this._activeTool = tool;
    const isDrawTool = tool !== null && tool !== "move" && tool !== "select";
    this._svg.style.cursor = isDrawTool ? "crosshair" : (tool === "select" ? "default" : "");
  }

  setOperation(op) { this.#draw?.setOperation(op); }

  addShape(shape) {
    this.#shapes.set(shape.id, shape);
    if (this.#shapesLayer) {
      const g = this._renderShapeEl(shape);
      this.#shapeElMap.set(shape.id, g);
      this.#shapesLayer.appendChild(g);
    }
  }

  updateShape(shape) {
    this.#shapes.set(shape.id, shape);
    const old = this.#shapeElMap.get(shape.id);
    if (old?.parentNode) old.parentNode.removeChild(old);
    if (this.#shapesLayer) {
      const g = this._renderShapeEl(shape);
      this.#shapeElMap.set(shape.id, g);
      this.#shapesLayer.appendChild(g);
    }
    if (this.#selectedId === shape.id) this.#edit?.refresh();
  }

  removeShape(id) {
    this.#shapes.delete(id);
    const el = this.#shapeElMap.get(id);
    if (el?.parentNode) el.parentNode.removeChild(el);
    this.#shapeElMap.delete(id);
    if (this.#selectedId === id) {
      this.#selectedId = null;
      this.#edit?.setSelected(null);
      this.#edit?.refresh();
    }
  }

  clearShapes() {
    for (const id of [...this.#shapes.keys()]) this.removeShape(id);
  }

  selectShape(id) {
    this.#selectedId = id;
    for (const [sid, g] of this.#shapeElMap) {
      g.classList.toggle("sk-shape--selected", sid === id);
    }
    this.#edit?.setSelected(id);
    this.#edit?.refresh();
  }

  // ── Island + mirror polygons ──────────────────────────────────────────────────

  setIslands(islands) {
    this.#islands = islands ?? [];
    this._rebuildIslandLayer();
  }

  setMirrorPolygons(polys) {
    this.#mirrorPolys = polys ?? [];
    this._rebuildMirrorLayer();
  }

  setShapesVisible(v) {
    this.#shapesVisible = v;
    if (this.#shapesLayer) this.#shapesLayer.style.display = v ? "" : "none";
  }

  setMirrorVisible(v) {
    this.#mirrorVisible = v;
    if (this.#mirrorLayer) this.#mirrorLayer.style.display = v ? "" : "none";
  }

  setChunkVisible(v) {
    if (this.#chunkLayer) this.#chunkLayer.style.display = v ? "" : "none";
  }

  // ── CanvasBase hooks ──────────────────────────────────────────────────────────

  _onViewportChanged() {
    this.#edit?.refresh();
    this._refreshCenter();
    this.#draw?.refreshDrawHandles();
  }

  _onToolMousedown(e, svgPt) {
    const bx = Math.floor(svgPt.x), bz = Math.floor(svgPt.y);
    this.#draw?.onMouseDown(bx, bz, this._activeTool);
  }

  _onPointerMove(e, svgPt) {
    const bx = Math.floor(svgPt.x), bz = Math.floor(svgPt.y);
    this.#draw?.onMouseMove(bx, bz);
    if (this.#cursorEl) this.#cursorEl.textContent = `X ${bx}  Z ${bz}`;
    this.#edit?.onPointerMove(svgPt.x, svgPt.y, this._activeTool);
  }

  _onToolMouseup(e, svgPt) {
    this.#draw?.onMouseUp();
  }

  _onCanvasClick(e, svgPt) {
    // Only fires when activeTool is null/move and no drag occurred.
    const wx = svgPt.x, wz = svgPt.y;
    const hit = this.#hitTestShapes(wx, wz);
    this.#callbacks.onShapeSelected?.(hit);
  }

  _onMouseleave() {
    if (this.#cursorEl) this.#cursorEl.textContent = "";
    this.#callbacks.onCursorCoords?.(null, null);
  }

  _onResizeMove(e) {
    if (!this.#edit) return false;
    const svgPt = this._clientToSvg(e.clientX, e.clientY);
    return this.#edit.onResizeMove(svgPt.x, svgPt.y);
  }

  _onResizeUp(e) {
    if (e.button !== 0) return false;
    return this.#edit?.onResizeUp() ?? false;
  }

  // ── Build ─────────────────────────────────────────────────────────────────────

  _onZoom(scale) {
    if (this.#zoomEl) this.#zoomEl.textContent = `${Math.round(scale * 100)}%`;
  }

  _build() {
    const { w, h } = this.#canvasSize();
    this._svg.setAttribute("width",  w);
    this._svg.setAttribute("height", h);
    this._svg.setAttribute("viewBox", `0 0 ${w} ${h}`);

    this._viewportG   = svgEl("g", { id: "sk-layout-viewport" });
    this.#bboxLayer   = svgEl("g", { id: "sk-layout-bbox",   "pointer-events": "none" });
    this.#chunkLayer  = svgEl("g", { id: "sk-layout-chunks", "pointer-events": "none" });
    this.#axisLayer   = svgEl("g", { id: "sk-layout-axis",   "pointer-events": "none" });
    this.#mirrorLayer = svgEl("g", { id: "sk-layout-mirror", "pointer-events": "none" });
    this.#islandLayer = svgEl("g", { id: "sk-layout-islands","pointer-events": "none" });
    this.#shapesLayer = svgEl("g", { id: "sk-layout-shapes" });
    this.#drawLayer   = svgEl("g", { id: "sk-layout-draw",   "pointer-events": "none" });

    this._viewportG.appendChild(this.#bboxLayer);
    this._viewportG.appendChild(this.#chunkLayer);
    this._viewportG.appendChild(this.#axisLayer);
    this._viewportG.appendChild(this.#mirrorLayer);
    this._viewportG.appendChild(this.#islandLayer);
    this._viewportG.appendChild(this.#shapesLayer);
    this._viewportG.appendChild(this.#drawLayer);
    this._svg.appendChild(this._viewportG);

    this.#handlesLayer     = svgEl("g", { id: "sk-layout-handles" });
    this.#centerLayer      = svgEl("g", { id: "sk-layout-center",       "pointer-events": "none" });
    this.#drawHandlesLayer = svgEl("g", { id: "sk-layout-draw-handles", "pointer-events": "none" });
    this._svg.appendChild(this.#handlesLayer);
    this._svg.appendChild(this.#centerLayer);
    this._svg.appendChild(this.#drawHandlesLayer);

    if (!this.#shapesVisible) this.#shapesLayer.style.display = "none";
    if (!this.#mirrorVisible) this.#mirrorLayer.style.display = "none";

    this._applyViewportTransform();

    const getViewport = () => ({ scale: this._scale, panX: this._panX, panY: this._panY });

    this.#draw = new SketchDrawController(
      this.#drawLayer,
      this.#drawHandlesLayer,
      getViewport,
      {
        onShapeCreated: (partial) => this.#callbacks.onShapeCreated?.(partial),
      },
    );

    this.#edit = new SketchEditController(
      this.#handlesLayer,
      getViewport,
      (id) => this.#shapes.get(id),
      {
        onShapeUpdated: (shape) => {
          this.updateShape(shape);
          this.#callbacks.onShapeUpdated?.(shape);
        },
      },
    );

    // Keyboard: Escape cancels draw; Delete/Backspace deletes selected shape.
    document.addEventListener("keydown", (e) => {
      if (this._wrap.closest("[hidden]")) return;
      if (["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
      if (e.key === "Escape") this.#draw.cancel();
      if ((e.key === "Delete" || e.key === "Backspace") && this.#selectedId) {
        this.#callbacks.onShapeDeleted?.(this.#selectedId);
      }
    });

    // Double-click closes polygon (duplicate vertex removed inside controller).
    this._svg.addEventListener("dblclick", (e) => {
      if (this._activeTool !== "polygon") return;
      e.stopPropagation();
      this.#draw.onDblClick();
    });
  }

  // ── Bbox + axis rendering ─────────────────────────────────────────────────────

  _renderBbox() {
    if (!this.#bboxLayer) return;
    while (this.#bboxLayer.firstChild) this.#bboxLayer.removeChild(this.#bboxLayer.firstChild);
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    this.#bboxLayer.appendChild(svgEl("rect", {
      x: min_x, y: min_z, width: max_x - min_x, height: max_z - min_z,
      fill: "var(--bg-selected)", "fill-opacity": "0.18",
      stroke: "var(--border)", "stroke-width": "1",
      "vector-effect": "non-scaling-stroke",
    }));
  }

  _renderChunkGrid() {
    if (!this.#chunkLayer) return;
    while (this.#chunkLayer.firstChild) this.#chunkLayer.removeChild(this.#chunkLayer.firstChild);
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    const attrs = {
      stroke: "var(--canvas-chunk)", "stroke-width": "1",
      "stroke-dasharray": "3 3", opacity: "1",
      "vector-effect": "non-scaling-stroke",
    };
    const addLine = (x1, y1, x2, y2) =>
      this.#chunkLayer.appendChild(svgEl("line", { x1, y1, x2, y2, ...attrs }));

    const startX = Math.ceil(min_x / 16) * 16;
    for (let x = startX; x <= max_x; x += 16) {
      addLine(x, min_z, x, max_z);
    }
    const startZ = Math.ceil(min_z / 16) * 16;
    for (let z = startZ; z <= max_z; z += 16) {
      addLine(min_x, z, max_x, z);
    }
  }

  _renderAxis() {
    if (!this.#axisLayer) return;
    while (this.#axisLayer.firstChild) this.#axisLayer.removeChild(this.#axisLayer.firstChild);
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    const cx = this.#centerX, cz = this.#centerZ;
    const attrs = {
      stroke: "var(--canvas-axis)", "stroke-width": "1",
      "stroke-dasharray": "6 4", opacity: "0.75",
      "vector-effect": "non-scaling-stroke",
    };
    const addLine = (x1, y1, x2, y2) =>
      this.#axisLayer.appendChild(svgEl("line", { x1, y1, x2, y2, ...attrs }));

    switch (this.#mode) {
      case "mirror_x": addLine(cx, min_z, cx, max_z); break;
      case "mirror_z": addLine(min_x, cz, max_x, cz); break;
      default:
        addLine(cx, min_z, cx, max_z);
        addLine(min_x, cz, max_x, cz);
    }
  }

  // ── Island layer ─────────────────────────────────────────────────────────────

  _rebuildIslandLayer() {
    if (!this.#islandLayer) return;
    while (this.#islandLayer.firstChild) this.#islandLayer.removeChild(this.#islandLayer.firstChild);
    for (const isl of this.#islands) {
      if (!isl?.exterior?.length) continue;
      this.#islandLayer.appendChild(svgEl("path", {
        d: polyToPath({ exterior: isl.exterior, holes: isl.holes ?? [] }, identityTransform),
        fill: DEFAULT_ISLAND_FILL, stroke: DEFAULT_ISLAND_STROKE,
        "stroke-width": "1.5", "fill-opacity": "0.22",
        "fill-rule": "evenodd", "vector-effect": "non-scaling-stroke",
      }));
    }
  }

  // ── Mirror layer ─────────────────────────────────────────────────────────────

  _rebuildMirrorLayer() {
    if (!this.#mirrorLayer) return;
    while (this.#mirrorLayer.firstChild) this.#mirrorLayer.removeChild(this.#mirrorLayer.firstChild);
    for (const poly of this.#mirrorPolys) {
      if (!poly?.exterior?.length) continue;
      this.#mirrorLayer.appendChild(svgEl("path", {
        d: polyToPath({ exterior: poly.exterior, holes: poly.holes ?? [] }, identityTransform),
        fill: "var(--canvas-mirror-fill)", stroke: "var(--canvas-mirror-stroke)",
        "stroke-width": "1",
        "fill-rule": "evenodd", "vector-effect": "non-scaling-stroke",
      }));
    }
  }

  // ── Shape elements ────────────────────────────────────────────────────────────

  _renderShapeEl(shape) {
    const isAdd    = shape.operation !== "subtract";
    const fill     = isAdd ? ADD_FILL   : SUB_FILL;
    const stroke   = isAdd ? ADD_STROKE : SUB_STROKE;
    const dashAttr = shape.override ? { "stroke-dasharray": "6 3" } : {};
    const common   = {
      fill, stroke, "stroke-width": "1.2", "fill-opacity": "0.28",
      "vector-effect": "non-scaling-stroke", ...dashAttr,
    };

    const g = svgEl("g", { class: "sk-shape", "data-id": shape.id });

    if (shape.type === "rectangle") {
      const el = renderShape("rectangle", shape, identityTransform, common);
      if (el) g.appendChild(el);
    } else if (shape.type === "circle") {
      const bounds = {
        min_x: shape.center_x - shape.radius, max_x: shape.center_x + shape.radius,
        min_z: shape.center_z - shape.radius, max_z: shape.center_z + shape.radius,
      };
      const el = renderShape("circle", bounds, identityTransform, common);
      if (el) g.appendChild(el);
    } else if (shape.type === "polygon" || shape.type === "lasso") {
      if (shape.vertices?.length >= 3) {
        g.appendChild(svgEl("path", {
          d: ringToPath(shape.vertices, identityTransform),
          "fill-rule": "evenodd", ...common,
        }));
      }
    }

    g.style.cursor = "pointer";
    g.addEventListener("click", (e) => {
      if (this._activeTool !== null && this._activeTool !== "move" && this._activeTool !== "select") return;
      e.stopPropagation();
      this.#callbacks.onShapeSelected?.(shape.id);
    });

    return g;
  }

  // ── Center marker ─────────────────────────────────────────────────────────────

  #toScreen(wx, wz) {
    return { x: wx * this._scale + this._panX, y: wz * this._scale + this._panY };
  }

  _refreshCenter() {
    if (!this.#centerLayer) return;
    while (this.#centerLayer.firstChild) this.#centerLayer.removeChild(this.#centerLayer.firstChild);
    const sp  = this.#toScreen(this.#centerX, this.#centerZ);
    const arm = 10;
    const col = "var(--canvas-axis)";
    this.#centerLayer.appendChild(svgEl("line", { x1: sp.x - arm, y1: sp.y, x2: sp.x + arm, y2: sp.y, stroke: col, "stroke-width": "1" }));
    this.#centerLayer.appendChild(svgEl("line", { x1: sp.x, y1: sp.y - arm, x2: sp.x, y2: sp.y + arm, stroke: col, "stroke-width": "1" }));
    this.#centerLayer.appendChild(svgEl("circle", { cx: sp.x, cy: sp.y, r: 4, fill: "none", stroke: col, "stroke-width": "1.5" }));
  }

  // ── Hit testing ───────────────────────────────────────────────────────────────

  #hitTestShapes(wx, wz) {
    const ids = [...this.#shapes.keys()];
    for (let i = ids.length - 1; i >= 0; i--) {
      const shape = this.#shapes.get(ids[i]);
      if (this.#shapeContainsPoint(shape, wx, wz)) return shape.id;
    }
    return null;
  }

  #shapeContainsPoint(shape, wx, wz) {
    if (shape.type === "rectangle") {
      return wx >= shape.min_x && wx <= shape.max_x && wz >= shape.min_z && wz <= shape.max_z;
    }
    if (shape.type === "circle") {
      return Math.hypot(wx - shape.center_x, wz - shape.center_z) <= shape.radius;
    }
    if (shape.type === "polygon" || shape.type === "lasso") {
      return shape.vertices?.length >= 3 && pointInRing(wx, wz, shape.vertices);
    }
    return false;
  }

}
