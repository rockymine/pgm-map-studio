import { describe, it, expect, beforeAll } from "vitest";

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

import { ringToPath, polyToPath, buildTransform } from "../../src/pgm_map_studio/studio/static/canvas/transform.js";

// ── Identity transform (sketch canvas pattern) ───────────────────────────────
// In SketchLayoutCanvas, world coords are SVG coords directly.
const identity = (x, z) => ({ x, y: z });

// ── Editor-style transform (MapCanvas pattern) ────────────────────────────────
const editorToSvg = buildTransform({ min_x: 0, min_z: 0, max_x: 100, max_z: 100 }, 300, 300);

// ── ringToPath ────────────────────────────────────────────────────────────────

describe("ringToPath — identity transform (sketch pattern)", () => {
  it("starts with M at first vertex", () => {
    const d = ringToPath([[0, 0], [10, 0], [10, 10]], identity);
    expect(d.startsWith("M")).toBe(true);
  });

  it("uses L for subsequent vertices", () => {
    const d = ringToPath([[0, 0], [10, 0], [10, 10]], identity);
    expect(d).toContain("L");
  });

  it("closes path with Z", () => {
    const d = ringToPath([[0, 0], [10, 0], [10, 10]], identity);
    expect(d.trim().endsWith("Z")).toBe(true);
  });

  it("maps world x to svg x, world z to svg y", () => {
    const d = ringToPath([[5, 3]], identity);
    expect(d).toContain("5");
    expect(d).toContain("3");
  });
});

describe("ringToPath — editor transform (MapCanvas pattern)", () => {
  it("produces a closed path string", () => {
    const d = ringToPath([[0, 0], [50, 0], [50, 50], [0, 50]], editorToSvg);
    expect(d.trim().endsWith("Z")).toBe(true);
  });

  it("maps world origin to a non-zero SVG coordinate (transform applied)", () => {
    const d = ringToPath([[0, 0]], editorToSvg);
    // With PAD=20 and scale derived from bbox, origin maps to ~(20, 20) not (0,0)
    expect(d).not.toContain("M0,0");
  });
});

// ── polyToPath ────────────────────────────────────────────────────────────────

describe("polyToPath — identity transform (sketch pattern)", () => {
  it("exterior only produces a single closed ring", () => {
    const poly = { exterior: [[0, 0], [10, 0], [10, 10], [0, 10]], holes: [] };
    const d = polyToPath(poly, identity);
    expect(d).toBeTruthy();
    expect(d.trim().endsWith("Z")).toBe(true);
  });

  it("hole is included in path", () => {
    const poly = {
      exterior: [[0, 0], [20, 0], [20, 20], [0, 20]],
      holes: [[[5, 5], [15, 5], [15, 15], [5, 15]]],
    };
    const d = polyToPath(poly, identity);
    // Both exterior and hole contribute — path must be longer than a bare ring
    const bare = ringToPath([[0, 0], [20, 0], [20, 20], [0, 20]], identity);
    expect(d.length).toBeGreaterThan(bare.length);
  });

  it("polygons variant renders all sub-polygons", () => {
    const poly = {
      polygons: [
        { exterior: [[0, 0], [5, 0], [5, 5], [0, 5]], holes: [] },
        { exterior: [[10, 10], [15, 10], [15, 15], [10, 15]], holes: [] },
      ],
    };
    const d = polyToPath(poly, identity);
    // Two M commands (one per polygon)
    expect((d.match(/M/g) || []).length).toBe(2);
  });
});

describe("polyToPath — editor transform (MapCanvas pattern)", () => {
  it("produces a non-empty path string for a square region", () => {
    const poly = { exterior: [[10, 10], [50, 10], [50, 50], [10, 50]], holes: [] };
    const d = polyToPath(poly, editorToSvg);
    expect(d).toBeTruthy();
    expect(d.trim().endsWith("Z")).toBe(true);
  });
});
