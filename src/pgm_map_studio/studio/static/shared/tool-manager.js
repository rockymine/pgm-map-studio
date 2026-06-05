/**
 * ToolManager — centralizes tool-button state management for activity toolbars.
 *
 * Eliminates the near-identical setTool pattern duplicated across activities.
 * See docs/cross-cutting.md §6.
 *
 * @param {object} canvas     — canvas instance (must have setActiveTool(tool))
 * @param {object} buttonMap  — plain object { toolName: btnEl }
 *                              Use "select" as key for the null/select-mode tool.
 */
export class ToolManager {
  #canvas;
  #buttons;       // Map<toolKey, btnEl>  where toolKey is null for "select"
  #activeTool = null;

  constructor(canvas, buttonMap) {
    this.#canvas  = canvas;
    this.#buttons = new Map(
      Object.entries(buttonMap).map(([name, btn]) => [name === "select" ? null : name, btn]),
    );
  }

  get activeTool() { return this.#activeTool; }

  setTool(tool) {
    // Convert "select" string to null (the canvas null-tool value)
    const canvasTool = tool === "select" ? null : tool;
    this.#activeTool = canvasTool;
    this.#canvas.setActiveTool(canvasTool);
    for (const [key, btn] of this.#buttons) {
      btn.classList.toggle("draw-tool-btn--active", canvasTool === key);
    }
  }

  enable()            { this.setEnabled(true); }
  setEnabled(enabled) { for (const btn of this.#buttons.values()) btn.disabled = !enabled; }
}
