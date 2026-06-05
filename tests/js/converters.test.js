import { describe, it, expect } from "vitest";
import {
  blockToExtentBounds,
  drawnBoundsFromBlocks,
  regionToBounds2d,
  applySymmetry,
  applySymmetryToBounds,
  rasterisePolygon,
  sketchShapeToPgmRegion,
} from "../../src/pgm_map_studio/studio/static/shared/converters.js";

// ── blockToExtentBounds ───────────────────────────────────────────────────────

describe("blockToExtentBounds", () => {
  it("adds +1 to both axes", () => {
    expect(blockToExtentBounds(7, 2)).toEqual({ min_x: 7, max_x: 8, min_z: 2, max_z: 3 });
  });

  it("works at origin", () => {
    expect(blockToExtentBounds(0, 0)).toEqual({ min_x: 0, max_x: 1, min_z: 0, max_z: 1 });
  });

  it("works with negative coordinates", () => {
    expect(blockToExtentBounds(-3, -5)).toEqual({ min_x: -3, max_x: -2, min_z: -5, max_z: -4 });
  });
});

// ── drawnBoundsFromBlocks ─────────────────────────────────────────────────────

describe("drawnBoundsFromBlocks", () => {
  it("single block applies +1 to max", () => {
    expect(drawnBoundsFromBlocks(3, 5, 3, 5)).toEqual({ min_x: 3, max_x: 4, min_z: 5, max_z: 6 });
  });

  it("range of blocks applies +1 to max only", () => {
    expect(drawnBoundsFromBlocks(3, 5, 6, 9)).toEqual({ min_x: 3, max_x: 7, min_z: 5, max_z: 10 });
  });

  it("normalises inverted input (b2 < b1)", () => {
    expect(drawnBoundsFromBlocks(6, 9, 3, 5)).toEqual({ min_x: 3, max_x: 7, min_z: 5, max_z: 10 });
  });
});

// ── regionToBounds2d ──────────────────────────────────────────────────────────

describe("regionToBounds2d", () => {
  it("block: applies +1 rule", () => {
    expect(regionToBounds2d({ type: "block", x: 5, z: 3 })).toEqual({ min_x: 5, max_x: 6, min_z: 3, max_z: 4 });
  });

  it("cylinder: base ± radius", () => {
    expect(regionToBounds2d({ type: "cylinder", base_x: 10, base_z: 10, radius: 5 }))
      .toEqual({ min_x: 5, max_x: 15, min_z: 5, max_z: 15 });
  });

  it("rectangle: passes through", () => {
    expect(regionToBounds2d({ type: "rectangle", min_x: 0, min_z: 0, max_x: 10, max_z: 20 }))
      .toEqual({ min_x: 0, min_z: 0, max_x: 10, max_z: 20 });
  });

  it("cuboid: XZ projection (y ignored)", () => {
    expect(regionToBounds2d({ type: "cuboid", min_x: 1, min_y: 0, min_z: 2, max_x: 5, max_y: 10, max_z: 8 }))
      .toEqual({ min_x: 1, min_z: 2, max_x: 5, max_z: 8 });
  });

  it("circle: center ± radius", () => {
    expect(regionToBounds2d({ type: "circle", center_x: 5, center_z: 5, radius: 3 }))
      .toEqual({ min_x: 2, max_x: 8, min_z: 2, max_z: 8 });
  });

  it("sphere: origin ± radius", () => {
    expect(regionToBounds2d({ type: "sphere", origin_x: 0, origin_z: 0, radius: 4 }))
      .toEqual({ min_x: -4, max_x: 4, min_z: -4, max_z: 4 });
  });

  it("point: ±0.5 around coordinate", () => {
    expect(regionToBounds2d({ type: "point", x: 10, z: 20 }))
      .toEqual({ min_x: 9.5, max_x: 10.5, min_z: 19.5, max_z: 20.5 });
  });

  it("union: returns null (composite)", () => {
    expect(regionToBounds2d({ type: "union" })).toBeNull();
  });

  it("intersect: returns null (composite)", () => {
    expect(regionToBounds2d({ type: "intersect" })).toBeNull();
  });

  it("negative: returns null (composite)", () => {
    expect(regionToBounds2d({ type: "negative" })).toBeNull();
  });

  it("null input: returns null", () => {
    expect(regionToBounds2d(null)).toBeNull();
  });
});

// ── applySymmetry ─────────────────────────────────────────────────────────────

