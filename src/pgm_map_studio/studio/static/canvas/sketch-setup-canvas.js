import { CanvasBase } from "./canvas-base.js";
import { svgEl as makeEl } from "./transform.js";

const CROSSHAIR_R  = 6;    // screen-px radius of center dot
const CROSSHAIR_ARM = 16;  // screen-px arm length
const HIT_RADIUS   = 20;   // screen-px — drag handle hit area around center
const FIT_MARGIN   = 0.82; // fraction of canvas used when fitting bbox

export class SketchSetupCanvas extends CanvasBase {
  #bbox        = null;  // { min_x, max_x, min_z, max_z }
  #cx          = 0;
  #cz          = 0;
  #mode        = "rot_180";

  #bboxLayer   = null;
  #axisLayer   = null;
  #crosshair   = null;  // screen-space <g>, repositioned on viewport change

  #draggingCenter = false;
  #onCenterMove   = null;  // callback(cx, cz)
  #cursorEl       = null;  // .canvas-cursor span for coordinate readout

  constructor(svgEl, wrapEl, { onCenterMove, cursorEl } = {}) {
    super(svgEl, wrapEl);
    this.#onCenterMove = onCenterMove ?? null;
    this.#cursorEl     = cursorEl ?? null;
    this._activeTool = "move";
    this._build();
  }

  // ── public API ────────────────────────────────────────────────────────────

  setBbox(bbox) {
    this.#bbox = bbox;
    this._renderBbox();
    this._renderAxis();
    this._updateCrosshair();
  }

  setCenter(cx, cz) {
    this.#cx = cx;
    this.#cz = cz;
    this._renderAxis();
    this._updateCrosshair();
  }

  setMode(mode) {
    this.#mode = mode;
    this._renderAxis();
  }

  fitToBbox() {
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    const w = this._wrap.clientWidth  || 400;
    const h = this._wrap.clientHeight || 400;
    const bboxW = max_x - min_x;
    const bboxH = max_z - min_z;
    if (!bboxW || !bboxH) return;
    const scale = Math.min(w / bboxW, h / bboxH) * FIT_MARGIN;
    this._scale = scale;
    this._panX  = w / 2 - ((min_x + max_x) / 2) * scale;
    this._panY  = h / 2 - ((min_z + max_z) / 2) * scale;
    this._applyViewportTransform();
  }

  resize() {
    const { w, h } = this.#svgSize();
    this._svg.setAttribute("width",  w);
    this._svg.setAttribute("height", h);
    this._svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    this._updateCrosshair();
  }

