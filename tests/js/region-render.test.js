import { describe, it, expect, beforeAll } from "vitest";

// Minimal DOM stub — avoids jsdom/happy-dom environment requirement
beforeAll(() => {
  globalThis.document = {
    createElementNS(_ns, tag) {
      const attrs = {};
      return {
        tagName: tag,
        setAttribute(k, v) { attrs[k] = String(v); },
        getAttribute(k) { return attrs[k] ?? null; },
        appendChild() {},
      };
    },
  };
});

import { renderRegionShape } from "../../src/pgm_map_studio/studio/static/shared/region-render.js";

// Simple identity toSvg: world coords → same pixel coords
const toSvg = (wx, wz) => ({ x: wx, y: wz });

// Common attrs used across tests
const ATTRS = { fill: "#ff0000", "fill-opacity": "0.2" };

describe("renderRegionShape — rectangle", () => {
  it("returns a <rect> element", () => {
    const el = renderRegionShape("rectangle", { min_x: 0, min_z: 0, max_x: 10, max_z: 20 }, toSvg, ATTRS);
    expect(el.tagName.toLowerCase()).toBe("rect");
  });

  it("sets x, y, width, height correctly", () => {
    const el = renderRegionShape("rectangle", { min_x: 5, min_z: 10, max_x: 15, max_z: 30 }, toSvg, ATTRS);
    expect(+el.getAttribute("x")).toBe(5);
    expect(+el.getAttribute("y")).toBe(10);
    expect(+el.getAttribute("width")).toBe(10);
    expect(+el.getAttribute("height")).toBe(20);
  });

  it("applies provided attrs", () => {
    const el = renderRegionShape("rectangle", { min_x: 0, min_z: 0, max_x: 1, max_z: 1 }, toSvg, { fill: "#abc" });
    expect(el.getAttribute("fill")).toBe("#abc");
  });
});

describe("renderRegionShape — cuboid", () => {
  it("returns a <rect> (XZ projection)", () => {
    const el = renderRegionShape("cuboid", { min_x: 0, min_z: 0, max_x: 4, max_z: 4 }, toSvg, {});
    expect(el.tagName.toLowerCase()).toBe("rect");
    expect(+el.getAttribute("width")).toBe(4);
    expect(+el.getAttribute("height")).toBe(4);
  });
});

describe("renderRegionShape — cylinder", () => {
  it("returns an <ellipse> element", () => {
    const el = renderRegionShape("cylinder", { min_x: 0, min_z: 0, max_x: 10, max_z: 10 }, toSvg, {});
    expect(el.tagName.toLowerCase()).toBe("ellipse");
  });

  it("sets cx, cy at bounds centre", () => {
    const el = renderRegionShape("cylinder", { min_x: 0, min_z: 0, max_x: 10, max_z: 10 }, toSvg, {});
    expect(+el.getAttribute("cx")).toBe(5);
    expect(+el.getAttribute("cy")).toBe(5);
  });

  it("sets rx, ry from half-width, half-height", () => {
    const el = renderRegionShape("cylinder", { min_x: 0, min_z: 0, max_x: 10, max_z: 6 }, toSvg, {});
    expect(+el.getAttribute("rx")).toBe(5);
    expect(+el.getAttribute("ry")).toBe(3);
  });
});

describe("renderRegionShape — circle", () => {
  it("returns an <ellipse> element", () => {
    const el = renderRegionShape("circle", { min_x: 2, min_z: 2, max_x: 8, max_z: 8 }, toSvg, {});
    expect(el.tagName.toLowerCase()).toBe("ellipse");
  });
});

describe("renderRegionShape — sphere", () => {
  it("returns an <ellipse> element", () => {
    const el = renderRegionShape("sphere", { min_x: 0, min_z: 0, max_x: 6, max_z: 6 }, toSvg, {});
    expect(el.tagName.toLowerCase()).toBe("ellipse");
  });
});

describe("renderRegionShape — polygon_2d", () => {
  it("returns a <path> element when passed exterior ring", () => {
    const poly = { exterior: [[0,0],[10,0],[10,10],[0,10]], holes: [] };
    const el = renderRegionShape("union", poly, toSvg, {});
    expect(el.tagName.toLowerCase()).toBe("path");
    expect(el.getAttribute("d")).toBeTruthy();
  });

  it("returns null when polygon has no exterior", () => {
    const el = renderRegionShape("union", { exterior: [], holes: [] }, toSvg, {});
    expect(el).toBeNull();
  });
});

describe("renderRegionShape — null input", () => {
  it("returns null when boundsOrPoly is null", () => {
    expect(renderRegionShape("rectangle", null, toSvg, {})).toBeNull();
  });
});
