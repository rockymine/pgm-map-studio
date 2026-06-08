/**
 * SketchEditController — 8-point rectangle resize handles and polygon vertex
 * drag for SketchLayoutCanvas. Extracted from sketch-layout-canvas.js.
 *
 * Constructor args:
 *   handlesLayer  SVGGElement              — screen-space handle layer
 *   getViewport   () => { scale, panX, panY }
 *   getShape      (id: string) => shape | undefined
 *   callbacks     { onShapeUpdated }
 */

import { svgEl, handleRectAttrs } from "./transform.js";

const HANDLE_HALF = 5;
const VERTEX_HALF = 4;

const HANDLE_DEFS = [
  { key: "nw", pos: b => [b.l,  b.t],  cursor: "nw-resize", xf: "min_x", zf: "min_z" },
  { key: "n",  pos: b => [b.mx, b.t],  cursor: "n-resize",  xf: null,    zf: "min_z" },
  { key: "ne", pos: b => [b.r,  b.t],  cursor: "ne-resize", xf: "max_x", zf: "min_z" },
  { key: "w",  pos: b => [b.l,  b.my], cursor: "w-resize",  xf: "min_x", zf: null    },
  { key: "e",  pos: b => [b.r,  b.my], cursor: "e-resize",  xf: "max_x", zf: null    },
  { key: "sw", pos: b => [b.l,  b.b],  cursor: "sw-resize", xf: "min_x", zf: "max_z" },
  { key: "s",  pos: b => [b.mx, b.b],  cursor: "s-resize",  xf: null,    zf: "max_z" },
  { key: "se", pos: b => [b.r,  b.b],  cursor: "se-resize", xf: "max_x", zf: "max_z" },
];

export class SketchEditController {
  #handlesLayer;
  #getViewport;
  #getShape;
  #callbacks;

  #selectedId      = null;
  #rectResizeState = null;   // { shapeId, xf, zf }
  #vertexDragState = null;   // { shapeId, vertexIdx }

  constructor(handlesLayer, getViewport, getShape, { onShapeUpdated } = {}) {
    this.#handlesLayer = handlesLayer;
    this.#getViewport  = getViewport;
    this.#getShape     = getShape;
    this.#callbacks    = { onShapeUpdated };
  }

  /** Sync selected shape id; call refresh() separately to redraw handles. */
  setSelected(id) {
    this.#selectedId = id;
  }

  /** Redraw handles for the current selected shape (call after viewport changes too). */
  refresh() {
    if (!this.#handlesLayer) return;
    while (this.#handlesLayer.firstChild) this.#handlesLayer.removeChild(this.#handlesLayer.firstChild);
    if (!this.#selectedId) return;
    const shape = this.#getShape(this.#selectedId);
    if (!shape) return;
    if (shape.type === "rectangle") {
      this.#renderRectHandles(shape);
    } else if (shape.type === "polygon" || shape.type === "lasso") {
      this.#renderVertexHandles(shape);
    }
  }

  /**
   * Handle document mousemove during a resize or vertex drag.
   * Returns true if the event was consumed.
   */
  onResizeMove(bx, bz) {
    if (this.#vertexDragState) {
      const { shapeId, vertexIdx } = this.#vertexDragState;
      const shape = this.#getShape(shapeId);
      if (shape?.type === "polygon" || shape?.type === "lasso") {
        shape.vertices[vertexIdx] = [bx, bz];
        this.#callbacks.onShapeUpdated?.(shape);
      }
      return true;
    }
    if (this.#rectResizeState) {
      const { shapeId, xf, zf } = this.#rectResizeState;
      const shape = this.#getShape(shapeId);
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
        this.#callbacks.onShapeUpdated?.(shape);
      }
      return true;
    }
    return false;
  }

  /**
   * Handle document mouseup to finish a resize or vertex drag.
   * Returns true if the event was consumed.
   */
  onResizeUp() {
    if (this.#rectResizeState) {
      this.#rectResizeState = null;
      this.refresh();
      return true;
    }
    if (this.#vertexDragState) {
      const { shapeId } = this.#vertexDragState;
      this.#vertexDragState = null;
      this.refresh();
      const shape = this.#getShape(shapeId);
      if (shape) this.#callbacks.onShapeUpdated?.(shape);
      return true;
    }
    return false;
  }

  // ── private ──────────────────────────────────────────────────────────────────

  #toScreen(wx, wz) {
    const { scale, panX, panY } = this.#getViewport();
    return { x: wx * scale + panX, y: wz * scale + panY };
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
        ...handleRectAttrs(hx, hy, HANDLE_HALF),
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
        ...handleRectAttrs(sp.x, sp.y, VERTEX_HALF),
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
}
