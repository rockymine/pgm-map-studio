/**
 * BuildRegionsActivity — workspace for the Build Regions activity.
 *
 * Step 1: Max build height — side-view canvas with draggable height line.
 * Step 2: Build area declaration — top-down EditorCanvas, full draw toolbar,
 *         region tree (build category), region inspector with CRUD.
 */

import { SideviewCanvas }    from "../canvas/sideview-canvas.js";
import { EditorCanvas }      from "../canvas/editor-canvas.js";
import { BuildRegionsPanel } from "../panels/build-regions-panel.js";
import { RegionsPanel }      from "../panels/regions-panel.js";
import { RegionInspector }   from "../panels/region-inspector.js";
import { RegionRegistry }    from "../region/region-registry.js";
import { ToolManager }                        from "../shared/tool-manager.js";
import { showToast }                          from "../shared/ui-helpers.js";
import { normalizeIslands, drawResultToPayload } from "../shared/canvas-helpers.js";
import * as api                               from "../api.js";

export class BuildRegionsActivity {
  #el             = null;
  #mapName        = null;
  #step           = 1;
  #buildRegionFirstLoad = true;

  // Build height
  #sideviewCanvas = null;
  #panel          = null;
  #axis           = "z";

  // Build region
  #editorCanvas = null;
  #regionsPanel = null;
  #inspector    = null;
  #registry     = null;
  #toolMgr      = null;
  #coordsEl     = null;
  #zoomEl       = null;

