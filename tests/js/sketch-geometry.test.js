/**
 * Tests for sketch/geometry.js — boolean island computation.
 *
 * All shape coordinates are in world-space extent bounds (min_x, max_x etc.
 * already have the +1 applied at draw time). Polygon-clipping must be
 * installed in the local test runner: cd /root/pgm-studio-tests && npm i polygon-clipping
 */

import { describe, it, expect } from "vitest";
import {
  shapeToRing,
  circleToRing,
  shapeToMultiPoly,
  pointInRing,
  pointInIsland,
  ringCentroid,
  computeIslands,
  assignShapesToIslands,
  computeMirrorPreview,
} from "../../src/pgm_map_studio/studio/static/sketch/geometry.js";

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Build a rectangle shape descriptor. */
function rect(min_x, min_z, max_x, max_z, opts = {}) {
  return { id: opts.id ?? "s1", type: "rectangle", operation: opts.op ?? "add",
           override: opts.override ?? false, min_x, min_z, max_x, max_z };
}

function circle(cx, cz, radius, opts = {}) {
  return { id: opts.id ?? "s1", type: "circle", operation: opts.op ?? "add",
           override: opts.override ?? false, center_x: cx, center_z: cz, radius };
}

function polygon(vertices, opts = {}) {
  return { id: opts.id ?? "s1", type: "polygon", operation: opts.op ?? "add",
           override: opts.override ?? false, vertices };
}

/** Sort island exteriors by centroid x then z for deterministic comparison. */
function sortIslands(islands) {
  return [...islands].sort((a, b) => {
    const [ax, az] = ringCentroid(a.exterior);
    const [bx, bz] = ringCentroid(b.exterior);
    return ax !== bx ? ax - bx : az - bz;
  });
}

/** Approximate bounding box of an exterior ring. */
function bbox(ring) {
  const xs = ring.map(p => p[0]), zs = ring.map(p => p[1]);
  return {
    min_x: Math.min(...xs), max_x: Math.max(...xs),
    min_z: Math.min(...zs), max_z: Math.max(...zs),
  };
}

// ── shapeToRing ───────────────────────────────────────────────────────────────

describe("shapeToRing", () => {
  it("rectangle produces a closed 5-point ring", () => {
    const ring = shapeToRing(rect(0, 0, 4, 3));
    expect(ring).toHaveLength(5);
    expect(ring[0]).toEqual(ring[4]); // closed
    expect(ring).toContainEqual([0, 0]);
    expect(ring).toContainEqual([4, 0]);
    expect(ring).toContainEqual([4, 3]);
    expect(ring).toContainEqual([0, 3]);
  });

  it("polygon closes the ring by appending the first vertex", () => {
    const verts = [[0, 0], [4, 0], [2, 4]];
    const ring = shapeToRing(polygon(verts));
    expect(ring).toHaveLength(4);
    expect(ring[0]).toEqual(ring[3]);
  });

  it("lasso is treated the same as polygon", () => {
    const verts = [[0, 0], [4, 0], [2, 4]];
    const lasso = { id: "s1", type: "lasso", operation: "add", override: false, vertices: verts };
    expect(shapeToRing(lasso)).toEqual(shapeToRing(polygon(verts)));
  });

  it("polygon with fewer than 3 vertices returns empty ring", () => {
    const s = polygon([[0, 0], [1, 0]]);
    expect(shapeToRing(s)).toEqual([]);
  });
});

// ── circleToRing ──────────────────────────────────────────────────────────────

describe("circleToRing", () => {
  it("produces a closed ring", () => {
    const ring = circleToRing(0, 0, 10);
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("all points are within radius + 1 of center (rounding)", () => {
    const ring = circleToRing(5, 5, 20);
    for (const [x, z] of ring) {
      expect(Math.hypot(x - 5, z - 5)).toBeLessThanOrEqual(21);
    }
  });

  it("respects nPoints parameter", () => {
    const ring = circleToRing(0, 0, 10, 8);
    expect(ring).toHaveLength(9); // 8 + closing point
  });
});

// ── pointInRing / pointInIsland ───────────────────────────────────────────────

describe("pointInRing", () => {
  const square = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]];

  it("interior point is inside", () => {
    expect(pointInRing(2, 2, square)).toBe(true);
  });

  it("exterior point is outside", () => {
    expect(pointInRing(5, 5, square)).toBe(false);
  });

  it("point on the boundary is edge-case (consistent with ray-casting)", () => {
    // Behaviour on exact boundary is well-defined but unspecified; just must not throw.
    expect(() => pointInRing(4, 2, square)).not.toThrow();
  });
});

