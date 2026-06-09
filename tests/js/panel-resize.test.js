import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { connectPanelResizers } from "../../src/pgm_map_studio/studio/static/shared/panel-resize.js";

function classList() {
  const values = new Set();
  return {
    add: value => values.add(value),
    remove: value => values.delete(value),
    has: value => values.has(value),
  };
}

function fixture({ side = "left", min = "200", max = "480" } = {}) {
  const listeners = {};
  const panel = { offsetWidth: 280, style: {} };
  const handle = {
    dataset: {
      resizeTarget: "panel",
      resizeSide: side,
      resizeMin: min,
      resizeMax: max,
    },
    classList: classList(),
    addEventListener: (type, handler) => { listeners[type] = handler; },
  };
  const root = { querySelectorAll: () => [handle] };
  return { root, handle, panel, listeners };
}

describe("connectPanelResizers", () => {
  let documentListeners;

  beforeEach(() => {
    documentListeners = {};
    global.document = {
      body: { style: {} },
      getElementById: vi.fn(),
      addEventListener: (type, handler) => { documentListeners[type] = handler; },
      removeEventListener: vi.fn(),
    };
  });

  afterEach(() => {
    delete global.document;
  });

  it("resizes a left panel within configured limits", () => {
    const { root, panel, listeners } = fixture();
    document.getElementById.mockReturnValue(panel);

    connectPanelResizers(root);
    listeners.mousedown({ preventDefault: vi.fn(), clientX: 100 });
    documentListeners.mousemove({ clientX: 350 });

    expect(panel.style.width).toBe("480px");
  });

  it("reverses drag direction for a right panel", () => {
    const { root, panel, listeners } = fixture({ side: "right" });
    document.getElementById.mockReturnValue(panel);

    connectPanelResizers(root);
    listeners.mousedown({ preventDefault: vi.fn(), clientX: 500 });
    documentListeners.mousemove({ clientX: 600 });

    expect(panel.style.width).toBe("200px");
  });

  it("connects each handle only once", () => {
    const { root, handle } = fixture();
    document.getElementById.mockReturnValue({});
    const spy = vi.spyOn(handle, "addEventListener");

    connectPanelResizers(root);
    connectPanelResizers(root);

    expect(spy).toHaveBeenCalledTimes(1);
  });
});
