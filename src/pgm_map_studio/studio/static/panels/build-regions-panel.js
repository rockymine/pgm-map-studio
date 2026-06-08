/**
 * BuildRegionsPanel — sidebar panel for the Build Regions activity.
 *
 * Controls:
 *   - Max build height numeric input (synced with canvas handle)
 *   - Clear button to remove the height limit
 *   - Axis toggle (Z view / X view)
 *   - Save button
 */

import * as api from "../api.js";
import { showToast } from "../shared/ui-helpers.js";

export class BuildRegionsPanel {
  #mapName  = null;
  #dirty    = false;
  #opts;

  // DOM refs
  #heightInput;
  #saveBtn;
  #saveStatus;
  #axisZBtn;
  #axisXBtn;

  constructor(opts = {}) {
    this.#opts = opts;

    this.#heightInput = document.getElementById("br-max-height");
    this.#saveBtn     = document.getElementById("br-save-btn");
    this.#saveStatus  = document.getElementById("br-save-status");
    this.#axisZBtn    = document.getElementById("br-axis-z");
    this.#axisXBtn    = document.getElementById("br-axis-x");

    this._attachListeners();
  }

  async load(mapName) {
    this.#mapName = mapName;
    this.#dirty   = false;
    this._setSaveStatus("");

    try {
      const data = await api.fetchMapData(mapName);
      const h = data.max_build_height;
      this.#heightInput.value = (h != null) ? String(h) : "";
      this._updateSaveBtn();
    } catch {
      this.#heightInput.value = "";
    }
  }

  /** Called by the canvas when the user drags the height line. */
  setHeightFromCanvas(worldY) {
    this.#heightInput.value = String(worldY);
    this._markDirty();
  }

  /** Returns the current height value (null = unset). */
  getHeight() {
    const v = this.#heightInput.value.trim();
    const n = parseInt(v, 10);
    return (v === "" || isNaN(n)) ? null : n;
  }

  getAxis() {
    return this.#axisXBtn?.classList.contains("active") ? "x" : "z";
  }

  // ── Private ────────────────────────────────────────────────────────────────

  _attachListeners() {
    this.#heightInput?.addEventListener("input", () => {
      this._markDirty();
      this.#opts.onHeightInput?.(this.getHeight());
    });

    this.#saveBtn?.addEventListener("click", () => this._save());

    this.#axisZBtn?.addEventListener("click", () => this._setAxis("z"));
    this.#axisXBtn?.addEventListener("click", () => this._setAxis("x"));
  }

  _setAxis(axis) {
    this.#axisZBtn?.classList.toggle("filter-chip--active", axis === "z");
    this.#axisXBtn?.classList.toggle("filter-chip--active", axis === "x");
    this.#opts.onAxisChange?.(axis);
  }

  _markDirty() {
    this.#dirty = true;
    this._updateSaveBtn();
  }

  _updateSaveBtn() {
    if (this.#saveBtn) this.#saveBtn.disabled = !this.#dirty;
  }

  _setSaveStatus(msg) {
    if (this.#saveStatus) this.#saveStatus.textContent = msg;
  }

  async _save() {
    if (!this.#mapName || !this.#dirty) return;
    try {
      this.#saveBtn.disabled = true;
      this._setSaveStatus("Saving…");
      const h = this.getHeight();
      await api.patchMapMetadata(this.#mapName, { max_build_height: h });
      this.#dirty = false;
      this._updateSaveBtn();
      this._setSaveStatus("Saved");
      setTimeout(() => this._setSaveStatus(""), 2000);
      showToast("Build height saved", "success");
      this.#opts.onStatusChange?.("green");
    } catch (err) {
      this._setSaveStatus("Save failed");
      showToast(`Save failed: ${err.message}`, "error");
      this.#saveBtn.disabled = false;
    }
  }
}
