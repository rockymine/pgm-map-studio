import { describe, it, expect, vi } from "vitest";
import { ToolManager } from "../../src/pgm_map_studio/studio/static/shared/tool-manager.js";

function mockCanvas() {
  return { setActiveTool: vi.fn() };
}

function mockBtn() {
  const toggles = new Map();
  return {
    _disabled: false,
    get disabled() { return this._disabled; },
    set disabled(v) { this._disabled = v; },
    classList: {
      toggle(cls, force) { toggles.set(cls, force); },
      has(cls) { return toggles.get(cls) === true; },
    },
    _toggles: toggles,
  };
}

describe("ToolManager", () => {
  it("calls canvas.setActiveTool on setTool", () => {
    const canvas = mockCanvas();
    const move = mockBtn();
    const mgr = new ToolManager(canvas, { move });
    mgr.setTool("move");
    expect(canvas.setActiveTool).toHaveBeenCalledWith("move");
  });

  it("converts 'select' key to null tool for canvas", () => {
    const canvas = mockCanvas();
    const sel = mockBtn();
    const mgr = new ToolManager(canvas, { select: sel });
    mgr.setTool("select");
    expect(canvas.setActiveTool).toHaveBeenCalledWith(null);
  });

  it("marks active button with draw-tool-btn--active class", () => {
    const canvas = mockCanvas();
    const move = mockBtn(), sel = mockBtn(), cyl = mockBtn();
    const mgr = new ToolManager(canvas, { move, select: sel, cylinder: cyl });
    mgr.setTool("move");
    expect(move.classList.has("draw-tool-btn--active")).toBe(true);
    expect(sel.classList.has("draw-tool-btn--active")).toBe(false);
    expect(cyl.classList.has("draw-tool-btn--active")).toBe(false);
  });

  it("switches active button when tool changes", () => {
    const canvas = mockCanvas();
    const move = mockBtn(), cyl = mockBtn();
    const mgr = new ToolManager(canvas, { move, cylinder: cyl });
    mgr.setTool("move");
    mgr.setTool("cylinder");
    expect(move.classList.has("draw-tool-btn--active")).toBe(false);
    expect(cyl.classList.has("draw-tool-btn--active")).toBe(true);
  });

  it("activeTool getter returns current tool name (null for select)", () => {
    const canvas = mockCanvas();
    const sel = mockBtn();
    const mgr = new ToolManager(canvas, { select: sel });
    mgr.setTool("select");
    expect(mgr.activeTool).toBeNull();
  });

  it("activeTool getter returns tool string for named tools", () => {
    const canvas = mockCanvas();
    const move = mockBtn();
    const mgr = new ToolManager(canvas, { move });
    mgr.setTool("move");
    expect(mgr.activeTool).toBe("move");
  });

  it("setEnabled(false) disables all buttons", () => {
    const canvas = mockCanvas();
    const move = mockBtn(), sel = mockBtn();
    const mgr = new ToolManager(canvas, { move, select: sel });
    mgr.setEnabled(false);
    expect(move.disabled).toBe(true);
    expect(sel.disabled).toBe(true);
  });

  it("enable() re-enables all buttons", () => {
    const canvas = mockCanvas();
    const move = mockBtn();
    const mgr = new ToolManager(canvas, { move });
    mgr.setEnabled(false);
    mgr.enable();
    expect(move.disabled).toBe(false);
  });
});
