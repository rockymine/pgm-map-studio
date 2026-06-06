import { SketchOverviewPanel } from "../panels/sketch-overview-panel.js";

export class SketchOverviewActivity {
  #el    = null;
  #panel = null;

  constructor({ onStatusChange } = {}) {
    this.#el    = document.getElementById("sk-overview-workspace");
    this.#panel = new SketchOverviewPanel(this.#el, { onStatusChange });
  }

  activate({ sketchId } = {}) {
    this.#el.hidden = false;
    if (sketchId) this.#panel.load(sketchId);
  }

  deactivate() {
    this.#el.hidden = true;
  }
}