describe("applySymmetry", () => {
  describe("mirror_x — flips X around vertical line at x = cx", () => {
    it("at origin", () => {
      expect(applySymmetry(10, 20, "mirror_x", 0, 0)).toEqual([-10, 20]);
    });
    it("with non-zero center", () => {
      expect(applySymmetry(10, 20, "mirror_x", 5, 5)).toEqual([0, 20]);
    });
  });

  describe("mirror_z — flips Z around horizontal line at z = cz", () => {
    it("at origin", () => {
      expect(applySymmetry(10, 20, "mirror_z", 0, 0)).toEqual([10, -20]);
    });
    it("with non-zero center", () => {
      expect(applySymmetry(10, 20, "mirror_z", 5, 15)).toEqual([10, 10]);
    });
  });

  describe("rot_180 — half-turn around center", () => {
    it("at origin", () => {
      expect(applySymmetry(10, 20, "rot_180", 0, 0)).toEqual([-10, -20]);
    });
    it("maps point to center when point is at radius", () => {
      expect(applySymmetry(10, 20, "rot_180", 5, 10)).toEqual([0, 0]);
    });
  });

  describe("rot_90 CCW — quarter-turn around center", () => {
    it("unit vector on X maps to unit vector on +Z", () => {
      expect(applySymmetry(1, 0, "rot_90", 0, 0)).toEqual([0, 1]);
    });
    it("unit vector on +Z maps to unit vector on -X", () => {
      expect(applySymmetry(0, 1, "rot_90", 0, 0)).toEqual([-1, 0]);
    });
  });
});

// ── applySymmetryToBounds ─────────────────────────────────────────────────────

describe("applySymmetryToBounds", () => {
  const bounds = { min_x: 2, max_x: 6, min_z: 3, max_z: 9 };

  it("mirror_x round-trip returns original bounds", () => {
    const once = applySymmetryToBounds(bounds, "mirror_x", 0, 0);
    const twice = applySymmetryToBounds(once, "mirror_x", 0, 0);
    expect(twice).toEqual(bounds);
  });

  it("mirror_z round-trip returns original bounds", () => {
    const once = applySymmetryToBounds(bounds, "mirror_z", 0, 0);
    const twice = applySymmetryToBounds(once, "mirror_z", 0, 0);
    expect(twice).toEqual(bounds);
  });

  it("rot_180 round-trip returns original bounds", () => {
    const once = applySymmetryToBounds(bounds, "rot_180", 0, 0);
    const twice = applySymmetryToBounds(once, "rot_180", 0, 0);
    expect(twice).toEqual(bounds);
  });

  it("mirrors a symmetric bounds at its own center to itself", () => {
    const sym = { min_x: -5, max_x: 5, min_z: -5, max_z: 5 };
    expect(applySymmetryToBounds(sym, "mirror_x", 0, 0)).toEqual(sym);
    expect(applySymmetryToBounds(sym, "mirror_z", 0, 0)).toEqual(sym);
    expect(applySymmetryToBounds(sym, "rot_180", 0, 0)).toEqual(sym);
  });
});

// ── rasterisePolygon ──────────────────────────────────────────────────────────

describe("rasterisePolygon", () => {
  it("2×2 extent polygon yields exactly 4 blocks", () => {
    const exterior = [[0, 0], [2, 0], [2, 2], [0, 2]];
    const blocks = rasterisePolygon(exterior, []);
    const sorted = [...blocks].sort(([ax, az], [bx, bz]) => ax - bx || az - bz);
    expect(sorted).toEqual([[0, 0], [0, 1], [1, 0], [1, 1]]);
  });

  it("1×1 extent polygon yields 1 block", () => {
    const exterior = [[0, 0], [1, 0], [1, 1], [0, 1]];
    const blocks = rasterisePolygon(exterior, []);
    expect(blocks).toHaveLength(1);
    expect(blocks[0]).toEqual([0, 0]);
  });

  it("hole punches out blocks", () => {
    // 4×4 square with 2×2 hole in centre
    const exterior = [[0, 0], [4, 0], [4, 4], [0, 4]];
    const hole = [[1, 1], [3, 1], [3, 3], [1, 3]];
    const blocks = rasterisePolygon(exterior, [hole]);
    // should have 16 - 4 = 12 blocks
    expect(blocks).toHaveLength(12);
  });

  it("empty polygon yields no blocks", () => {
    expect(rasterisePolygon([], [])).toEqual([]);
  });
});

// ── sketchShapeToPgmRegion ────────────────────────────────────────────────────

describe("sketchShapeToPgmRegion", () => {
  it("rectangle remaps to PGM rectangle", () => {
    expect(sketchShapeToPgmRegion({ type: "rectangle", min_x: 0, max_x: 10, min_z: 0, max_z: 10 }))
      .toEqual({ type: "rectangle", min_x: 0, max_x: 10, min_z: 0, max_z: 10 });
  });

  it("circle remaps to PGM circle", () => {
    expect(sketchShapeToPgmRegion({ type: "circle", center_x: 5, center_z: 5, radius: 3 }))
      .toEqual({ type: "circle", center_x: 5, center_z: 5, radius: 3 });
  });

  it("polygon returns null (no PGM primitive)", () => {
    expect(sketchShapeToPgmRegion({ type: "polygon", vertices: [[0, 0], [1, 0], [0, 1]] })).toBeNull();
  });

  it("lasso returns null (no PGM primitive)", () => {
    expect(sketchShapeToPgmRegion({ type: "lasso", vertices: [[0, 0]] })).toBeNull();
  });
});
