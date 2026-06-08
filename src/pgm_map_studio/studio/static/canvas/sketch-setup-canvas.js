/**
 * SketchSetupCanvas — fixed-fit display of the map bounding box, axis lines,
 * and a draggable center-point handle. No pan, zoom, or move tool.
 *
 * The viewport is recomputed automatically whenever setBbox() or resize() is
 * called so the bbox always fills FIT_MARGIN of the available div space.
 *
 * Public API:
 *   setBbox(bbox)         set/change the bounding box (triggers auto-fit)
 *   setCenter(cx, cz)     programmatic center update (no fit)
 *   setMode(mode)         mirror mode for axis lines
 *   resize()              call when the wrapper div changes size
 */

import { svgEl as makeEl } from "./transform.js";

const CROSSHAIR_R   = 6;    // screen-px radius of center dot
const CROSSHAIR_ARM = 16;   // screen-px arm length
const HIT_RADIUS    = 20;   // screen-px drag-target radius around center
const FIT_MARGIN    = 0.82; // fraction of div used by the bbox

export class SketchSetupCanvas {
  #svg;
  #wrap;

  #bbox = null;
  #cx   = 0;
  #cz   = 0;
  #mode = "rot_180";

  // auto-fit transform — recomputed from bbox + div size, never user-set
  #scale = 1;
  #panX  = 0;
  #panY  = 0;

  #viewportG = null;
  #bboxLayer  = null;
  #chunkLayer = null;
  #axisLayer  = null;
  #crosshair  = null;

  #dragging     = false;
  #onCenterMove = null;
  #cursorEl     = null;

  constructor(svgEl, wrapEl, { onCenterMove, cursorEl } = {}) {
    this.#svg         = svgEl;
    this.#wrap        = wrapEl;
    this.#onCenterMove = onCenterMove ?? null;
    this.#cursorEl    = cursorEl ?? null;
    this.#build();
  }

  // ── public API ─────────────────────────────────────────────────────────────

  setBbox(bbox) {
    this.#bbox = bbox;
    this.#fit();
    this.#renderBbox();
    this.#renderChunkGrid();
    this.#renderAxis();
    this.#updateCrosshair();
  }

  setCenter(cx, cz) {
    this.#cx = cx;
    this.#cz = cz;
    this.#renderAxis();
    this.#updateCrosshair();
  }

  setMode(mode) {
    this.#mode = mode;
    this.#renderAxis();
  }

  resize() {
    const { w, h } = this.#size();
    this.#svg.setAttribute("width",   w);
    this.#svg.setAttribute("height",  h);
    this.#svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    this.#fit();
    this.#renderAxis();
    this.#updateCrosshair();
  }

  // ── private ────────────────────────────────────────────────────────────────

  #size() {
    const subbar = this.#wrap.querySelector(".canvas-subbar");
    const w = this.#wrap.clientWidth  || 400;
    const h = (this.#wrap.clientHeight || 400) - (subbar?.offsetHeight ?? 0);
    return { w, h };
  }

