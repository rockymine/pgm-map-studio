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

export interface WiringEntry {
  event: string;
  value: string;
  rule_id?: string | null;
}

export interface AuthoringNode {
  id: string;
  type: string;
  label: string;
  category: string;
  bounds: Bounds | null;
  coords: Record<string, unknown> | null;
  member_ids?: string[];
  wiring?: WiringEntry[];
  polygon_2d?: Polygon2d | null;
}

export interface RegionAuthoringResponse {
  primitives: AuthoringNode[];
  composed: AuthoringNode[];
  bounding_box?: Bounds | null;
}

export interface BuildabilityResponse {
  bbox: Bounds;
  width: number;
  height: number;
  classes: string[];
  colors: Record<string, string>;
  counts: Record<string, number>;
  rows: string[];
  has_y0: boolean;
}

export interface WoolSource {
  type: string;
  color: string;
  x: number;
  y: number;
  z: number;
  count: number;
}

export interface WoolColorSummary {
  color: string;
  total: number;
  source_types: string[];
  repeatable: boolean;
  one_time: boolean;
  sources: WoolSource[];
}

export interface WoolSourcesResponse {
  colors: WoolColorSummary[];
  have_layers: boolean;
}

export interface WoolAvailabilityEntry {
  wool_id: string;
  color: string;
  obtainable: boolean;
  repeatable: boolean;
  one_time: boolean;
  severity: string;
  message: string;
  source_types: string[];
}

export interface WoolAvailabilityResponse {
  wools: WoolAvailabilityEntry[];
  have_layers: boolean;
}

export interface WoolSuggestion {
  color: string;
  total: number;
  source_types: string[];
}

export interface WoolSuggestionsResponse {
  suggestions: WoolSuggestion[];
  have_layers: boolean;
}

export interface NavPoint {
  kind: string;
  name: string;
  x: number;
  z: number;
  component: number;
}

export interface IsolatedPoint {
  kind: string;
  name: string;
}

export interface TraversabilityResponse {
  connected: boolean;
  component_count: number;
  severity: string;
  message: string;
  have_layers: boolean;
  points: NavPoint[];
  isolated: IsolatedPoint[];
}

export interface XZ {
  x?: number | string | null;
  z?: number | string | null;
}

export interface XYZ {
  x?: number | string | null;
  y?: number | string | null;
  z?: number | string | null;
}

export interface Bounds2d {
  min: XZ;
  max: XZ;
}

export interface Team {
  id: string;
  name?: string;
  color?: string;
  dye_color?: string;
  max_players?: number;
  min_players?: number;
}

export interface Author {
  uuid?: string;
  role?: string;
  contribution?: string | null;
  name?: string | null;
}

export interface KitItem {
  slot?: number | null;
  material?: string;
  amount?: number | null;
  damage?: number | null;
  unbreakable?: boolean | null;
  team_color?: boolean | null;
  enchantments?: string | null;
}

export interface KitArmor {
  slot_name?: string;
  material?: string;
  unbreakable?: boolean | null;
  team_color?: boolean | null;
  enchantments?: string | null;
}

export interface Kit {
  id: string;
  items?: KitItem[];
  armor?: KitArmor[];
}

export interface Region {
  id?: string;
  type: string;
  bounds_2d?: Bounds2d | null;
  min?: XYZ | null;
  max?: XYZ | null;
  base?: XYZ | null;
  center?: XZ | null;
  origin?: XYZ | null;
  position?: XYZ | null;
  radius?: number | string | null;
  height?: number | string | null;
  children?: string | Region[] | null;
  source_id?: string | null;
  normal?: XYZ | null;
  offset?: XYZ | null;
  ref_id?: string | null;
  y?: number | string | null;
}

export interface Spawn {
  team?: string;
  kit?: string | null;
  yaw?: number;
  region?: string | Region | null;
}

export interface Monument {
  id?: string;
  team?: string;
  location?: XYZ | null;
  monument_region?: string | null;
}

export interface Wool {
  id?: string;
  color?: string;
  location?: XYZ | null;
  wool_room_region?: string | null;
  monuments?: Monument[];
  team?: string | null;
}

export interface DropItem {
  material?: string;
  damage?: number | null;
  amount?: number | null;
  chance?: number | null;
}

export interface Spawner {
  spawn_region?: string | null;
  player_region?: string | null;
  delay?: string | null;
  max_entities?: number | null;
  items?: DropItem[];
}

export interface Renewable {
  region_id?: string | null;
  rate?: number | null;
  renew_filter?: string | null;
  replace_filter?: string | null;
  grow?: boolean | null;
}

export interface BlockDropRule {
  region_id?: string | null;
  filter_id?: string | null;
  replacement?: string | null;
  wrong_tool?: boolean | null;
  items?: DropItem[];
}

export interface Filter {
  id?: string;
  type: string;
  children?: string[] | null;
  child?: string | null;
  region?: string | null;
}

export interface ApplyRule {
  id?: string | null;
  region?: string | null;
  enter?: string | null;
  leave?: string | null;
  block?: string | null;
  block_place?: string | null;
  block_break?: string | null;
  block_physics?: string | null;
  block_place_against?: string | null;
  use?: string | null;
  filter?: string | null;
  kit?: string | null;
  lend_kit?: string | null;
  velocity?: string | null;
  message?: string | null;
}

export interface ObserverSpawn {
  team?: string;
  kit?: string | null;
  yaw?: number | null;
  region?: string | Region | null;
}

export interface MapProject {
  name?: string;
  version?: string | null;
  gamemode?: string | null;
  objective?: string | null;
  max_build_height?: number | null;
  authors?: Author[];
  kits?: Kit[];
  teams?: Team[];
  spawns?: Spawn[];
  observer_spawn?: ObserverSpawn | null;
  wools?: Wool[];
  spawners?: Spawner[];
  renewables?: Renewable[];
  block_drop_rules?: BlockDropRule[];
  filters?: Record<string, Filter>;
  regions?: Record<string, Region>;
  apply_rules?: ApplyRule[];
}

export interface Bbox {
  min_x: number;
  min_z: number;
  max_x: number;
  max_z: number;
}

export interface Center {
  cx?: number;
  cz?: number;
}

export interface SketchSetup {
  bbox?: Bbox | null;
  center?: Center | null;
  mirror_mode?: "mirror_x" | "mirror_z" | "rot_180" | "rot_90";
}

export interface BezierControl {
  in?: number[] | null;
  out?: number[] | null;
}

export interface Shape {
  id?: string;
  type: string;
  operation?: string;
  override?: boolean;
  min_x?: number | null;
  min_z?: number | null;
  max_x?: number | null;
  max_z?: number | null;
  center_x?: number | null;
  center_z?: number | null;
  radius?: number | null;
  vertices?: number[][] | null;
  controls?: Record<string, BezierControl> | null;
}

export interface IslandMeta {
  id?: string;
  name?: string;
  mirrors?: boolean;
  shapeIds?: string[];
}

export interface SketchLayout {
  shapes?: Shape[];
  islands?: IslandMeta[];
}

export interface SketchProject {
  id?: string;
  gamemode?: string;
  name?: string;
  version?: string;
  objective?: string;
  authors?: Author[];
  setup?: SketchSetup | null;
  layout?: SketchLayout | null;
  export_slug?: string | null;
}
