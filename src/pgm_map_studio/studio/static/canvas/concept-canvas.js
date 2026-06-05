/**
 * ConceptCanvas — SVG canvas for the Sketch (concept-first) workflow.
 * Extends CanvasBase for shared pan/zoom/transform machinery.
 *
 * Stub implementation: pan and zoom only. Full drawing tools are added in
 * Phase 1 (Sketch — Layout activity).
 *
 * Public surface (planned):
 *   render(bbox)         initialise canvas from bounding box
 *   resize()             re-render at new dimensions (preserves zoom)
 *   setActiveTool(tool)  null | "move" | "rectangle" | "circle" | "polygon" | "lasso"
 *
 * bbox shape: { min_x, min_z, max_x, max_z }
 */

import { buildTransform, buildInverseTransform, svgEl } from "./transform.js";
import { CanvasBase } from "./canvas-base.js";

export class ConceptCanvas extends CanvasBase {
  #bbox    = null;
  #toSvg   = null;
  #toWorld = null;

  constructor(svgEl_, wrapEl) {
    super(svgEl_, wrapEl);
  }

  // ── public API ─────────────────────────────────────────────────────────────

  render(bbox) {
    this.#bbox   = bbox;
    this._scale  = 1;
    this._panX   = 0;
    this._panY   = 0;
    this.#repaint();
  }

  resize() {
    if (!this.#bbox) return;
    this.#repaint();
  }

  setActiveTool(tool) {
    this._activeTool = tool;
    this._svg.style.cursor = tool && tool !== "move" ? "crosshair" : (tool === "move" ? "grab" : "default");
  }

  // ── CanvasBase hook overrides ──────────────────────────────────────────────

  _onPointerMove(e, svgPt) {
    // TODO (Phase 1.3): dispatch to active draw tool
  }

  _onToolMousedown(e, svgPt) {
    // TODO (Phase 1.3): dispatch to active draw tool
  }

  _onToolMouseup(e, svgPt) {
    // TODO (Phase 1.3): dispatch to active draw tool
  }

  _onCanvasClick(e, svgPt) {
    // TODO (Phase 1.3): hit-test shapes and islands
  }

  // ── rendering ──────────────────────────────────────────────────────────────

  #repaint() {
    const w = this._wrap.clientWidth  || 400;
    const h = this._wrap.clientHeight || 400;
    this._svg.setAttribute("width",   w);
    this._svg.setAttribute("height",  h);
    this._svg.setAttribute("viewBox", `0 0 ${w} ${h}`);

    this.#toSvg   = buildTransform(this.#bbox, w, h);
    this.#toWorld = buildInverseTransform(this.#bbox, w, h);

    while (this._svg.firstChild) this._svg.removeChild(this._svg.firstChild);

    const viewport = svgEl("g");
    this._viewportG = viewport;
    this._applyViewportTransform();

    // TODO (Phase 1.3): add island, shape, and overlay layers here

    this._svg.appendChild(viewport);
  }
}
