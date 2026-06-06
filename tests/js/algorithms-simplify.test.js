import { describe, it, expect } from "vitest";
import { simplifyVW } from "../../src/pgm_map_studio/studio/static/algorithms/simplify.js";

describe("simplifyVW", () => {
  it("returns input unchanged when 2 or fewer vertices", () => {
    expect(simplifyVW([], 1)).toEqual([]);
    expect(simplifyVW([[0, 0]], 1)).toEqual([[0, 0]]);
    expect(simplifyVW([[0, 0], [1, 1]], 1)).toEqual([[0, 0], [1, 1]]);
  });

  it("always preserves first and last vertex", () => {
    const pts = [[0, 0], [1, 0.01], [2, 0], [3, 100]];
    const result = simplifyVW(pts, 100);
    expect(result[0]).toEqual([0, 0]);
    expect(result[result.length - 1]).toEqual([3, 100]);
  });

  it("removes a collinear mid-point at any tolerance > 0", () => {
    // Three collinear points: the middle one forms a zero-area triangle.
    const pts = [[0, 0], [5, 0], [10, 0]];
    const result = simplifyVW(pts, 0.001);
    expect(result).toHaveLength(2);
    expect(result).toContainEqual([0, 0]);
    expect(result).toContainEqual([10, 0]);
  });

  it("keeps a vertex that forms a large triangle area", () => {
    const pts = [[0, 0], [5, 100], [10, 0]];
    // Triangle area = 0.5 * base * height = 0.5 * 10 * 100 = 500
    const result = simplifyVW(pts, 100);
    expect(result).toHaveLength(3); // all three preserved
  });

  it("removes a low-area bump but keeps a high-area peak", () => {
    // Baseline + small bump (area ≈ 1) + large peak (area = 50)
    const pts = [
      [0, 0],
      [5, 0.4],   // small bump — triangle area ≈ 1
      [10, 0],
      [15, 10],   // large peak — triangle area ≈ 50
      [20, 0],
    ];
    const result = simplifyVW(pts, 5); // removes bump, keeps peak
    expect(result).not.toContainEqual([5, 0.4]);
    expect(result).toContainEqual([15, 10]);
  });

  it("with tolerance=0 nothing is removed (all areas > 0 for non-collinear)", () => {
    const pts = [[0, 0], [1, 1], [2, 0], [3, 2], [4, 0]];
    const result = simplifyVW(pts, 0);
    expect(result).toHaveLength(pts.length);
  });

  it("very high tolerance collapses to just first and last", () => {
    const pts = [[0, 0], [2, 3], [5, 1], [8, 4], [10, 0]];
    const result = simplifyVW(pts, 1e9);
    expect(result[0]).toEqual([0, 0]);
    expect(result[result.length - 1]).toEqual([10, 0]);
    // Interior points removed
    expect(result.length).toBeLessThan(pts.length);
  });

  it("does not mutate the input array", () => {
    const pts = [[0, 0], [5, 0.1], [10, 0]];
    const copy = pts.map(p => [...p]);
    simplifyVW(pts, 1);
    expect(pts).toEqual(copy);
  });

  it("real-world: simplifies a rough circle to fewer points", () => {
    // Generate 64 points on a circle of radius 50, with slight noise.
    const pts = Array.from({ length: 64 }, (_, i) => {
      const a = (2 * Math.PI * i) / 64;
      return [Math.round(50 * Math.cos(a)), Math.round(50 * Math.sin(a))];
    });
    const simplified = simplifyVW(pts, 10);
    expect(simplified.length).toBeLessThan(pts.length);
    expect(simplified.length).toBeGreaterThan(2);
  });
});
