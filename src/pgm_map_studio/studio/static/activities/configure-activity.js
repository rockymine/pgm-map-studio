/**
 * configure-activity.js — Configure wizard embedded in the editor shell.
 *
 * 3 sequential steps:
 *   1. Scan Layer  — pick surface|y0|bedrock|base; clicking a type fetches
 *                    and renders that layer's pixel data on the canvas.
 *   2. Islands     — review detected islands; optionally exclude some.
 *   3. Symmetry    — confirm/override/reject detected symmetry.
 *
 * On "Done", calls onComplete() so the editor can switch to Overview.
 */

import { ConfigureCanvas } from "../canvas/configure-canvas.js";
import { showToast, showSystemError } from "../shared/ui-helpers.js";

const _SYMMETRY_LABELS = {
  rot_90:   "Rotate 90°",
  rot_180:  "Rotate 180°",
  mirror_x: "Mirror X (left/right)",
  mirror_z: "Mirror Z (front/back)",
};

export class ConfigureActivity {
  #el;
  #canvas;
  #mapName    = null;
  #callbacks;

  #step             = 1;
  #scanLayer        = "surface";
  #origLayer        = "surface";
  #excludeBlocks    = [];   // current block exclusion list (persisted eagerly)
  #origExcludeBlocks= [];   // snapshot at load time — for change detection
  #blockTypes       = [];   // flat array of {block_id, name, color, count}
  #excludedIds      = new Set();
  #origExcludedIds  = new Set();  // snapshot when entering step 2
  #islandsData      = [];
  #symmetryData     = null;
  #symChoice        = null;   // null | "rot_90" | … | "none"

