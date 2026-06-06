/**
 * sketch-layout-activity.js — Layout activity coordinator.
 *
 * Owns the island computation loop: any shape change triggers a full
 * recompute via computeIslands + assignShapesToIslands, which then drives
 * both the canvas and the panel. Saves to the API on every settled change
 * (debounced 800 ms).
 *
 * Receives setup values (bbox, center, mirror mode) from sketch-main.js so
 * the mirror preview stays in sync when the user changes Setup.
 */

import * as api from "../api.js";
import { showToast } from "../shared/ui-helpers.js";
import { SketchLayoutCanvas } from "../canvas/sketch-layout-canvas.js";
import { SketchLayoutPanel }  from "../panels/sketch-layout-panel.js";
import { computeIslands, assignShapesToIslands, computeMirrorPreview, restoreIslandMeta } from "../sketch/geometry.js";

let _nextId = 1;
function genId() { return `s${Date.now()}_${_nextId++}`; }

export class SketchLayoutActivity {
  #el       = null;
  #sketchId = null;

  #canvas = null;
  #panel  = null;
  #toolbarWired = false;

  // state
  #shapes  = [];    // [shape, ...]  (ordered; mutable)
  #islands = [];    // latest computeIslands result
  #setup   = { bbox: null, center: { cx: 0, cz: 0 }, mirror_mode: "rot_180" };

  #mirrorVisible  = true;
  #shapesVisible  = false;
  #selectedId     = null;   // currently selected shape id (tracked for inspector refresh)

  // save debounce
  #saveTimer = null;

  // external callbacks
  #onStatusChange = null;
  #onExportReady  = null;
  #onChanged      = null;