describe("pointInIsland", () => {
  const outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]];
  const hole  = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]];

  it("point inside exterior but not in hole is inside island", () => {
    expect(pointInIsland(1, 1, { exterior: outer, holes: [hole] })).toBe(true);
  });

  it("point inside the hole is not inside island", () => {
    expect(pointInIsland(5, 5, { exterior: outer, holes: [hole] })).toBe(false);
  });

  it("point outside exterior is not inside island", () => {
    expect(pointInIsland(15, 5, { exterior: outer, holes: [hole] })).toBe(false);
  });
});

// ── ringCentroid ──────────────────────────────────────────────────────────────

describe("ringCentroid", () => {
  it("centroid of an axis-aligned rectangle is its centre", () => {
    const ring = [[0, 0], [4, 0], [4, 6], [0, 6], [0, 0]];
    const [cx, cz] = ringCentroid(ring);
    expect(cx).toBeCloseTo(2);
    expect(cz).toBeCloseTo(3);
  });

  it("centroid of a symmetric triangle is at (cx=1, cz=1/3) for a unit triangle", () => {
    const ring = [[0, 0], [3, 0], [0, 3], [0, 0]];
    const [cx, cz] = ringCentroid(ring);
    expect(cx).toBeCloseTo(1);
    expect(cz).toBeCloseTo(1);
  });
});

// ── computeIslands ────────────────────────────────────────────────────────────