  constructor({ onStatusChange } = {}) {
    this.#el = document.getElementById("br-workspace");

    // ── Build height setup ─────────────────────────────────────────────────
    this.#panel = new BuildRegionsPanel({
      onStatusChange,
      onHeightInput: (y) => this.#sideviewCanvas?.setBuildHeight(y),
      onAxisChange:  (axis) => this.#loadAxis(axis),
    });

    const canvasEl = document.getElementById("br-sideview-canvas");
    this.#sideviewCanvas = new SideviewCanvas(canvasEl, {
      onHeightChange: (y) => this.#panel.setHeightFromCanvas(y),
    });

    // ── Step nav ───────────────────────────────────────────────────────────
    document.getElementById("br-next-btn")?.addEventListener("click", () => this.#goNext());
    document.getElementById("br-prev-btn")?.addEventListener("click", () => this.#goBack());

    // ── Build region setup ─────────────────────────────────────────────────
    this.#coordsEl = document.getElementById("br-cursor-coords");
    this.#zoomEl   = document.getElementById("br-zoom-level");

    this.#registry = new RegionRegistry({
      onSelectionChange: (node, selectedIds) => {
        this.#editorCanvas?.setSelectedRegions(selectedIds);
        this.#regionsPanel?.setSelected(node?.id ?? null, selectedIds);
        if (node) {
          this.#editorCanvas?.showAnchors(node);
          this.#inspector?.show(node);
        } else {
          this.#editorCanvas?.clearAnchors();
          this.#inspector?.clear();
        }
      },
    });

    this.#regionsPanel = new RegionsPanel(
      document.getElementById("br-region-list"),
      { onSelect: (node) => this.#registry.select(node.id) },
    );

    this.#inspector = new RegionInspector(
      document.getElementById("br-region-detail"),
      {
        onSelect: (node) => this.#registry.select(node.id),
        onDelete: async (node) => {
          if (!this.#mapName) return;
          try {
            await api.deleteRegion(this.#mapName, node.id);
            this.#registry.deselect();
            this.#inspector.clear();
            await this.#reloadBuildRegion(this.#mapName);
            showToast("Region deleted", "success");
          } catch (err) {
            showToast(`Delete failed: ${err.message}`, "error");
          }
        },
      },
    );

    this.#initBuildRegionCanvas();
  }

  activate({ mapName } = {}) {
    this.#el.hidden = false;
    if (mapName && mapName !== this.#mapName) {
      this.#mapName = mapName;
      this.#panel.load(mapName);
      this.#loadAxis(this.#axis);
      this.#setStep(1);
    }
  }

  deactivate() { this.#el.hidden = true; }

  resize() {
    this.#sideviewCanvas?.resize();
    this.#editorCanvas?.resize();
  }

  // ── Step navigation ────────────────────────────────────────────────────────

  #setStep(n) {
    this.#step = n;

    this.#el.querySelectorAll(".br-step-panel[data-step]").forEach(el => {
      el.hidden = parseInt(el.dataset.step, 10) !== n;
    });

    const step1Canvas = document.getElementById("br-canvas-step1");
    const step2Canvas = document.getElementById("br-canvas-step2");
    if (step1Canvas) step1Canvas.hidden = n !== 1;
    if (step2Canvas) step2Canvas.hidden = n !== 2;

    const rightHandle = document.getElementById("br-right-handle");
    const rightPanel  = document.getElementById("br-right");
    if (rightHandle) rightHandle.hidden = n !== 2;
    if (rightPanel)  rightPanel.hidden  = n !== 2;

    const prevBtn = document.getElementById("br-prev-btn");
    const nextBtn = document.getElementById("br-next-btn");
    if (prevBtn) prevBtn.hidden = n === 1;
    if (nextBtn) nextBtn.hidden = n === 2;

    if (n === 1) this.#buildRegionFirstLoad = true;

    if (n === 2 && this.#mapName) {
      this.#reloadBuildRegion(this.#mapName);
      requestAnimationFrame(() => this.#editorCanvas?.resize());
    }
  }

  #goNext() { if (this.#step < 2) this.#setStep(this.#step + 1); }
  #goBack() { if (this.#step > 1) this.#setStep(this.#step - 1); }

  // ── Build region canvas init ───────────────────────────────────────────────

  #initBuildRegionCanvas() {
    const svgEl  = document.getElementById("br-map-svg");
    const wrapEl = document.getElementById("br-svg-area");
    if (!svgEl || !wrapEl) return;

    this.#editorCanvas = new EditorCanvas(svgEl, wrapEl, {
      onCoords: (x, z) => {
        if (this.#coordsEl)
          this.#coordsEl.textContent = x !== null ? `X ${x}  Z ${z}` : "";
      },
      onZoom: (scale) => {
        if (this.#zoomEl)
          this.#zoomEl.textContent = `${Math.round(scale * 100)}%`;
      },
      onCanvasClick: (node) => {
        if (node) this.#registry.select(node.id);
        else      this.#registry.deselect();
      },
      onRegionDraw: async (drawResult) => {
        if (!this.#mapName) return;
        await this.#createRegionFromDraw(drawResult);
      },
    });

    this.#toolMgr = new ToolManager(this.#editorCanvas, {
      move:      document.getElementById("br-tool-move"),
      select:    document.getElementById("br-tool-select"),
      rectangle: document.getElementById("br-tool-rectangle"),
      cuboid:    document.getElementById("br-tool-cuboid"),
      cylinder:  document.getElementById("br-tool-cylinder"),
      circle:    document.getElementById("br-tool-circle"),
      point:     document.getElementById("br-tool-point"),
    });

    const toolBtns = [
      ["br-tool-move",      "move"],
      ["br-tool-select",    "select"],
      ["br-tool-rectangle", "rectangle"],
      ["br-tool-cuboid",    "cuboid"],
      ["br-tool-cylinder",  "cylinder"],
      ["br-tool-circle",    "circle"],
      ["br-tool-point",     "point"],
    ];
    for (const [id, tool] of toolBtns) {
      document.getElementById(id)
        ?.addEventListener("click", () => this.#toolMgr.setTool(tool));
    }
    this.#toolMgr.setTool("move");

    this.#editorCanvas.connectBlocksToggle(
      document.getElementById("br2-toggle-blocks"),
      document.getElementById("br2-blocks-label"),
      () => api.fetchTopSurface(this.#mapName),
    );

    document.addEventListener("keydown", (e) => {
      if (this.#el.hidden || this.#step !== 2) return;
      if (e.target.matches("input,select,textarea")) return;
      const map = {
        m: "move", M: "move", s: "select", S: "select",
        r: "rectangle", R: "rectangle", c: "cuboid", C: "cuboid",
        y: "cylinder", Y: "cylinder", o: "circle", O: "circle",
        p: "point", P: "point", Escape: "move",
      };
      if (map[e.key]) this.#toolMgr.setTool(map[e.key]);
    });
  }

  // ── Build region data loading ──────────────────────────────────────────────

  #registerNodes(nodes) {
    for (const node of nodes) {
      if (node.id) this.#registry.register(node, null);
      if (node.children?.length) this.#registerNodes(node.children);
    }
  }

  async #reloadBuildRegion(mapName) {
    this.#registry.clear();
    this.#regionsPanel.build([]);
    this.#inspector.clear();

    try {
      const [treeData, islands] = await Promise.all([
        api.fetchRegionsTree(mapName),
        api.fetchIslands(mapName).catch(() => null),
      ]);

      const buildGroup = treeData.groups.find(g => g.name === "build");
      const groups     = buildGroup ? [buildGroup] : [];
      this.#editorCanvas.render(
        {
          bounding_box: treeData.bounding_box,
          islands: normalizeIslands(islands ?? []),
        },
        groups,
      );

      for (const group of groups) {
        this.#registerNodes(group.regions);
      }

      this.#regionsPanel.build(groups);
      if (this.#buildRegionFirstLoad) {
        this.#editorCanvas.autoLoadBlocks();
        this.#buildRegionFirstLoad = false;
      } else {
        this.#editorCanvas.reloadBlocks();
      }
    } catch (err) {
      console.error("BuildRegionsActivity: build region load failed:", err);
    }
  }

  // ── Region CRUD ────────────────────────────────────────────────────────────

  async #createRegionFromDraw(drawResult) {
    this.#toolMgr.setTool("move");
    const payload = drawResultToPayload(drawResult, "build");

    try {
      const result = await api.createRegion(this.#mapName, payload);
      await this.#reloadBuildRegion(this.#mapName);
      if (result.id) this.#registry.select(result.id);
      showToast("Region created", "success");
    } catch (err) {
      showToast(`Create failed: ${err.message}`, "error");
    }
  }

  // ── Build height ───────────────────────────────────────────────────────────

  async #loadAxis(axis) {
    this.#axis = axis;
    if (!this.#mapName) return;
    this.#sideviewCanvas.setBuildHeight(this.#panel.getHeight());
    try {
      const data = await api.fetchSegments(this.#mapName, axis);
      this.#sideviewCanvas.setData(data);
      this.#sideviewCanvas.setBuildHeight(this.#panel.getHeight());
    } catch (err) {
      console.warn("BuildRegionsActivity: could not load segments:", err.message);
      this.#sideviewCanvas.setData(null);
    }
  }
}

