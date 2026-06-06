import * as api from "../api.js";
import { SketchSetupCanvas } from "../canvas/sketch-setup-canvas.js";
import { showToast } from "../shared/ui-helpers.js";

const PRESETS = {
  square: { min_x: -256, max_x: 256, min_z: -256, max_z: 256 },
  wide:   { min_x: -320, max_x: 320, min_z: -192, max_z: 192 },
  tall:   { min_x: -192, max_x: 192, min_z: -320, max_z: 320 },
};

export class SketchSetupPanel {
  #el;
  #sketchId       = null;
  #dirty          = false;
  #onStatusChange = null;

  // form refs
  #minXEl; #minZEl; #maxXEl; #maxZEl;
  #sizeXEl; #sizeZEl;
  #cxEl; #czEl;
  #modeChips;
  #presetChips;
  #centerResetBtn;
  #saveBtn; #statusEl;
  #activeMode = "rot_180";

  // canvas
  #canvas;

  constructor(el, { onStatusChange } = {}) {
    this.#el             = el;
    this.#onStatusChange = onStatusChange ?? null;

    this.#minXEl  = el.querySelector("#sk-bbox-min-x");
    this.#minZEl  = el.querySelector("#sk-bbox-min-z");
    this.#maxXEl  = el.querySelector("#sk-bbox-max-x");
    this.#maxZEl  = el.querySelector("#sk-bbox-max-z");
    this.#sizeXEl = el.querySelector("#sk-bbox-size-x");
    this.#sizeZEl = el.querySelector("#sk-bbox-size-z");
    this.#cxEl    = el.querySelector("#sk-center-x");
    this.#czEl    = el.querySelector("#sk-center-z");
    this.#saveBtn = el.querySelector("#sk-setup-save-btn");
    this.#statusEl= el.querySelector("#sk-setup-status");
    this.#modeChips     = [...el.querySelectorAll(".sk-mode-chip")];
    this.#presetChips   = [...el.querySelectorAll(".sk-bbox-preset")];
    this.#centerResetBtn = el.querySelector("#sk-center-reset");

    this.#canvas = new SketchSetupCanvas(
      el.querySelector("#sk-setup-svg"),
      el.querySelector("#sk-setup-canvas-wrap"),
      {
        onCenterMove: (cx, cz) => this.#onCanvasCenterMove(cx, cz),
        cursorEl: el.querySelector("#sk-setup-cursor"),
      },
    );