  constructor({ onStatusChange, onComplete } = {}) {
    this.#el        = document.getElementById("cfg-workspace");
    this.#callbacks = { onStatusChange, onComplete };
    this.#canvas    = new ConfigureCanvas(
      document.getElementById("cfg-canvas"),
      document.getElementById("cfg-canvas-wrap"),
    );
    this.#wireStaticUI();
  }

  // ── Activity protocol ────────────────────────────────────────────────────

  activate({ mapName } = {}) {
    this.#el.hidden = false;
    if (mapName && mapName !== this.#mapName) {
      this.#mapName = mapName;
      this.#reset();
      this.#loadAll();
    }
    requestAnimationFrame(() => this.#canvas.resize());
  }

  deactivate() {
    this.#el.hidden = true;
    const notice = document.getElementById("cfg-topbar-notice");
    if (notice) notice.hidden = true;
  }

  resize() {
    this.#canvas.resize();
  }

  // ── Init ─────────────────────────────────────────────────────────────────

  #reset() {
    this.#scanLayer         = "surface";
    this.#origLayer         = "surface";
    this.#excludeBlocks     = [];
    this.#origExcludeBlocks = [];
    this.#blockTypes        = [];
    this.#excludedIds       = new Set();
    this.#islandsData       = [];
    this.#symmetryData      = null;
    this.#symChoice         = null;
    this.#gotoStep(1);
  }

  async #loadAll() {
    await this.#loadState();
    await Promise.all([
      this.#loadLayerPixels(this.#origLayer),
      this.#loadBlockTypes(this.#origLayer),
    ]);
    await this.#loadIslands();
    await this.#loadSymmetry();
  }

  // ── Static UI wiring (runs once in constructor) ───────────────────────────

  #wireStaticUI() {
    document.getElementById("cfg-next-btn")?.addEventListener("click", () => this.#goNext());
    document.getElementById("cfg-prev-btn")?.addEventListener("click", () => this.#goPrev());
    document.getElementById("cfg-finish-btn")?.addEventListener("click", () => this.#goNext());
    document.getElementById("cfg-center-x")?.addEventListener("input", () => this.#updateSymCanvas());
    document.getElementById("cfg-center-z")?.addEventListener("input", () => this.#updateSymCanvas());
    document.getElementById("cfg-center-reset")?.addEventListener("click", () => this.#resetCenter());

    document.getElementById("cfg-layer-list")?.querySelectorAll(".filter-chip[data-layer]").forEach(el => {
      el.addEventListener("click", () => this.#onLayerChipClick(el.dataset.layer));
    });
  }

  // ── Step navigation ───────────────────────────────────────────────────────

  #gotoStep(n) {
    this.#step = n;

    // Step bar
    this.#el.querySelectorAll(".step-item[data-step]").forEach(el => {
      const s = parseInt(el.dataset.step, 10);
      el.classList.toggle("active", s === n);
      el.classList.toggle("done",   s < n);
    });

    // Step panels
    this.#el.querySelectorAll(".cfg-step-panel[data-step]").forEach(el => {
      el.hidden = parseInt(el.dataset.step, 10) !== n;
    });

    // Nav buttons
    const prev   = document.getElementById("cfg-prev-btn");
    const next   = document.getElementById("cfg-next-btn");
    const finish = document.getElementById("cfg-finish-btn");
    if (prev)   prev.hidden   = n === 1;
    if (next)   next.hidden   = n === 3;
    if (finish) finish.hidden = n !== 3;

    // Canvas mode + per-step notice/button state
    if (n === 1) {
      this.#canvas.setMode("layer");
      this.#updateChangeWarn();
    }
    if (n === 2) {
      this.#canvas.setMode("islands");
      this.#canvas.setExcludedIds([...this.#excludedIds]);
      this.#origExcludedIds = new Set(this.#excludedIds);
      this.#updateIslandWarn();
    }
    if (n === 3) {
      this.#canvas.setMode("symmetry");
      this.#updateSymCanvas();
      this.#clearTopbarNotice();
    }

    this.#updateNextEnabled();
  }

  #updateNextEnabled() {
    const finish = document.getElementById("cfg-finish-btn");
    if (this.#step === 3 && finish) {
      finish.disabled = this.#symChoice === null;
    }
  }

  async #goNext() {
    if (this.#step === 1) {
      await this.#confirmLayer();
    } else if (this.#step === 2) {
      const btn = document.getElementById("cfg-next-btn");
      if (btn) btn.disabled = true;
      const ok = await this.#rerunSymmetry();
      if (btn) btn.disabled = false;
      if (!ok) return;
      this.#origExcludedIds = new Set(this.#excludedIds);
      this.#symChoice = null;
      await this.#loadSymmetry();
      this.#gotoStep(3);
    } else {
      await this.#finish();
    }
  }

  #goPrev() {
    if (this.#step > 1) this.#gotoStep(this.#step - 1);
  }

  // ── Step 1: Scan Layer ────────────────────────────────────────────────────

  #onLayerChipClick(layer) {
    if (!layer || !this.#mapName) return;
    this.#scanLayer    = layer;
    this.#excludeBlocks = [];   // exclusions are per-layer; reset when previewing a new layer

    this.#el.querySelectorAll("#cfg-layer-list .filter-chip[data-layer]").forEach(el => {
      el.classList.toggle("filter-chip--active", el.dataset.layer === layer);
    });

    this.#updateChangeWarn();
    this.#loadLayerPixels(layer);
    this.#loadBlockTypes(layer);
  }

  #updateChangeWarn() {
    const layerChanged  = this.#scanLayer !== this.#origLayer;
    const blocksChanged = !this.#setsEqual(new Set(this.#excludeBlocks), new Set(this.#origExcludeBlocks));
    const pending = layerChanged || blocksChanged;

    const notice = document.getElementById("cfg-topbar-notice");
    const noticeText = document.getElementById("cfg-topbar-notice-text");
    if (notice) {
      notice.hidden = !pending;
      if (noticeText && pending) {
        noticeText.textContent = layerChanged && blocksChanged
          ? "Layer and block exclusions changed — re-run pending"
          : layerChanged
          ? "Scan layer changed — re-run pending"
          : "Block exclusions changed — re-run pending";
      }
      if (pending && typeof lucide !== "undefined")
        lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "13", height: "13" } });
    }

    const nextBtn = document.getElementById("cfg-next-btn");
    if (nextBtn) {
      nextBtn.classList.toggle("action-btn--primary", !pending);
      nextBtn.classList.toggle("action-btn--warn",    pending);
      nextBtn.title = pending ? "Next will re-run island detection and symmetry analysis" : "";
    }
  }

  #setsEqual(a, b) {
    if (a.size !== b.size) return false;
    for (const v of a) if (!b.has(v)) return false;
    return true;
  }

  #updateIslandWarn() {
    const pending = !this.#setsEqual(this.#excludedIds, this.#origExcludedIds);
    const notice = document.getElementById("cfg-topbar-notice");
    const noticeText = document.getElementById("cfg-topbar-notice-text");
    if (notice) {
      notice.hidden = !pending;
      if (noticeText && pending)
        noticeText.textContent = "Island exclusions changed — re-run pending";
      if (pending && typeof lucide !== "undefined")
        lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "13", height: "13" } });
    }
    const nextBtn = document.getElementById("cfg-next-btn");
    if (nextBtn) {
      nextBtn.classList.toggle("action-btn--primary", !pending);
      nextBtn.classList.toggle("action-btn--warn",    pending);
      nextBtn.title = pending ? "Next will re-run symmetry analysis" : "";
    }
  }

  #clearTopbarNotice() {
    const notice = document.getElementById("cfg-topbar-notice");
    if (notice) notice.hidden = true;
    const nextBtn = document.getElementById("cfg-next-btn");
    if (nextBtn) {
      nextBtn.classList.remove("action-btn--warn");
      nextBtn.classList.add("action-btn--primary");
      nextBtn.title = "";
    }
  }

  async #confirmLayer() {
    const layerChanged  = this.#scanLayer !== this.#origLayer;
    const blocksChanged = !this.#setsEqual(new Set(this.#excludeBlocks), new Set(this.#origExcludeBlocks));

    if (layerChanged || blocksChanged) {
      const ok = await this.#rerunLayout();
      if (!ok) return;
      await this.#loadBlockTypes(this.#scanLayer);
      await this.#loadIslands();
      this.#symmetryData = null;
      this.#symChoice    = null;
      this.#excludedIds  = new Set();
    }
    // Single PATCH: persists layer choice, block exclusions, and confirmed flag in one write.
    const confirmPayload = { confirmed: true, exclude_blocks: this.#excludeBlocks };
    if (layerChanged) confirmPayload.scan_layer = this.#scanLayer;
    await fetch(`/api/configure/${this.#mapName}/scan-layer`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(confirmPayload),
    });
    this.#origLayer         = this.#scanLayer;
    this.#origExcludeBlocks = [...this.#excludeBlocks];
    this.#updateChangeWarn();
    await this.#loadSymmetry();
    this.#gotoStep(2);
  }

  // ── Block inclusion/exclusion ─────────────────────────────────────────────

  #excludeBlock(blockId) {
    if (!this.#excludeBlocks.includes(blockId)) this.#excludeBlocks.push(blockId);
    this.#renderBlockLists();
    this.#updateChangeWarn();
  }

  #includeBlock(blockId) {
    this.#excludeBlocks = this.#excludeBlocks.filter(b => b !== blockId);
    this.#renderBlockLists();
    this.#updateChangeWarn();
  }

  #renderBlockLists() {
    const blocks = Array.isArray(this.#blockTypes) ? this.#blockTypes : [];
    const excludedSet = new Set(this.#excludeBlocks);
    const included = blocks.filter(b => !excludedSet.has(b.block_id));
    const excluded = blocks.filter(b => excludedSet.has(b.block_id));

    const isBedrock = this.#scanLayer === "bedrock";
    const canExclude = !isBedrock && included.length > 1;

    const incEl = document.getElementById("cfg-block-included");
    if (incEl) {
      incEl.innerHTML = "";
      if (!included.length) {
        incEl.innerHTML = `<div class="list-empty">No blocks in layer.</div>`;
      } else {
        for (const b of included) {
          const row = document.createElement("div");
          row.className = "list-row list-row--compact";
          const removeDisabled = !canExclude ? " disabled" : "";
          row.innerHTML = `
            <span class="list-swatch" style="background:${b.color}"></span>
            <span class="list-label">${b.name}</span>
            <span class="list-tag">${b.count.toLocaleString()}</span>
            <button class="btn-remove btn-remove--hover-only" data-id="${b.block_id}"${removeDisabled}
                    title="Exclude this block type"><i data-lucide="x" style="width:12px;height:12px"></i></button>`;
          if (canExclude) {
            row.querySelector(".btn-remove").addEventListener("click", e => {
              e.stopPropagation();
              this.#excludeBlock(b.block_id);
            });
          }
          incEl.appendChild(row);
        }
      }
      if (typeof lucide !== "undefined")
        lucide.createIcons({ attrs: { "stroke-width": "2", width: "12", height: "12" } });
    }

    const excEl = document.getElementById("cfg-block-excluded");
    if (excEl) {
      excEl.innerHTML = "";
      if (!excluded.length) {
        excEl.innerHTML = `<div class="list-empty">No blocks excluded.</div>`;
      } else {
        for (const b of excluded) {
          const row = document.createElement("div");
          row.className = "list-row list-row--compact";
          row.innerHTML = `
            <span class="list-swatch" style="background:${b.color}"></span>
            <span class="list-label">${b.name}</span>
            <button class="btn-remove btn-remove--hover-only" data-id="${b.block_id}"
                    title="Re-include this block type"><i data-lucide="rotate-ccw" style="width:12px;height:12px"></i></button>`;
          row.querySelector(".btn-remove").addEventListener("click", e => {
            e.stopPropagation();
            this.#includeBlock(b.block_id);
          });
          excEl.appendChild(row);
        }
        if (typeof lucide !== "undefined")
          lucide.createIcons({ attrs: { "stroke-width": "2", width: "12", height: "12" } });
      }
    }
  }

  async #rerunLayout() {
    return new Promise(resolve => {
      const src = new EventSource(`/api/pipeline/${this.#mapName}/run?force_layout=1&force_symmetry=1`);
      src.addEventListener("done",  () => { src.close(); showToast("Pipeline complete", "success"); resolve(true); });
      src.addEventListener("error", () => { src.close(); showSystemError("Pipeline re-run failed."); resolve(false); });
    });
  }

  async #rerunSymmetry() {
    return new Promise(resolve => {
      const src = new EventSource(`/api/pipeline/${this.#mapName}/run?force_symmetry=1`);
      src.addEventListener("done",  () => {
        src.close();
        showToast("Symmetry updated", "success");
        resolve(true);
      });
      src.addEventListener("error", () => {
        src.close();
        showSystemError("Symmetry re-run failed.");
        resolve(false);
      });
    });
  }

  // ── Step 2: Islands ───────────────────────────────────────────────────────

  #renderIslandList() {
    const included = this.#islandsData.filter(i => !this.#excludedIds.has(i.id));
    const excluded = this.#islandsData.filter(i =>  this.#excludedIds.has(i.id));
    const canExclude = included.length > 1;

    const incEl = document.getElementById("cfg-island-list");
    if (incEl) {
      incEl.innerHTML = "";
      if (!included.length) {
        incEl.innerHTML = `<div class="list-empty">No islands detected.</div>`;
      } else {
        for (const island of included) {
          const row = document.createElement("div");
          row.className = "list-row list-row--compact";
          const removeDisabled = !canExclude ? " disabled" : "";
          row.innerHTML = `
            <span class="list-swatch" style="background:#6366f1"></span>
            <span class="list-label">Island ${island.id}</span>
            <span class="list-tag">${island.block_count.toLocaleString()}</span>
            <button class="btn-remove btn-remove--hover-only" data-id="${island.id}"${removeDisabled}
                    title="Exclude island"><i data-lucide="x" style="width:12px;height:12px"></i></button>`;
          if (canExclude) {
            row.querySelector(".btn-remove").addEventListener("click", e => {
              e.stopPropagation();
              this.#toggleIsland(island.id, true);
            });
          }
          incEl.appendChild(row);
        }
      }
      if (typeof lucide !== "undefined")
        lucide.createIcons({ attrs: { "stroke-width": "2", width: "12", height: "12" } });
    }

    const excEl = document.getElementById("cfg-island-excluded");
    if (excEl) {
      excEl.innerHTML = "";
      if (!excluded.length) {
        excEl.innerHTML = `<div class="list-empty">No islands excluded.</div>`;
      } else {
        for (const island of excluded) {
          const row = document.createElement("div");
          row.className = "list-row list-row--compact";
          row.innerHTML = `
            <span class="list-swatch" style="background:#6b7280"></span>
            <span class="list-label">Island ${island.id}</span>
            <span class="list-tag">${island.block_count.toLocaleString()}</span>
            <button class="btn-remove btn-remove--hover-only" data-id="${island.id}"
                    title="Re-include island"><i data-lucide="rotate-ccw" style="width:12px;height:12px"></i></button>`;
          row.querySelector(".btn-remove").addEventListener("click", e => {
            e.stopPropagation();
            this.#toggleIsland(island.id, false);
          });
          excEl.appendChild(row);
        }
        if (typeof lucide !== "undefined")
          lucide.createIcons({ attrs: { "stroke-width": "2", width: "12", height: "12" } });
      }
    }
  }

  async #toggleIsland(id, excluded) {
    await fetch(`/api/configure/${this.#mapName}/exclude-island`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ island_id: id, excluded }),
    });
    if (excluded) this.#excludedIds.add(id);
    else          this.#excludedIds.delete(id);
    this.#canvas.setExcludedIds([...this.#excludedIds]);
    this.#renderIslandList();
    this.#updateIslandWarn();
  }

  // ── Step 3: Symmetry ──────────────────────────────────────────────────────

  #renderSymPanel() {
    if (!this.#symmetryData) return;
    const modes   = this.#symmetryData.modes ?? [];
    const primary = this.#symmetryData.primary;

    // Pre-select detected primary if nothing chosen yet
    if (this.#symChoice === null && primary) {
      this.#symChoice = primary.type;
      this.#updateNextEnabled();
    }

    const modeList = document.getElementById("cfg-sym-modes");
    if (!modeList) return;
    modeList.innerHTML = "";

    const sorted = [...modes].sort((a, b) => b.confidence - a.confidence);
    for (const m of sorted) {
      const row = document.createElement("div");
      row.className = `list-row list-row--compact${this.#symChoice === m.type ? " list-row--selected" : ""}`;
      row.dataset.type = m.type;
      row.innerHTML = `
        <span class="list-label">${_SYMMETRY_LABELS[m.type] ?? m.type}</span>
        <span class="badge badge--${m.detected ? "success" : "neutral"}">${Math.round(m.confidence * 100)}%</span>
        ${m.detected ? '<span class="badge badge--dim">detected</span>' : ""}`;
      row.addEventListener("click", () => {
        this.#symChoice = m.type;
        this.#updateSymChoiceUI();
        this.#updateSymCanvas();
      });
      modeList.appendChild(row);
    }

    // "No symmetry" option
    const noneRow = document.createElement("div");
    noneRow.className = `list-row list-row--compact${this.#symChoice === "none" ? " list-row--selected" : ""}`;
    noneRow.dataset.type = "none";
    noneRow.innerHTML = `<span class="list-label">No symmetry</span>`;
    noneRow.addEventListener("click", () => {
      this.#symChoice = "none";
      this.#updateSymChoiceUI();
      this.#updateSymCanvas();
    });
    modeList.appendChild(noneRow);

    // Center values
    const cx = this.#symmetryData.center?.center_x ?? 0;
    const cz = this.#symmetryData.center?.center_z ?? 0;
    const inpX = document.getElementById("cfg-center-x");
    const inpZ = document.getElementById("cfg-center-z");
    if (inpX) inpX.value = cx;
    if (inpZ) inpZ.value = cz;

    const axisSection = document.getElementById("cfg-sym-axis-section");
    if (axisSection) axisSection.hidden = this.#symChoice === "none";

    this.#updateNextEnabled();
    if (typeof lucide !== "undefined")
      lucide.createIcons({ attrs: { "stroke-width": "1.5", width: "14", height: "14" } });
  }

  #updateSymChoiceUI() {
    document.getElementById("cfg-sym-modes")?.querySelectorAll("[data-type]").forEach(el => {
      el.classList.toggle("list-row--selected", el.dataset.type === this.#symChoice);
    });
    const axisSection = document.getElementById("cfg-sym-axis-section");
    if (axisSection) axisSection.hidden = this.#symChoice === "none";
    this.#updateNextEnabled();
  }

  #updateSymCanvas() {
    if (!this.#symmetryData) return;
    this.#canvas.setSymmetryType(this.#symChoice === "none" ? null : this.#symChoice);
    const cx = parseFloat(document.getElementById("cfg-center-x")?.value ?? 0);
    const cz = parseFloat(document.getElementById("cfg-center-z")?.value ?? 0);
    this.#canvas.setCenter(cx, cz);
  }

  #resetCenter() {
    const cx = this.#symmetryData?.center?.center_x ?? 0;
    const cz = this.#symmetryData?.center?.center_z ?? 0;
    const inpX = document.getElementById("cfg-center-x");
    const inpZ = document.getElementById("cfg-center-z");
    if (inpX) inpX.value = cx;
    if (inpZ) inpZ.value = cz;
    this.#updateSymCanvas();
  }

  // ── Finish ────────────────────────────────────────────────────────────────

  async #finish() {
    const payload = { status: this.#symChoice === "none" ? "none" : "confirmed" };
    if (this.#symChoice && this.#symChoice !== "none") payload.confirmed_type = this.#symChoice;
    const cx = parseFloat(document.getElementById("cfg-center-x")?.value ?? "");
    const cz = parseFloat(document.getElementById("cfg-center-z")?.value ?? "");
    if (!isNaN(cx)) payload.center_x = cx;
    if (!isNaN(cz)) payload.center_z = cz;

    const r = await fetch(`/api/configure/${this.#mapName}/symmetry`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (r.ok) {
      this.#callbacks.onComplete?.();
    } else {
      showSystemError("Failed to save symmetry decision.");
    }
  }

  // ── Data loading ──────────────────────────────────────────────────────────

  async #loadState() {
    try {
      const r = await fetch(`/api/configure/${this.#mapName}/state`);
      if (!r.ok) return;
      const s = await r.json();
      this.#scanLayer         = s.scan_layer;
      this.#origLayer         = s.scan_layer;
      this.#excludeBlocks     = [...(s.exclude_blocks ?? [])];
      this.#origExcludeBlocks = [...(s.exclude_blocks ?? [])];
      this.#excludedIds       = new Set(s.exclude_islands ?? []);

      this.#el.querySelectorAll("#cfg-layer-list .filter-chip[data-layer]").forEach(el => {
        el.classList.toggle("filter-chip--active", el.dataset.layer === this.#scanLayer);
      });
    } catch (_) {}
  }

  async #loadBlockTypes(layerType) {
    try {
      const r = await fetch(`/api/configure/${this.#mapName}/layers/${layerType}/block-types`);
      if (!r.ok) return;
      this.#blockTypes = await r.json();   // flat array
      this.#renderBlockLists();
    } catch (_) {}
  }

  async #loadLayerPixels(layerType) {
    try {
      const r = await fetch(`/api/configure/${this.#mapName}/layers/${layerType}/pixels`);
      if (r.ok) {
        const data = await r.json();
        this.#canvas.loadBlockLayer(data);
      }
    } catch (_) {}
  }

  async #loadIslands() {
    try {
      const r = await fetch(`/api/map/${this.#mapName}/islands`);
      if (r.ok) {
        this.#islandsData = await r.json();
        this.#canvas.loadIslands(this.#islandsData);
        this.#renderIslandList();
      }
    } catch (_) {}
  }

  async #loadSymmetry() {
    try {
      const r = await fetch(`/api/map/${this.#mapName}/symmetry`);
      if (r.ok) {
        this.#symmetryData = await r.json();
        this.#canvas.loadSymmetry(this.#symmetryData);
        this.#renderSymPanel();
      }
    } catch (_) {}
  }

}