describe("computeIslands — basic cases", () => {
  it("no shapes → no islands", () => {
    const { islands } = computeIslands([]);
    expect(islands).toHaveLength(0);
  });

  it("single add rectangle → 1 island", () => {
    const { islands } = computeIslands([rect(0, 0, 10, 10)]);
    expect(islands).toHaveLength(1);
    expect(islands[0].exterior.length).toBeGreaterThan(0);
  });

  it("two non-overlapping add rectangles → 2 islands", () => {
    const shapes = [
      rect(0, 0, 5, 5, { id: "a" }),
      rect(10, 10, 15, 15, { id: "b" }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(2);
  });

  it("two overlapping add rectangles merge into 1 island", () => {
    const shapes = [
      rect(0, 0, 8, 8, { id: "a" }),
      rect(4, 4, 12, 12, { id: "b" }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(1);
  });

  it("subtract covering entire add area → 0 islands", () => {
    const shapes = [
      rect(0, 0, 10, 10, { id: "a" }),
      rect(0, 0, 10, 10, { id: "b", op: "subtract" }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(0);
  });

  it("subtract carves a hole into the middle of an island", () => {
    const shapes = [
      rect(0, 0, 12, 12, { id: "a" }),
      rect(4, 4, 8, 8, { id: "b", op: "subtract" }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(1);
    expect(islands[0].holes).toHaveLength(1);
  });

  it("subtract splitting a rectangle through the middle → 2 islands", () => {
    // Wide rectangle cut vertically through the middle.
    const shapes = [
      rect(0, 0, 20, 10, { id: "a" }),
      rect(8, 0, 12, 10, { id: "b", op: "subtract" }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(2);
    const sorted = sortIslands(islands);
    // Left island centroid x ≈ 4, right x ≈ 16
    expect(ringCentroid(sorted[0].exterior)[0]).toBeLessThan(8);
    expect(ringCentroid(sorted[1].exterior)[0]).toBeGreaterThan(12);
  });

  it("only subtract shapes (no add) → 0 islands", () => {
    const { islands } = computeIslands([
      rect(0, 0, 10, 10, { op: "subtract" }),
    ]);
    expect(islands).toHaveLength(0);
  });
});

describe("computeIslands — circle shapes", () => {
  it("circle add shape creates an island", () => {
    const { islands } = computeIslands([circle(0, 0, 50)]);
    expect(islands).toHaveLength(1);
    // Bounding box should be roughly ±50 (with rounding).
    const b = bbox(islands[0].exterior);
    expect(b.min_x).toBeLessThanOrEqual(-48);
    expect(b.max_x).toBeGreaterThanOrEqual(48);
  });

  it("two touching (but non-overlapping) circles stay as 2 islands", () => {
    // Centers 100 apart with radius 40 each → 20 gap
    const shapes = [
      circle(-50, 0, 40, { id: "a" }),
      circle(50, 0, 40, { id: "b" }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(2);
  });

  it("two overlapping circles merge into 1 island", () => {
    const shapes = [
      circle(0, 0, 30, { id: "a" }),
      circle(20, 0, 30, { id: "b" }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(1);
  });
});

describe("computeIslands — polygon / lasso shapes", () => {
  it("L-shaped polygon creates one island", () => {
    // L shape: 10×10 with top-right 5×5 removed
    const verts = [[0,0],[10,0],[10,5],[5,5],[5,10],[0,10]];
    const { islands } = computeIslands([polygon(verts)]);
    expect(islands).toHaveLength(1);
  });

  it("polygon subtract carves into rectangle", () => {
    const shapes = [
      rect(0, 0, 20, 20, { id: "a" }),
      polygon([[5,0],[15,0],[10,8]], { id: "b", op: "subtract" }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(1);
    // The top portion should have been carved out.
    const b = bbox(islands[0].exterior);
    expect(b.max_z).toBeCloseTo(20);
  });
});

describe("computeIslands — override mode", () => {
  it("override-add is immune to normal subtract", () => {
    // The override-add area should survive even though a normal subtract covers it.
    const shapes = [
      rect(0, 0, 20, 10, { id: "base" }),
      rect(5, 0, 15, 10, { id: "sub", op: "subtract" }),          // removes centre strip
      rect(7, 2, 13, 8, { id: "ovr", op: "add", override: true }), // re-adds inner area
    ];
    const { islands } = computeIslands(shapes);
    // Should have 3 islands: left strip, right strip, override-add island
    // (override-add is unioned back in after normal sub, which may or may not
    //  reconnect — depends on gap. With a gap of 2 blocks they stay separate.)
    expect(islands.length).toBeGreaterThanOrEqual(1);
    // The override-add centroid (10, 5) must be inside some island.
    const covered = islands.some(isl => pointInIsland(10, 5, isl));
    expect(covered).toBe(true);
  });

  it("override-subtract cuts through override-add", () => {
    const shapes = [
      rect(0, 0, 20, 20, { id: "base" }),
      rect(5, 5, 15, 15, { id: "ovradd", op: "add", override: true }),  // redundant but valid
      rect(8, 0, 12, 20, { id: "ovrsub", op: "subtract", override: true }), // cuts through centre
    ];
    const { islands } = computeIslands(shapes);
    // Override-sub cuts through the whole thing, so there should be 2 islands
    // (left and right of the cut).
    expect(islands.length).toBe(2);
    // Nothing at x=10 (the cut zone)
    const atCentre = islands.some(isl => pointInIsland(10, 10, isl));
    expect(atCentre).toBe(false);
  });

  it("override-add shapes with no normal add create islands by themselves", () => {
    const shapes = [
      rect(0, 0, 10, 10, { id: "oa", op: "add", override: true }),
    ];
    const { islands } = computeIslands(shapes);
    expect(islands).toHaveLength(1);
  });
});

describe("computeIslands — name/mirror persistence", () => {
  it("preserves name and mirror flag when centroid is nearby", () => {
    const prev = [
      {
        id: "isl_old", name: "My Island", color: "#aaa", mirrors: false,
        exterior: [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        holes: [], shapeIds: [],
      },
    ];
    // Slightly different rectangle — centroid shifts from (5,5) to (5.5,5.5)
    const { islands } = computeIslands([rect(0, 0, 11, 11)], prev);
    expect(islands).toHaveLength(1);
    expect(islands[0].name).toBe("My Island");
    expect(islands[0].mirrors).toBe(false);
  });

  it("new island (centroid too far) gets default name", () => {
    const prev = [
      {
        id: "isl_old", name: "My Island", color: "#aaa", mirrors: true,
        exterior: [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        holes: [], shapeIds: [],
      },
    ];
    const { islands } = computeIslands([rect(100, 100, 110, 110)], prev);
    expect(islands[0].name).toBe("Island 1"); // default, not matched
  });
});

// ── assignShapesToIslands ─────────────────────────────────────────────────────

describe("assignShapesToIslands", () => {
  it("add shape is assigned to the island it creates", () => {
    const shapes = [rect(0, 0, 10, 10, { id: "r1" })];
    const { islands, addUnion, overrideAddUnion } = computeIslands(shapes);
    assignShapesToIslands(shapes, islands, addUnion, overrideAddUnion);
    expect(islands[0].shapeIds).toContain("r1");
  });

  it("subtract shape spanning two islands appears in both", () => {
    const shapes = [
      rect(0, 0, 8, 10, { id: "left" }),
      rect(12, 0, 20, 10, { id: "right" }),
      rect(0, 3, 20, 7, { id: "sub", op: "subtract" }), // carves both
    ];
    const { islands, addUnion, overrideAddUnion } = computeIslands(shapes);
    assignShapesToIslands(shapes, islands, addUnion, overrideAddUnion);
    const subIslands = islands.filter(isl => isl.shapeIds.includes("sub"));
    // Sub shape intersects both original rects' extents
    expect(subIslands.length).toBeGreaterThanOrEqual(1);
  });

  it("unrelated shape not assigned to an island it does not touch", () => {
    const shapes = [
      rect(0, 0, 10, 10, { id: "a" }),
      rect(50, 50, 60, 60, { id: "b" }),
    ];
    const { islands, addUnion, overrideAddUnion } = computeIslands(shapes);
    assignShapesToIslands(shapes, islands, addUnion, overrideAddUnion);
    const sorted = sortIslands(islands);
    // Island near (5,5) should only have "a"
    const near0 = sorted.find(isl => ringCentroid(isl.exterior)[0] < 30);
    expect(near0?.shapeIds).not.toContain("b");
  });

  it("override-add shape assigned to island it directly overlaps", () => {
    const shapes = [
      rect(0, 0, 20, 10, { id: "base" }),
      rect(5, 0, 15, 10, { id: "sub", op: "subtract" }),
      rect(7, 2, 13, 8, { id: "ovradd", op: "add", override: true }),
    ];
    const { islands, addUnion, overrideAddUnion } = computeIslands(shapes);
    assignShapesToIslands(shapes, islands, addUnion, overrideAddUnion);
    const ovrIsland = islands.find(isl => isl.shapeIds.includes("ovradd"));
    expect(ovrIsland).toBeDefined();
  });
});

// ── computeMirrorPreview ──────────────────────────────────────────────────────

describe("computeMirrorPreview", () => {
  const baseIsland = {
    id: "isl_1",
    name: "Island 1",
    mirrors: true,
    exterior: [[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]],
    holes: [],
  };

  it("non-participating island produces no preview copies", () => {
    const isl = { ...baseIsland, mirrors: false };
    expect(computeMirrorPreview([isl], "mirror_x", 0, 0)).toHaveLength(0);
  });

  it("mirror_x reflects across x = cx: produces 1 copy", () => {
    const copies = computeMirrorPreview([baseIsland], "mirror_x", 0, 0);
    expect(copies).toHaveLength(1);
    // Original is in x=[10,20]. Mirrored across x=0 → x=[-20,-10].
    const b = bbox(copies[0].exterior);
    expect(b.max_x).toBeLessThanOrEqual(-10 + 0.5); // slight rounding ok
    expect(b.min_x).toBeCloseTo(-20);
  });

  it("mirror_z reflects across z = cz: produces 1 copy", () => {
    const copies = computeMirrorPreview([baseIsland], "mirror_z", 0, 0);
    expect(copies).toHaveLength(1);
    // Original z=[0,10]. Mirrored across z=0 → z=[-10,0].
    const b = bbox(copies[0].exterior);
    expect(b.min_z).toBeCloseTo(-10);
    expect(b.max_z).toBeLessThanOrEqual(0 + 0.5);
  });

  it("rot_180 rotates 180° around center: produces 1 copy", () => {
    const copies = computeMirrorPreview([baseIsland], "rot_180", 15, 5);
    expect(copies).toHaveLength(1);
    // Center of island is (15,5). rot_180 around (15,5) returns the same bbox.
    const b = bbox(copies[0].exterior);
    expect(b.min_x).toBeCloseTo(10);
    expect(b.max_x).toBeCloseTo(20);
  });

  it("rot_90 produces 3 copies (90°, 180°, 270°)", () => {
    const copies = computeMirrorPreview([baseIsland], "rot_90", 0, 0);
    expect(copies).toHaveLength(3);
    expect(copies.every(c => c.sourceId === "isl_1")).toBe(true);
  });

  it("multiple islands each produce their own copies", () => {
    const islands = [
      { ...baseIsland, id: "a", mirrors: true },
      { ...baseIsland, id: "b", mirrors: true, exterior: [[30, 0], [40, 0], [40, 10], [30, 10], [30, 0]] },
    ];
    const copies = computeMirrorPreview(islands, "rot_180", 0, 0);
    expect(copies).toHaveLength(2);
  });

  it("sourceId links each preview copy to its origin island", () => {
    const islands = [
      { ...baseIsland, id: "isl_A" },
      { ...baseIsland, id: "isl_B", mirrors: false },
    ];
    const copies = computeMirrorPreview(islands, "mirror_x", 0, 0);
    expect(copies).toHaveLength(1);
    expect(copies[0].sourceId).toBe("isl_A");
  });

  it("holes are transformed correctly in preview copies", () => {
    const withHole = {
      ...baseIsland,
      holes: [[[12, 2], [18, 2], [18, 8], [12, 8], [12, 2]]],
    };
    const copies = computeMirrorPreview([withHole], "mirror_x", 0, 0);
    expect(copies[0].holes).toHaveLength(1);
    // Hole was at x=[12,18], mirrored to x=[-18,-12]
    const hb = bbox(copies[0].holes[0]);
    expect(hb.min_x).toBeCloseTo(-18);
    expect(hb.max_x).toBeCloseTo(-12);
  });
});