    this.#wireForm();
  }

  async load(sketchId) {
    this.#sketchId = sketchId;
    this.#setDirty(false);
    this.#statusEl.textContent = "";
    try {
      const data = await api.fetchSketch(sketchId);
      this.#populate(data.setup ?? null);
    } catch (err) {
      this.#statusEl.textContent = `Failed to load: ${err.message}`;
    }
  }

  resize() {
    this.#canvas.resize();
  }

  // ── private ───────────────────────────────────────────────────────────────

  #populate(setup) {
    if (setup?.bbox) {
      this.#minXEl.value = setup.bbox.min_x ?? "";
      this.#minZEl.value = setup.bbox.min_z ?? "";
      this.#maxXEl.value = setup.bbox.max_x ?? "";
      this.#maxZEl.value = setup.bbox.max_z ?? "";
      this.#updateSizeDisplay();
      this.#matchPreset();
      this.#updateModeAvailability();
      this.#canvas.setBbox(setup.bbox);
    } else {
      // No saved setup — apply Square as the default starting point
      const p = PRESETS.square;
      this.#minXEl.value = p.min_x;
      this.#maxXEl.value = p.max_x;
      this.#minZEl.value = p.min_z;
      this.#maxZEl.value = p.max_z;
      this.#updateSizeDisplay();
      this.#activatePreset("square");
      this.#updateModeAvailability();
      this.#canvas.setBbox(p);
      this.#canvas.fitToBbox();
    }
    if (setup?.center) {
      this.#cxEl.value = setup.center.cx ?? 0;
      this.#czEl.value = setup.center.cz ?? 0;
      this.#canvas.setCenter(setup.center.cx ?? 0, setup.center.cz ?? 0);
    }
    if (setup?.mirror_mode) {
      this.#setMode(setup.mirror_mode, false);
    } else {
      this.#setMode("rot_180", false);
    }
    if (setup?.bbox) this.#canvas.fitToBbox();
    this.#setDirty(false);
  }

  #wireForm() {
    // Bbox inputs — manual edit deselects any active preset
    for (const el of [this.#minXEl, this.#minZEl, this.#maxXEl, this.#maxZEl]) {
      el.addEventListener("input", () => {
        this.#updateSizeDisplay();
        this.#clearPreset();
        this.#updateModeAvailability();
        this.#setDirty(true);
      });
      el.addEventListener("change", () => this.#commitBbox());
    }

    // Bbox presets
    for (const chip of this.#presetChips) {
      chip.addEventListener("click", () => {
        const p = PRESETS[chip.dataset.preset];
        if (!p) return;
        this.#minXEl.value = p.min_x;
        this.#maxXEl.value = p.max_x;
        this.#minZEl.value = p.min_z;
        this.#maxZEl.value = p.max_z;
        this.#updateSizeDisplay();
        this.#activatePreset(chip.dataset.preset);
        this.#updateModeAvailability();
        this.#commitBbox();
        this.#setDirty(true);
      });
    }

    // Center reset
    this.#centerResetBtn.addEventListener("click", () => {
      this.#cxEl.value = 0;
      this.#czEl.value = 0;
      this.#canvas.setCenter(0, 0);
      this.#setDirty(true);
    });

    // Center inputs — commit on blur or Enter
    const commitCenter = () => this.#commitCenter();
    for (const el of [this.#cxEl, this.#czEl]) {
      el.addEventListener("blur", commitCenter);
      el.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); commitCenter(); } });
      el.addEventListener("input", () => this.#setDirty(true));
    }

    // Mode chips
    for (const chip of this.#modeChips) {
      chip.addEventListener("click", () => { this.#setMode(chip.dataset.mode); this.#setDirty(true); });
    }

    this.#saveBtn.addEventListener("click", () => this.#save());
  }

  #updateSizeDisplay() {
    const minX = parseFloat(this.#minXEl.value);
    const maxX = parseFloat(this.#maxXEl.value);
    const minZ = parseFloat(this.#minZEl.value);
    const maxZ = parseFloat(this.#maxZEl.value);
    this.#sizeXEl.textContent = (isFinite(minX) && isFinite(maxX) && maxX > minX) ? maxX - minX : "";
    this.#sizeZEl.textContent = (isFinite(minZ) && isFinite(maxZ) && maxZ > minZ) ? maxZ - minZ : "";
  }

  #commitBbox() {
    const bbox = this.#parseBbox();
    if (!bbox) return;
    this.#canvas.setBbox(bbox);
    this.#canvas.fitToBbox();
  }

  #commitCenter() {
    const cx = parseFloat(this.#cxEl.value);
    const cz = parseFloat(this.#czEl.value);
    if (!isFinite(cx) || !isFinite(cz)) return;
    this.#canvas.setCenter(cx, cz);
    this.#setDirty(true);
  }

  #onCanvasCenterMove(cx, cz) {
    this.#cxEl.value = cx;
    this.#czEl.value = cz;
    this.#setDirty(true);
  }

  #updateModeAvailability() {
    const bbox = this.#parseBbox();
    const isSquare = !!bbox && (bbox.max_x - bbox.min_x) === (bbox.max_z - bbox.min_z);

    const chip90 = this.#modeChips.find(c => c.dataset.mode === "rot_90");
    if (!chip90) return;
    chip90.disabled = !isSquare;
    chip90.title = isSquare
      ? "Quadrant symmetry around center — 4 teams"
      : "Requires a square bounding box";
    if (!isSquare && this.#activeMode === "rot_90") {
      this.#setMode("rot_180");
    }
  }

  #activatePreset(name) {
    for (const chip of this.#presetChips) {
      chip.classList.toggle("filter-chip--active", chip.dataset.preset === name);
    }
  }

  #clearPreset() {
    for (const chip of this.#presetChips) chip.classList.remove("filter-chip--active");
  }

  #matchPreset() {
    const minX = parseFloat(this.#minXEl.value);
    const maxX = parseFloat(this.#maxXEl.value);
    const minZ = parseFloat(this.#minZEl.value);
    const maxZ = parseFloat(this.#maxZEl.value);
    for (const [name, p] of Object.entries(PRESETS)) {
      if (p.min_x === minX && p.max_x === maxX && p.min_z === minZ && p.max_z === maxZ) {
        this.#activatePreset(name);
        return;
      }
    }
    this.#clearPreset();
  }

  #setMode(mode, updateCanvas = true) {
    this.#activeMode = mode;
    for (const chip of this.#modeChips) {
      chip.classList.toggle("filter-chip--active", chip.dataset.mode === mode);
    }
    if (updateCanvas) this.#canvas.setMode(mode);
  }

  #parseBbox() {
    const minX = parseFloat(this.#minXEl.value);
    const minZ = parseFloat(this.#minZEl.value);
    const maxX = parseFloat(this.#maxXEl.value);
    const maxZ = parseFloat(this.#maxZEl.value);
    if (!isFinite(minX) || !isFinite(minZ) || !isFinite(maxX) || !isFinite(maxZ)) return null;
    if (maxX <= minX || maxZ <= minZ) return null;
    return { min_x: minX, max_x: maxX, min_z: minZ, max_z: maxZ };
  }

  async #save() {
    if (!this.#sketchId) return;
    const bbox = this.#parseBbox();
    if (!bbox) {
      showToast("Enter a valid bounding box first", "error");
      return;
    }
    this.#saveBtn.disabled     = true;
    this.#statusEl.textContent = "Saving…";
    const payload = {
      bbox,
      center:      { cx: parseFloat(this.#cxEl.value) || 0, cz: parseFloat(this.#czEl.value) || 0 },
      mirror_mode: this.#activeMode,
    };
    try {
      await api.saveSketchSetup(this.#sketchId, payload);
      this.#setDirty(false);
      showToast("Setup saved", "success");
      this.#statusEl.textContent = "";
    } catch (err) {
      this.#statusEl.textContent = `Save failed: ${err.message}`;
      showToast(`Save failed: ${err.message}`, "error");
      this.#saveBtn.disabled = false;
    }
  }

  #setDirty(isDirty) {
    this.#dirty            = isDirty;
    this.#saveBtn.disabled = !isDirty;
    this.#updateStatusDot();
  }

  #updateStatusDot() {
    if (!this.#onStatusChange) return;
    const valid = !!this.#parseBbox();
    this.#onStatusChange(valid ? "green" : "yellow");
  }
}
