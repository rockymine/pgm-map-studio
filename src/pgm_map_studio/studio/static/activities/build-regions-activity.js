/**
 * BuildRegionsActivity — workspace for the Build Regions activity.
 *
 * Shows a depth-tinted side view of the map (vertical cross-section) with a
 * draggable build height line. The sidebar panel syncs the numeric input with
 * the canvas handle.
 */

import { SideviewCanvas }     from "../canvas/sideview-canvas.js";
import { BuildRegionsPanel }  from "../panels/build-regions-panel.js";
import * as api               from "../api.js";

export class BuildRegionsActivity {
  #el       = null;
  #canvas   = null;
  #panel    = null;
  #mapName  = null;
  #axis     = "z";

  constructor({ onStatusChange } = {}) {
    this.#el = document.getElementById("br-workspace");

    this.#panel = new BuildRegionsPanel({
      onStatusChange,
      onHeightInput: (y) => this.#canvas?.setBuildHeight(y),
      onAxisChange:  (axis) => this._loadAxis(axis),
    });

    const canvasEl = document.getElementById("br-sideview-canvas");
    this.#canvas = new SideviewCanvas(canvasEl, {
      onHeightChange: (y) => this.#panel.setHeightFromCanvas(y),
    });
  }

  activate({ mapName } = {}) {
    this.#el.hidden = false;
    if (mapName && mapName !== this.#mapName) {
      this.#mapName = mapName;
      this.#panel.load(mapName);
      this._loadAxis(this.#axis);
    }
  }

  deactivate() {
    this.#el.hidden = true;
  }

  resize() {
    this.#canvas?.resize();
  }

  // ── Private ────────────────────────────────────────────────────────────────

  async _loadAxis(axis) {
    this.#axis = axis;
    if (!this.#mapName) return;

    // Show current build height while data loads
    const h = this.#panel.getHeight();
    this.#canvas.setBuildHeight(h);

    try {
      const data = await api.fetchSegments(this.#mapName, axis);
      this.#canvas.setData(data);
      this.#canvas.setBuildHeight(this.#panel.getHeight());
    } catch (err) {
      console.warn("BuildRegionsActivity: could not load segments:", err.message);
      this.#canvas.setData(null);
    }
  }
}