  constructor({ onStatusChange, onExportReady, onChanged } = {}) {
    this.#onStatusChange = onStatusChange ?? null;
    this.#onExportReady  = onExportReady  ?? null;
    this.#onChanged      = onChanged      ?? null;

    this.#el = document.getElementById("sk-layout-workspace");

    const svgEl_      = this.#el.querySelector("#sk-layout-svg");
    const wrapEl      = this.#el.querySelector("#sk-layout-canvas-wrap");
    const cursorEl    = this.#el.querySelector("#sk-layout-cursor");
    const zoomEl      = this.#el.querySelector("#sk-layout-zoom");
    const treeEl      = this.#el.querySelector("#sk-layout-tree");
    const inspectorEl = this.#el.querySelector("#sk-layout-inspector");

    this.#canvas = new SketchLayoutCanvas(svgEl_, wrapEl, {
      cursorEl, zoomEl,
      onShapeCreated:  s  => this.#onShapeCreated(s),
      onShapeUpdated:  s  => this.#onShapeUpdated(s),
      onShapeSelected: id => this.#onShapeSelected(id),
      onShapeDeleted:  id => this.#onShapeDeleted(id),
    });

    this.#panel = new SketchLayoutPanel(treeEl, inspectorEl, {
      onShapeDelete:         id  => this.#onShapeDeleted(id),
      onShapeOpToggle:       id  => this.#toggleOp(id),
      onShapeOverrideToggle: id  => this.#toggleOverride(id),
      onIslandMirrorsToggle: id  => this.#toggleMirrors(id),
      onIslandRename:        (id, name) => this.#renameIsland(id, name),
      onShapeSelect:         id  => { this.#canvas.selectShape(id); this.#panel.setSelected(id); },
      onSimplify:            (id, verts) => this.#onSimplify(id, verts),
    });
  }

  activate({ sketchId } = {}) {
    this.#sketchId = sketchId;
    this.#el.hidden = false;
    this.#canvas?.resize();  // force correct SVG size before async load
    if (!this.#toolbarWired) { this.#wireToolbar(this.#el); this.#toolbarWired = true; }
    this.#load();
  }

  deactivate() {
    clearTimeout(this.#saveTimer);
    this.#el.hidden = true;
  }

  resize() { this.#canvas?.resize(); }

  /** Called by sketch-main when Setup values change. */
  updateSetup(setup) {
    this.#setup = { ...this.#setup, ...setup };
    if (setup.bbox) {
      this.#canvas?.setBbox(setup.bbox);
      this.#canvas?.fitToBbox();
    }
    if (setup.center !== undefined) {
      this.#canvas?.setCenter(setup.center.cx ?? 0, setup.center.cz ?? 0);
    }
    if (setup.mirror_mode !== undefined) {
      this.#canvas?.setMode(setup.mirror_mode);
    }
    this.#refreshMirrorPreview();
  }

  // ── Load ──────────────────────────────────────────────────────────────────────

  async #load() {
    try {
      const data   = await api.fetchSketch(this.#sketchId);
      const setup  = data.setup ?? null;
      const layout = data.layout ?? null;

      if (setup) {
        this.#setup = {
          bbox:        setup.bbox        ?? null,
          center:      setup.center      ?? { cx: 0, cz: 0 },
          mirror_mode: setup.mirror_mode ?? "rot_180",
        };
        if (setup.bbox)        this.#canvas.setBbox(setup.bbox);
        if (setup.center)      this.#canvas.setCenter(setup.center.cx ?? 0, setup.center.cz ?? 0);
        if (setup.mirror_mode) this.#canvas.setMode(setup.mirror_mode);
        this.#canvas.fitToBbox();
      } else {
        // No saved setup — mirror the Square defaults from sketch-setup-panel
        const defaultBbox = { min_x: -256, max_x: 256, min_z: -256, max_z: 256 };
        this.#setup = { bbox: defaultBbox, center: { cx: 0, cz: 0 }, mirror_mode: "rot_180" };
        this.#canvas.setBbox(defaultBbox);
        this.#canvas.setCenter(0, 0);
        this.#canvas.setMode("rot_180");
        this.#canvas.fitToBbox();
      }

      if (layout?.shapes) {
        this.#shapes = layout.shapes.map(s => ({ ...s }));

        // Compute islands fresh (no prev) to get real exterior geometry + shapeIds.
        const { islands, addUnion, afterSub, overrideAddUnion } = computeIslands(this.#shapes, []);
        assignShapesToIslands(this.#shapes, islands, addUnion, overrideAddUnion, afterSub);

        // Restore saved name/color/mirrors by matching on shapeId set overlap.
        const savedMeta = layout.islands ?? [];
        restoreIslandMeta(islands, savedMeta, ["id", "name", "mirrors"]);

        this.#islands = islands;
        this.#canvas.setIslands(islands.map(isl => ({
          exterior: isl.exterior, holes: isl.holes,
        })));
        this.#panel.setShapes(this.#shapes);
        this.#panel.setIslands(islands);
        this.#refreshMirrorPreview();
        this.#updateStatus();
        if (typeof window !== "undefined") {
          window.lucide?.createIcons({ attrs: { "stroke-width": "1.5", width: "14", height: "14" } });
        }

        for (const shape of this.#shapes) this.#canvas.addShape(shape);
      }
    } catch (err) {
      showToast(`Layout load failed: ${err.message}`, "error");
    }
  }

  // ── Toolbar wiring ────────────────────────────────────────────────────────────

  #setActiveTool(tool) {
    this.#canvas.setActiveTool(tool);
    if (tool !== "select" && this.#selectedId !== null) {
      this.#selectedId = null;
      this.#canvas.selectShape(null);
      this.#panel.setSelected(null);
    }
    const subbar = this.#el.querySelector("#sk-layout-canvas-wrap .canvas-subbar");
    if (!subbar) return;
    for (const btn of subbar.querySelectorAll("[data-tool]")) {
      btn.classList.toggle("draw-tool-btn--active", btn.dataset.tool === tool);
    }
  }

  #wireToolbar(el) {
    const subbar = el.querySelector("#sk-layout-canvas-wrap .canvas-subbar");

    const toolBtns = subbar?.querySelectorAll("[data-tool]") ?? [];
    for (const btn of toolBtns) {
      btn.addEventListener("click", () => {
        this.#setActiveTool(btn.dataset.tool || null);
      });
    }

    const opBtns = subbar?.querySelectorAll("[data-op]") ?? [];
    for (const btn of opBtns) {
      btn.addEventListener("click", () => {
        const op = btn.dataset.op;
        this.#canvas.setOperation(op);
        opBtns.forEach(b => {
          b.classList.remove("draw-tool-btn--op-add", "draw-tool-btn--op-sub");
          if (b === btn) b.classList.add(op === "add" ? "draw-tool-btn--op-add" : "draw-tool-btn--op-sub");
        });
      });
    }

    el.querySelector("#sk-layout-toggle-shapes")?.addEventListener("change", (e) => {
      this.#shapesVisible = e.target.checked;
      this.#canvas.setShapesVisible(this.#shapesVisible);
    });

    el.querySelector("#sk-layout-toggle-mirror")?.addEventListener("change", (e) => {
      this.#mirrorVisible = e.target.checked;
      this.#canvas.setMirrorVisible(this.#mirrorVisible);
    });
  }

  // ── Shape lifecycle ───────────────────────────────────────────────────────────

  #onShapeCreated(partial) {
    const shape = { ...partial, id: genId(), override: false };
    this.#shapes.push(shape);
    this.#canvas.addShape(shape);
    this.#recompute();
    this.#scheduleSave();
    // Auto-select the new shape and switch to select mode
    this.#onShapeSelected(shape.id);
    this.#setActiveTool("select");
  }

  #onShapeUpdated(shape) {
    const idx = this.#shapes.findIndex(s => s.id === shape.id);
    if (idx !== -1) this.#shapes[idx] = shape;
    this.#recompute();
    if (this.#selectedId !== null) this.#panel.setSelected(this.#selectedId);
    this.#scheduleSave();
  }

  #onShapeSelected(id) {
    this.#selectedId = id;
    this.#canvas.selectShape(id);
    this.#panel.setSelected(id);
  }

  #onShapeDeleted(id) {
    this.#shapes = this.#shapes.filter(s => s.id !== id);
    this.#canvas.removeShape(id);
    this.#recompute();
    this.#scheduleSave();
    this.#selectedId = null;
    this.#panel.setSelected(null);
    this.#canvas.selectShape(null);
  }

  #toggleOp(id) {
    const shape = this.#shapes.find(s => s.id === id);
    if (!shape) return;
    shape.operation = shape.operation === "subtract" ? "add" : "subtract";
    this.#canvas.updateShape(shape);
    this.#recompute();
    this.#scheduleSave();
  }

  #toggleOverride(id) {
    const shape = this.#shapes.find(s => s.id === id);
    if (!shape) return;
    shape.override = !shape.override;
    this.#canvas.updateShape(shape);
    this.#recompute();
    this.#scheduleSave();
  }

  #toggleMirrors(id) {
    const isl = this.#islands.find(i => i.id === id);
    if (!isl) return;
    isl.mirrors = !isl.mirrors;
    this.#refreshMirrorPreview();
    this.#scheduleSave();
  }

  #renameIsland(id, name) {
    const isl = this.#islands.find(i => i.id === id);
    if (isl) isl.name = name;
    this.#scheduleSave();
  }

  #onSimplify(id, vertices) {
    const shape = this.#shapes.find(s => s.id === id);
    if (!shape) return;
    shape.vertices = vertices;
    this.#canvas.updateShape(shape);
    this.#recompute();
    if (this.#selectedId !== null) this.#panel.setSelected(this.#selectedId);
    this.#scheduleSave();
  }

  // ── Island recompute ──────────────────────────────────────────────────────────

  #recompute(prevIslands = null) {
    const { islands, addUnion, afterSub, overrideAddUnion } = computeIslands(
      this.#shapes, prevIslands ?? this.#islands,
    );
    assignShapesToIslands(this.#shapes, islands, addUnion, overrideAddUnion, afterSub);
    this.#islands = islands;

    this.#canvas.setIslands(islands.map(isl => ({
      exterior: isl.exterior,
      holes:    isl.holes,
    })));

    this.#panel.setShapes(this.#shapes);
    this.#panel.setIslands(islands);

    this.#refreshMirrorPreview();
    this.#updateStatus();
    if (typeof window !== "undefined") {
      window.lucide?.createIcons({ attrs: { "stroke-width": "1.5", width: "14", height: "14" } });
    }
  }

  #refreshMirrorPreview() {
    if (!this.#mirrorVisible || !this.#setup.mirror_mode || !this.#setup.center) {
      this.#canvas.setMirrorPolygons([]);
      return;
    }
    const { cx = 0, cz = 0 } = this.#setup.center;
    const preview = computeMirrorPreview(this.#islands, this.#setup.mirror_mode, cx, cz);
    this.#canvas.setMirrorPolygons(preview);
  }

  // ── Status dot ────────────────────────────────────────────────────────────────

  #updateStatus() {
    const valid = this.#islands.length >= 1;
    this.#onStatusChange?.(valid ? "green" : "yellow");
    this.#onExportReady?.(this.#islands.length >= 2);
  }

  // ── Persistence ───────────────────────────────────────────────────────────────

  #scheduleSave() {
    clearTimeout(this.#saveTimer);
    this.#onChanged?.();
    this.#saveTimer = setTimeout(() => this.#save(), 800);
  }

  async #save() {
    if (!this.#sketchId) return;
    const islandMeta = this.#islands.map(isl => ({
      id:       isl.id,
      name:     isl.name,
      mirrors:  isl.mirrors,
      shapeIds: isl.shapeIds,
    }));
    try {
      await api.saveSketchLayout(this.#sketchId, this.#shapes, islandMeta);
    } catch (err) {
      showToast(`Layout save failed: ${err.message}`, "error");
    }
  }
}