  #svgSize() {
    const subbar = this._wrap.querySelector(".canvas-subbar");
    const w = this._wrap.clientWidth  || 400;
    const h = (this._wrap.clientHeight || 400) - (subbar?.offsetHeight ?? 0);
    return { w, h };
  }

  // ── CanvasBase hooks ──────────────────────────────────────────────────────

  _onViewportChanged() {
    this._updateCrosshair();
  }

  _onToolMousedown(e, svgPt) {
    if (!this.#bbox) return;
    const rect  = this._svg.getBoundingClientRect();
    const sx    = this.#cx * this._scale + this._panX;
    const sy    = this.#cz * this._scale + this._panY;
    const dx    = (e.clientX - rect.left) - sx;
    const dy    = (e.clientY - rect.top)  - sy;
    if (Math.sqrt(dx * dx + dy * dy) <= HIT_RADIUS) {
      this.#draggingCenter = true;
      this._activeTool = "center-drag";
      this._svg.style.cursor = "grabbing";
    }
  }

  _onPointerMove(e, svgPt) {
    if (this.#draggingCenter) {
      const cx = Math.round(svgPt.x);
      const cz = Math.round(svgPt.y);
      this.#cx = cx;
      this.#cz = cz;
      this._renderAxis();
      this._updateCrosshair();
      this.#onCenterMove?.(cx, cz);
    } else if (this.#bbox) {
      // Show grab cursor when hovering near the center dot
      const rect = this._svg.getBoundingClientRect();
      const sx = this.#cx * this._scale + this._panX;
      const sy = this.#cz * this._scale + this._panY;
      const dx = (e.clientX - rect.left) - sx;
      const dy = (e.clientY - rect.top)  - sy;
      this._svg.style.cursor = Math.sqrt(dx * dx + dy * dy) <= HIT_RADIUS ? "grab" : "";
    }
    if (this.#cursorEl) {
      this.#cursorEl.textContent = `X ${Math.round(svgPt.x)}  Z ${Math.round(svgPt.y)}`;
    }
  }

  _onMouseleave() {
    if (this.#cursorEl) this.#cursorEl.textContent = "";
  }

  _onToolMouseup() {
    if (this.#draggingCenter) {
      this.#draggingCenter = false;
      this._activeTool = "move";
      this._svg.style.cursor = "";
    }
  }

  // ── private rendering ─────────────────────────────────────────────────────

  _build() {
    const { w, h } = this.#svgSize();
    this._svg.setAttribute("width",  w);
    this._svg.setAttribute("height", h);
    this._svg.setAttribute("viewBox", `0 0 ${w} ${h}`);

    this._viewportG = makeEl("g", { id: "sk-setup-viewport" });
    this.#bboxLayer = makeEl("g", { id: "sk-setup-bbox" });
    this.#axisLayer = makeEl("g", { id: "sk-setup-axis" });
    this._viewportG.appendChild(this.#bboxLayer);
    this._viewportG.appendChild(this.#axisLayer);
    this._svg.appendChild(this._viewportG);

    // Crosshair — screen-space group, repositioned in _updateCrosshair.
    // Must be built with makeEl (not innerHTML) to get the SVG namespace.
    this.#crosshair = makeEl("g", { id: "sk-setup-crosshair", style: "pointer-events:none" });
    this.#crosshair.appendChild(makeEl("line", {
      x1: -CROSSHAIR_ARM, y1: 0, x2: CROSSHAIR_ARM, y2: 0,
      stroke: "var(--canvas-axis)", "stroke-width": "1.5", opacity: "0.9",
    }));
    this.#crosshair.appendChild(makeEl("line", {
      x1: 0, y1: -CROSSHAIR_ARM, x2: 0, y2: CROSSHAIR_ARM,
      stroke: "var(--canvas-axis)", "stroke-width": "1.5", opacity: "0.9",
    }));
    this.#crosshair.appendChild(makeEl("circle", {
      cx: 0, cy: 0, r: CROSSHAIR_R,
      fill: "var(--canvas-axis)", stroke: "var(--bg-deep)", "stroke-width": "1.5",
    }));
    this._svg.appendChild(this.#crosshair);
    this.#crosshair.setAttribute("display", "none");

    this._applyViewportTransform();
  }

  _renderBbox() {
    while (this.#bboxLayer.firstChild) this.#bboxLayer.removeChild(this.#bboxLayer.firstChild);
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    // Faint fill for the map area
    this.#bboxLayer.appendChild(makeEl("rect", {
      x: min_x, y: min_z, width: max_x - min_x, height: max_z - min_z,
      fill: "var(--bg-selected)", "fill-opacity": "0.18",
      stroke: "var(--border)", "stroke-width": "1",
      "vector-effect": "non-scaling-stroke",
    }));
  }

  _renderAxis() {
    while (this.#axisLayer.firstChild) this.#axisLayer.removeChild(this.#axisLayer.firstChild);
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    const cx = this.#cx, cz = this.#cz;
    const attrs = {
      stroke: "var(--canvas-axis)", "stroke-width": "1",
      "stroke-dasharray": "6 4", opacity: "0.75",
      "vector-effect": "non-scaling-stroke",
    };

    const addLine = (x1, y1, x2, y2) =>
      this.#axisLayer.appendChild(makeEl("line", { x1, y1, x2, y2, ...attrs }));

    switch (this.#mode) {
      case "mirror_x":
        addLine(cx, min_z, cx, max_z);
        break;
      case "mirror_z":
        addLine(min_x, cz, max_x, cz);
        break;
      case "rot_180":
      case "rot_90":
        addLine(cx, min_z, cx, max_z);
        addLine(min_x, cz, max_x, cz);
        break;
    }
  }

  _updateCrosshair() {
    if (!this.#crosshair) return;
    if (!this.#bbox) { this.#crosshair.setAttribute("display", "none"); return; }
    const sx = this.#cx * this._scale + this._panX;
    const sy = this.#cz * this._scale + this._panY;
    this.#crosshair.setAttribute("display", "");
    this.#crosshair.setAttribute("transform", `translate(${sx.toFixed(1)}, ${sy.toFixed(1)})`);
  }
}
