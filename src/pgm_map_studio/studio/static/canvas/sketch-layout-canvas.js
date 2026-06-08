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
import { drawnBoundsFromBlocks } from "../shared/converters.js";
import { renderShape } from "../shared/shape-render.js";
import { pointInRing } from "../sketch/geometry.js";

// ── Constants ─────────────────────────────────────────────────────────────────

const HANDLE_HALF  = 5;  // half-size of resize handles in screen px
const VERTEX_HALF  = 4;  // half-size of polygon vertex handles in screen px
const FIT_MARGIN   = 0.85;

// Shape colours
const ADD_FILL    = "#0d9488";
const ADD_STROKE  = "#0f766e";
const SUB_FILL    = "#dc2626";
const SUB_STROKE  = "#b91c1c";

// Island result colour (when no per-island colour is supplied)
const DEFAULT_ISLAND_FILL   = "#6366f1";
const DEFAULT_ISLAND_STROKE = "#4338ca";

// Mirror preview overlay
const MIRROR_FILL    = "var(--canvas-axis)";
const MIRROR_OPACITY = "0.12";

// In SketchLayoutCanvas, world coords ARE SVG base coords (no buildTransform needed).
// This identity passes world (x, z) straight through to the SVG coordinate system.
// MapCanvas uses buildInverseTransform() for the same _clientToSvg() output — do not
// collapse that distinction.
const identityTransform = (x, z) => ({ x, y: z });

