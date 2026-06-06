import { SketchSetupPanel } from "../panels/sketch-setup-panel.js";

export class SketchSetupActivity {
  #el    = null;
  #panel = null;

  constructor({ onStatusChange, onSetupSaved } = {}) {
    this.#el    = document.getElementById("sk-setup-workspace");
    this.#panel = new SketchSetupPanel(this.#el, { onStatusChange, onSetupSaved });
  }

  activate({ sketchId } = {}) {
    this.#el.hidden = false;
    if (sketchId) this.#panel.load(sketchId);
  }

  deactivate() {
    this.#el.hidden = true;
  }

  resize() {
    this.#panel.resize();
  }
}
