// GENERATED from pgm_map_studio.schemas — DO NOT EDIT.
// Regenerate: python tools/generate_ts_contract.py

export interface Bounds {
  min_x: number;
  min_z: number;
  max_x: number;
  max_z: number;
}

export interface Polygon2d {
  exterior: number[][];
  holes?: number[][][];
}

export interface RegionTreeNode {
  id: string;
  type: string;
  label: string;
  bounds: Bounds | null;
  coords: Record<string, unknown> | null;
  is_negative: boolean;
  synthetic_id: boolean;
  children: RegionTreeNode[];
  source: RegionTreeNode | null;
  polygon_2d?: Polygon2d | null;
}

export interface RegionGroup {
  name: string;
  label: string;
  regions: RegionTreeNode[];
}

export interface RegionTreeResponse {
  groups: RegionGroup[];
  bounding_box?: Bounds | null;
}