  #fit() {
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    const { w, h } = this.#size();
    const bw = max_x - min_x, bh = max_z - min_z;
    if (!bw || !bh) return;
    this.#scale = Math.min(w / bw, h / bh) * FIT_MARGIN;
    this.#panX  = w / 2 - ((min_x + max_x) / 2) * this.#scale;
    this.#panY  = h / 2 - ((min_z + max_z) / 2) * this.#scale;
    this.#viewportG.setAttribute("transform",
      `matrix(${this.#scale},0,0,${this.#scale},${this.#panX},${this.#panY})`);
  }

  #toWorld(sx, sy) {
    return { x: (sx - this.#panX) / this.#scale, z: (sy - this.#panY) / this.#scale };
  }

  #toScreen(wx, wz) {
    return { x: wx * this.#scale + this.#panX, y: wz * this.#scale + this.#panY };
  }

  #hitsCrosshair(clientX, clientY) {
    const rect = this.#svg.getBoundingClientRect();
    const sp   = this.#toScreen(this.#cx, this.#cz);
    const dx   = (clientX - rect.left) - sp.x;
    const dy   = (clientY - rect.top)  - sp.y;
    return Math.sqrt(dx * dx + dy * dy) <= HIT_RADIUS;
  }

  #build() {
    const { w, h } = this.#size();
    this.#svg.setAttribute("width",   w);
    this.#svg.setAttribute("height",  h);
    this.#svg.setAttribute("viewBox", `0 0 ${w} ${h}`);

    this.#viewportG  = makeEl("g", { id: "sk-setup-viewport" });
    this.#bboxLayer  = makeEl("g", { id: "sk-setup-bbox" });
    this.#chunkLayer = makeEl("g", { id: "sk-setup-chunks" });
    this.#axisLayer  = makeEl("g", { id: "sk-setup-axis" });
    this.#viewportG.appendChild(this.#bboxLayer);
    this.#viewportG.appendChild(this.#chunkLayer);
    this.#viewportG.appendChild(this.#axisLayer);
    this.#svg.appendChild(this.#viewportG);

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
    this.#svg.appendChild(this.#crosshair);
    this.#crosshair.setAttribute("display", "none");

    this.#svg.addEventListener("mousedown", (e) => {
      if (e.button !== 0 || !this.#bbox) return;
      if (this.#hitsCrosshair(e.clientX, e.clientY)) {
        this.#dragging = true;
        this.#svg.style.cursor = "grabbing";
        e.preventDefault();
      }
    });

    document.addEventListener("mousemove", (e) => {
      if (this.#dragging) {
        const rect = this.#svg.getBoundingClientRect();
        const w    = this.#toWorld(e.clientX - rect.left, e.clientY - rect.top);
        const cx   = Math.round(w.x);
        const cz   = Math.round(w.z);
        this.#cx   = cx;
        this.#cz   = cz;
        this.#renderAxis();
        this.#updateCrosshair();
        this.#onCenterMove?.(cx, cz);
        if (this.#cursorEl) this.#cursorEl.textContent = `X ${cx}  Z ${cz}`;
      } else if (this.#bbox) {
        this.#svg.style.cursor = this.#hitsCrosshair(e.clientX, e.clientY) ? "grab" : "";
      }
    });

    document.addEventListener("mouseup", (e) => {
      if (e.button !== 0 || !this.#dragging) return;
      this.#dragging = false;
      this.#svg.style.cursor = "";
    });

    this.#svg.addEventListener("mouseleave", () => {
      if (!this.#dragging && this.#cursorEl) this.#cursorEl.textContent = "";
    });
  }

  #renderBbox() {
    while (this.#bboxLayer.firstChild) this.#bboxLayer.removeChild(this.#bboxLayer.firstChild);
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    this.#bboxLayer.appendChild(makeEl("rect", {
      x: min_x, y: min_z, width: max_x - min_x, height: max_z - min_z,
      fill: "var(--bg-selected)", "fill-opacity": "0.18",
      stroke: "var(--border)", "stroke-width": "1",
      "vector-effect": "non-scaling-stroke",
    }));
  }

  #renderChunkGrid() {
    while (this.#chunkLayer.firstChild) this.#chunkLayer.removeChild(this.#chunkLayer.firstChild);
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    const attrs = {
      stroke: "var(--canvas-chunk)", "stroke-width": "1",
      "stroke-dasharray": "3 3", opacity: "1",
      "vector-effect": "non-scaling-stroke",
    };
    const line = (x1, y1, x2, y2) =>
      this.#chunkLayer.appendChild(makeEl("line", { x1, y1, x2, y2, ...attrs }));

    const startX = Math.ceil(min_x / 16) * 16;
    for (let x = startX; x <= max_x; x += 16) {
      line(x, min_z, x, max_z);
    }
    const startZ = Math.ceil(min_z / 16) * 16;
    for (let z = startZ; z <= max_z; z += 16) {
      line(min_x, z, max_x, z);
    }
  }

  #renderAxis() {
    while (this.#axisLayer.firstChild) this.#axisLayer.removeChild(this.#axisLayer.firstChild);
    if (!this.#bbox) return;
    const { min_x, max_x, min_z, max_z } = this.#bbox;
    const cx = this.#cx, cz = this.#cz;
    const attrs = {
      stroke: "var(--canvas-axis)", "stroke-width": "1",
      "stroke-dasharray": "6 4", opacity: "0.75",
      "vector-effect": "non-scaling-stroke",
    };
    const line = (x1, y1, x2, y2) =>
      this.#axisLayer.appendChild(makeEl("line", { x1, y1, x2, y2, ...attrs }));

    switch (this.#mode) {
      case "mirror_x": line(cx, min_z, cx, max_z); break;
      case "mirror_z": line(min_x, cz, max_x, cz); break;
      default:
        line(cx, min_z, cx, max_z);
        line(min_x, cz, max_x, cz);
    }
  }

  #updateCrosshair() {
    if (!this.#crosshair) return;
    if (!this.#bbox) { this.#crosshair.setAttribute("display", "none"); return; }
    const sp = this.#toScreen(this.#cx, this.#cz);
    this.#crosshair.setAttribute("display", "");
    this.#crosshair.setAttribute("transform", `translate(${sp.x.toFixed(1)},${sp.y.toFixed(1)})`);
  }
}