// 8-handle definitions for rectangle resize (clockwise from NW)
const HANDLE_DEFS = [
  { key: "nw", pos: b => [b.l, b.t],  cursor: "nw-resize", xf: "min_x", zf: "min_z" },
  { key: "n",  pos: b => [b.mx, b.t], cursor: "n-resize",  xf: null,    zf: "min_z" },
  { key: "ne", pos: b => [b.r, b.t],  cursor: "ne-resize", xf: "max_x", zf: "min_z" },
  { key: "w",  pos: b => [b.l, b.my], cursor: "w-resize",  xf: "min_x", zf: null    },
  { key: "e",  pos: b => [b.r, b.my], cursor: "e-resize",  xf: "max_x", zf: null    },
  { key: "sw", pos: b => [b.l, b.b],  cursor: "sw-resize", xf: "min_x", zf: "max_z" },
  { key: "s",  pos: b => [b.mx, b.b], cursor: "s-resize",  xf: null,    zf: "max_z" },
  { key: "se", pos: b => [b.r, b.b],  cursor: "se-resize", xf: "max_x", zf: "max_z" },
];

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

  // draw state
  #activeOperation = "add";
  #drawState       = null;
  #drawHandleData  = [];    // [{wx, wz, isFirst}] — world coords for screen-space handles

  // resize / vertex drag state
  #rectResizeState = null;   // { shapeId, xf, zf }
  #vertexDragState = null;   // { shapeId, vertexIdx }

  // callbacks
  #callbacks = {};

  // SVG layers
  #bboxLayer    = null;
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
    this._refreshHandles();
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
    this.#cancelDraw();
    this._activeTool = tool;
    const isDrawTool = tool !== null && tool !== "move" && tool !== "select";
    this._svg.style.cursor = isDrawTool ? "crosshair" : (tool === "select" ? "default" : "");
  }

  setOperation(op) { this.#activeOperation = op; }

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
    if (this.#selectedId === shape.id) this._refreshHandles();
  }

  removeShape(id) {
    this.#shapes.delete(id);
    const el = this.#shapeElMap.get(id);
    if (el?.parentNode) el.parentNode.removeChild(el);
    this.#shapeElMap.delete(id);
    if (this.#selectedId === id) { this.#selectedId = null; this._refreshHandles(); }
  }

  clearShapes() {
    for (const id of [...this.#shapes.keys()]) this.removeShape(id);
  }

  selectShape(id) {
    this.#selectedId = id;
    for (const [sid, g] of this.#shapeElMap) {
      g.classList.toggle("sk-shape--selected", sid === id);
    }
    this._refreshHandles();
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

  // ── CanvasBase hooks ──────────────────────────────────────────────────────────

  _onViewportChanged() {
    this._refreshHandles();
    this._refreshCenter();
    this._refreshDrawHandles();
  }

  _onToolMousedown(e, svgPt) {
    const bx = Math.floor(svgPt.x), bz = Math.floor(svgPt.y);
    const tool = this._activeTool;

    if (tool === "rectangle") {
      this.#startRect(bx, bz);
      return;
    }
    if (tool === "lasso") {
      this.#startLasso(bx, bz);
      return;
    }
    if (tool === "circle") {
      if (!this.#drawState) this.#startCircle(bx, bz);
      else                  this.#completeCircle(bx, bz);
      return;
    }
    if (tool === "polygon") {
      if (!this.#drawState) {
        this.#startPolygon(bx, bz);
      } else {
        const [fx, fz] = this.#drawState.vertices[0];
        if (Math.abs(bx - fx) <= 2 && Math.abs(bz - fz) <= 2
            && this.#drawState.vertices.length >= 3) {
          this.#closePolygon();
        } else {
          this.#addPolygonVertex(bx, bz);
        }
      }
    }
  }

  _onPointerMove(e, svgPt) {
    const bx = Math.floor(svgPt.x), bz = Math.floor(svgPt.y);
    if (this.#drawState?.type === "rectangle") this.#updateRectPreview(bx, bz);
    if (this.#drawState?.type === "circle")    this.#updateCirclePreview(bx, bz);
    if (this.#drawState?.type === "polygon")   this.#updatePolygonPreview(bx, bz);
    if (this.#drawState?.type === "lasso")     this.#addLassoPoint(bx, bz);
    if (this.#cursorEl) {
      this.#cursorEl.textContent = `X ${bx}  Z ${bz}`;
    }
  }

  _onToolMouseup(e, svgPt) {
    const bx = Math.floor(svgPt.x), bz = Math.floor(svgPt.y);
    if (this.#drawState?.type === "lasso") {
      this.#completeLasso();
      return;
    }
    if (this._activeTool === "rectangle" && this.#drawState) {
      this.#completeRect();
    }
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
    if (!this.#rectResizeState && !this.#vertexDragState) return false;
    const svgPt = this._clientToSvg(e.clientX, e.clientY);
    const bx = Math.floor(svgPt.x), bz = Math.floor(svgPt.y);

    if (this.#vertexDragState) {
      const { shapeId, vertexIdx } = this.#vertexDragState;
      const shape = this.#shapes.get(shapeId);
      if (shape?.type === "polygon" || shape?.type === "lasso") {
        shape.vertices[vertexIdx] = [bx, bz];
        this.updateShape(shape);
        this.#callbacks.onShapeUpdated?.(shape);
      }
      return true;
    }

    if (this.#rectResizeState) {
      const { shapeId, xf, zf } = this.#rectResizeState;
      const shape = this.#shapes.get(shapeId);
      if (shape?.type === "rectangle") {
        if (xf) shape[xf] = xf === "max_x" ? bx + 1 : bx;
        if (zf) shape[zf] = zf === "max_z" ? bz + 1 : bz;
        if (shape.min_x >= shape.max_x) {
          if (xf === "min_x") shape.min_x = shape.max_x - 1;
          else                shape.max_x = shape.min_x + 1;
        }
        if (shape.min_z >= shape.max_z) {
          if (zf === "min_z") shape.min_z = shape.max_z - 1;
          else                shape.max_z = shape.min_z + 1;
        }
        this.updateShape(shape);
        this.#callbacks.onShapeUpdated?.(shape);
      }
      return true;
    }

    return false;
  }

  _onResizeUp(e) {
    if (e.button !== 0) return false;
    if (this.#rectResizeState) {
      this.#rectResizeState = null;
      this._refreshHandles();
      return true;
    }
    if (this.#vertexDragState) {
      const { shapeId } = this.#vertexDragState;
      this.#vertexDragState = null;
      this._refreshHandles();
      const shape = this.#shapes.get(shapeId);
      if (shape) this.#callbacks.onShapeUpdated?.(shape);
      return true;
    }
    return false;
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
    this.#axisLayer   = svgEl("g", { id: "sk-layout-axis",   "pointer-events": "none" });
    this.#mirrorLayer = svgEl("g", { id: "sk-layout-mirror", "pointer-events": "none" });
    this.#islandLayer = svgEl("g", { id: "sk-layout-islands","pointer-events": "none" });
    this.#shapesLayer = svgEl("g", { id: "sk-layout-shapes" });
    this.#drawLayer   = svgEl("g", { id: "sk-layout-draw",   "pointer-events": "none" });

    this._viewportG.appendChild(this.#bboxLayer);
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

    // Keyboard: Escape cancels draw; Delete/Backspace deletes selected shape.
    document.addEventListener("keydown", (e) => {
      if (this._wrap.closest("[hidden]")) return;
      if (["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
      if (e.key === "Escape") this.#cancelDraw();
      if ((e.key === "Delete" || e.key === "Backspace") && this.#selectedId) {
        this.#callbacks.onShapeDeleted?.(this.#selectedId);
      }
    });

    // Double-click closes polygon.
    this._svg.addEventListener("dblclick", (e) => {
      if (this._activeTool !== "polygon" || !this.#drawState) return;
      e.stopPropagation();
      const ds = this.#drawState;
      // Second click of dblclick may have added a duplicate vertex — remove it.
      if (ds.vertices.length > 1) {
        const last = ds.vertices[ds.vertices.length - 1];
        const prev = ds.vertices[ds.vertices.length - 2];
        if (last[0] === prev[0] && last[1] === prev[1]) {
          ds.vertices.pop();
          const dot  = ds.dots.pop();  dot?.parentNode?.removeChild(dot);
          const line = ds.lines.pop(); line?.parentNode?.removeChild(line);
        }
      }
      this.#closePolygon();
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
        fill: MIRROR_FILL, stroke: MIRROR_FILL,
        "stroke-width": "1", "fill-opacity": MIRROR_OPACITY,
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

  // ── Handles ───────────────────────────────────────────────────────────────────

  _refreshHandles() {
    if (!this.#handlesLayer) return;
    while (this.#handlesLayer.firstChild) this.#handlesLayer.removeChild(this.#handlesLayer.firstChild);
    if (!this.#selectedId) return;
    const shape = this.#shapes.get(this.#selectedId);
    if (!shape) return;
    if (shape.type === "rectangle") {
      this.#renderRectHandles(shape);
    } else if (shape.type === "polygon" || shape.type === "lasso") {
      this.#renderVertexHandles(shape);
    }
  }

  #toScreen(wx, wz) {
    return { x: wx * this._scale + this._panX, y: wz * this._scale + this._panY };
  }

  #renderRectHandles(shape) {
    const tl = this.#toScreen(shape.min_x, shape.min_z);
    const br = this.#toScreen(shape.max_x, shape.max_z);
    const b  = {
      l: Math.min(tl.x, br.x), r: Math.max(tl.x, br.x),
      t: Math.min(tl.y, br.y), b: Math.max(tl.y, br.y),
    };
    b.mx = (b.l + b.r) / 2;
    b.my = (b.t + b.b) / 2;

    for (const hd of HANDLE_DEFS) {
      const [hx, hy] = hd.pos(b);
      const h = svgEl("rect", {
        x: hx - HANDLE_HALF, y: hy - HANDLE_HALF,
        width: HANDLE_HALF * 2, height: HANDLE_HALF * 2,
        fill: "var(--bg-deep)", stroke: "var(--text-muted)", "stroke-width": "1",
        style: `cursor:${hd.cursor}`,
      });
      h.addEventListener("mousedown", (e) => {
        if (e.button !== 0) return;
        e.stopPropagation();
        this.#rectResizeState = { shapeId: shape.id, xf: hd.xf, zf: hd.zf };
      });
      this.#handlesLayer.appendChild(h);
    }
  }

  #renderVertexHandles(shape) {
    if (!shape.vertices?.length) return;
    shape.vertices.forEach(([wx, wz], idx) => {
      const sp = this.#toScreen(wx, wz);
      const h = svgEl("rect", {
        x: sp.x - VERTEX_HALF, y: sp.y - VERTEX_HALF,
        width: VERTEX_HALF * 2, height: VERTEX_HALF * 2,
        fill: "var(--bg-deep)", stroke: "var(--text-muted)", "stroke-width": "1",
        style: "cursor:move",
      });
      h.addEventListener("mousedown", (e) => {
        if (e.button !== 0) return;
        e.stopPropagation();
        this.#vertexDragState = { shapeId: shape.id, vertexIdx: idx };
      });
      this.#handlesLayer.appendChild(h);
    });
  }

  // ── Draw handles (screen-space anchors during active draw) ───────────────────

  _refreshDrawHandles() {
    if (!this.#drawHandlesLayer) return;
    while (this.#drawHandlesLayer.firstChild) this.#drawHandlesLayer.removeChild(this.#drawHandlesLayer.firstChild);
    for (const { wx, wz, isFirst } of this.#drawHandleData) {
      const sp = this.#toScreen(wx, wz);
      this.#drawHandlesLayer.appendChild(svgEl("rect", {
        x: sp.x - HANDLE_HALF, y: sp.y - HANDLE_HALF,
        width: HANDLE_HALF * 2, height: HANDLE_HALF * 2,
        fill:   isFirst ? "var(--accent-light)" : "var(--canvas-handle-fill)",
        stroke: isFirst ? "var(--accent)"       : "var(--canvas-handle-stroke)",
        "stroke-width": "1.5",
      }));
    }
  }

  // ── Center marker ─────────────────────────────────────────────────────────────

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

  // ── Draw tools ────────────────────────────────────────────────────────────────

  #opFill()   { return this.#activeOperation === "subtract" ? SUB_FILL   : ADD_FILL; }
  #opStroke() { return this.#activeOperation === "subtract" ? SUB_STROKE : ADD_STROKE; }

  // Rectangle
  #startRect(bx, bz) {
    const preview = svgEl("rect", {
      fill: this.#opFill(), stroke: this.#opStroke(),
      "stroke-width": "1", "fill-opacity": "0.20", "stroke-dasharray": "5 3",
      "vector-effect": "non-scaling-stroke",
      x: bx, y: bz, width: 1, height: 1,
    });
    this.#drawLayer.appendChild(preview);
    this.#drawState = { type: "rectangle", startBx: bx, startBz: bz, currentBx: bx, currentBz: bz, preview };
    this.#drawHandleData = [{ wx: bx, wz: bz, isFirst: true }];
    this._refreshDrawHandles();
  }

  #updateRectPreview(bx, bz) {
    const { startBx, startBz, preview } = this.#drawState;
    this.#drawState.currentBx = bx;
    this.#drawState.currentBz = bz;
    const { min_x: minX, max_x: maxX, min_z: minZ, max_z: maxZ } = drawnBoundsFromBlocks(startBx, startBz, bx, bz);
    preview.setAttribute("x",      minX);
    preview.setAttribute("y",      minZ);
    preview.setAttribute("width",  maxX - minX);
    preview.setAttribute("height", maxZ - minZ);
    // Update 4-corner handles
    this.#drawHandleData = [
      { wx: minX, wz: minZ, isFirst: false },
      { wx: maxX, wz: minZ, isFirst: false },
      { wx: maxX, wz: maxZ, isFirst: false },
      { wx: minX, wz: maxZ, isFirst: false },
    ];
    this._refreshDrawHandles();
  }

  #completeRect() {
    const { startBx, startBz, currentBx, currentBz, preview } = this.#drawState;
    preview?.parentNode?.removeChild(preview);
    this.#drawState = null;
    this.#drawHandleData = [];
    this._refreshDrawHandles();
    const { min_x: minX, max_x: maxX, min_z: minZ, max_z: maxZ } = drawnBoundsFromBlocks(startBx, startBz, currentBx, currentBz);
    if (maxX - minX <= 1 && maxZ - minZ <= 1) return;  // reject single-click misfire (no drag)
    this.#callbacks.onShapeCreated?.({
      type: "rectangle", operation: this.#activeOperation, override: false,
      min_x: minX, max_x: maxX, min_z: minZ, max_z: maxZ,
    });
  }

  // Circle (two-click: center, then radius)
  #startCircle(bx, bz) {
    const dot = svgEl("rect", {
      x: bx - 0.5, y: bz - 0.5, width: 1, height: 1,
      fill: "var(--text-muted)", "pointer-events": "none",
    });
    const preview = svgEl("ellipse", {
      fill: this.#opFill(), stroke: this.#opStroke(),
      "stroke-width": "1", "fill-opacity": "0.20", "stroke-dasharray": "5 3",
      "vector-effect": "non-scaling-stroke",
      cx: bx, cy: bz, rx: 1, ry: 1,
    });
    this.#drawLayer.appendChild(preview);
    this.#drawLayer.appendChild(dot);
    this.#drawState = { type: "circle", centerX: bx, centerZ: bz, currentRadius: 1, preview, dot };
  }

  #updateCirclePreview(bx, bz) {
    const { centerX, centerZ, preview } = this.#drawState;
    const r = Math.max(1, Math.round(Math.hypot(bx - centerX, bz - centerZ)));
    this.#drawState.currentRadius = r;
    preview.setAttribute("cx", centerX);
    preview.setAttribute("cy", centerZ);
    preview.setAttribute("rx", r);
    preview.setAttribute("ry", r);
  }

  #completeCircle(bx, bz) {
    const { centerX, centerZ, preview, dot } = this.#drawState;
    preview?.parentNode?.removeChild(preview);
    dot?.parentNode?.removeChild(dot);
    this.#drawState = null;
    const radius = Math.max(1, Math.round(Math.hypot(bx - centerX, bz - centerZ)));
    this.#callbacks.onShapeCreated?.({
      type: "circle", operation: this.#activeOperation, override: false,
      center_x: centerX, center_z: centerZ, radius,
    });
  }

  // Polygon (click vertices, close on first-vertex click or dblclick)
  #startPolygon(bx, bz) {
    this.#drawHandleData = [{ wx: bx, wz: bz, isFirst: true }];
    this._refreshDrawHandles();
    const firstDot   = this.#makePolyDot(bx, bz, true);
    const previewLine = svgEl("line", {
      x1: bx, y1: bz, x2: bx, y2: bz,
      stroke: "var(--text-muted)", "stroke-width": "1", "stroke-dasharray": "4 3",
      "pointer-events": "none", "vector-effect": "non-scaling-stroke",
    });
    this.#drawLayer.appendChild(previewLine);
    this.#drawLayer.appendChild(firstDot);
    this.#drawState = { type: "polygon", vertices: [[bx, bz]], dots: [firstDot], lines: [], previewLine };
  }

  #addPolygonVertex(bx, bz) {
    this.#drawHandleData.push({ wx: bx, wz: bz, isFirst: false });
    this._refreshDrawHandles();
    const ds   = this.#drawState;
    const prev = ds.vertices[ds.vertices.length - 1];
    const seg  = svgEl("line", {
      x1: prev[0], y1: prev[1], x2: bx, y2: bz,
      stroke: "var(--text-muted)", "stroke-width": "1",
      "pointer-events": "none", "vector-effect": "non-scaling-stroke",
    });
    this.#drawLayer.insertBefore(seg, ds.previewLine);
    ds.lines.push(seg);
    const dot = this.#makePolyDot(bx, bz, false);
    this.#drawLayer.insertBefore(dot, ds.previewLine);
    ds.dots.push(dot);
    ds.vertices.push([bx, bz]);
    ds.previewLine.setAttribute("x1", bx);
    ds.previewLine.setAttribute("y1", bz);
    ds.previewLine.setAttribute("x2", bx);
    ds.previewLine.setAttribute("y2", bz);
  }

  #updatePolygonPreview(bx, bz) {
    if (!this.#drawState?.previewLine) return;
    this.#drawState.previewLine.setAttribute("x2", bx);
    this.#drawState.previewLine.setAttribute("y2", bz);
  }

  #closePolygon() {
    this.#drawHandleData = [];
    this._refreshDrawHandles();
    const saved = this.#drawState;
    this.#drawState = null;
    for (const el of [...(saved.dots ?? []), ...(saved.lines ?? []), saved.previewLine]) {
      el?.parentNode?.removeChild(el);
    }
    if (saved.vertices.length < 3) return;
    this.#callbacks.onShapeCreated?.({
      type: "polygon", operation: this.#activeOperation, override: false,
      vertices: saved.vertices,
    });
  }

  #makePolyDot(wx, wz, isFirst) {
    return svgEl("rect", {
      x: wx - 0.5, y: wz - 0.5, width: 1, height: 1,
      fill: isFirst ? "#f59e0b" : "var(--text-muted)",
      stroke: "var(--bg-deep)", "stroke-width": "0.08",
      "pointer-events": "none", "vector-effect": "non-scaling-stroke",
    });
  }

  // Lasso (hold drag to trace freeform; release to close)
  #startLasso(bx, bz) {
    const previewPath = svgEl("path", {
      fill: this.#opFill(), stroke: this.#opStroke(),
      "stroke-width": "1", "fill-opacity": "0.20", "stroke-dasharray": "5 3",
      "fill-rule": "evenodd", "vector-effect": "non-scaling-stroke",
    });
    this.#drawLayer.appendChild(previewPath);
    this.#drawState = { type: "lasso", vertices: [[bx, bz]], previewPath };
  }

  #addLassoPoint(bx, bz) {
    const { vertices } = this.#drawState;
    const last = vertices[vertices.length - 1];
    if (bx === last[0] && bz === last[1]) return;
    vertices.push([bx, bz]);
    this.#updateLassoPreview();
  }

  #updateLassoPreview() {
    const { vertices, previewPath } = this.#drawState;
    if (vertices.length < 2) return;
    previewPath.setAttribute("d", ringToPath(vertices, identityTransform));
  }

  #completeLasso() {
    const { vertices, previewPath } = this.#drawState;
    previewPath?.parentNode?.removeChild(previewPath);
    this.#drawState = null;
    if (vertices.length < 3) return;
    this.#callbacks.onShapeCreated?.({
      type: "lasso", operation: this.#activeOperation, override: false,
      vertices,
    });
  }

  #cancelDraw() {
    if (!this.#drawState) return;
    const ds = this.#drawState;
    this.#drawState = null;
    this.#drawHandleData = [];
    this._refreshDrawHandles();
    for (const el of [ds.preview, ds.previewPath, ds.previewLine, ds.dot,
                      ...(ds.dots ?? []), ...(ds.lines ?? [])]) {
      el?.parentNode?.removeChild(el);
    }
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
