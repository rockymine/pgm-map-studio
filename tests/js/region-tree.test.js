import { describe, expect, it, vi } from "vitest";

import { RegionRegistry } from "../../src/pgm_map_studio/studio/static/region/region-registry.js";
import {
  applyRegionPatchToNode,
  findRegionNode,
  getRegionGroups,
  registerRegionGroups,
  regionIdExists,
} from "../../src/pgm_map_studio/studio/static/region/region-tree.js";

function tree() {
  return {
    groups: [
      {
        name: "spawn",
        label: "Spawn Regions",
        regions: [{
          id: "spawn-root",
          type: "union",
          children: [{ id: "spawn-child", type: "cuboid", children: [] }],
        }],
      },
      {
        name: "wool",
        label: "Wool Regions",
        regions: [{ id: "wool-room", type: "cylinder", children: [] }],
      },
    ],
  };
}

describe("region tree helpers", () => {
  it("filters canonical groups without rebuilding region nodes", () => {
    const data = tree();
    const groups = getRegionGroups(data, "spawn");

    expect(groups).toHaveLength(1);
    expect(groups[0]).toBe(data.groups[0]);
    expect(groups[0].regions[0].children[0].id).toBe("spawn-child");
  });

  it("registers each root once and preserves child parent links", () => {
    const onSelectionChange = vi.fn();
    const registry = new RegionRegistry({ onSelectionChange });

    registerRegionGroups(registry, getRegionGroups(tree(), "spawn"));
    registry.select("spawn-child");
    registry.renameNode("spawn-child", "renamed-child");
    registry.unregister("renamed-child");
    registry.select("spawn-root");

    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ id: "spawn-root" }),
      ["spawn-root"],
    );
  });

  it("finds nested nodes and detects duplicate IDs", () => {
    const groups = tree().groups;

    expect(findRegionNode(groups, "spawn-child")?.type).toBe("cuboid");
    expect(regionIdExists(groups, "wool-room")).toBe(true);
    expect(regionIdExists(groups, "wool-room", "wool-room")).toBe(false);
    expect(regionIdExists(groups, "missing")).toBe(false);
  });

  it("applies local coordinate patch data without reloading the tree", () => {
    const node = {
      id: "spawn-child",
      type: "cylinder",
      bounds: { min_x: 0, min_z: 0, max_x: 2, max_z: 2 },
      coords: { base_x: 1, base_y: 10, base_z: 1, radius: 1, height: 4 },
    };

    applyRegionPatchToNode(
      node,
      { coords: { radius: 3 } },
      { bounds: { min_x: -2, min_z: -2, max_x: 4, max_z: 4 } },
    );

    expect(node.coords.radius).toBe(3);
    expect(node.bounds).toEqual({ min_x: -2, min_z: -2, max_x: 4, max_z: 4 });
  });
});
