"""Two-facet region categorisation derivation.

Implements ``docs/contracts/region-categorization.md``: every region gets a
``category`` (what it *is* in gameplay) and a list of ``roles`` (what it is *used
for* — rule wiring, conditional timing). Categories are **derived, never
persisted**; ``region_categories`` in ``xml_data.json`` is a user-override store
layered on top of this derivation (see :func:`categorize_regions`).

The single most important rule (contract §1): a region's ``category`` comes from
intrinsic gameplay signals — spawns, monuments, spawners, wool rooms, the
void-enforcement build structure — **never** from the mere fact that a filter is
applied to it. Filter targeting is recorded as a ``role`` instead.

The oracle for this module is ``tests/fixtures/region_categories/annealing_iv.json``
(author-verified).
"""
from __future__ import annotations

import re

# ── role vocabulary ───────────────────────────────────────────────────────────

# apply-rule events recorded as rule-wiring roles. These are the spatial
# edit/access events that participate in the category/role model; ``block_physics``,
# ``use`` and ``kit`` are mechanic-level and deliberately excluded from the wiring
# summary (they never change a region's category and only add noise).
_RULE_EVENTS = ("block", "block_break", "block_place", "enter")

# Role flags emitted before the rule-wiring entries, in this fixed order.
_FLAG_ORDER = ("rule_container", "rule_group", "time_gated")

# Region types that are compounds (resolved by recursion, never name-matched).
_COMPOUND_TYPES = frozenset(
    {"union", "complement", "negative", "intersect", "mirror", "translate"}
)

# Filter types that gate a rule on match time (→ ``time_gated`` role + duration).
_TIME_FILTER_TYPES = frozenset({"after", "time", "pulse"})

CATEGORIES = (
    "spawn", "observer_spawn", "wool_room", "monument",
    "wool_spawner", "build", "mechanic", "other",
)


# ── reference helpers ─────────────────────────────────────────────────────────

def _ref_id(ref) -> str:
    """Region/filter reference → id, accepting a string id or an inline dict."""
    if isinstance(ref, str):
        return ref
    if isinstance(ref, dict):
        return ref.get("id", "")
    return ""


def _is_synthetic(rid: str) -> bool:
    """Synthetic (parser-assigned) ids are anonymous children, never authored."""
    return "__anon_" in rid or "__apply_" in rid


def _child_ids(region: dict) -> list[str]:
    """String-id children of a compound (inline dicts tolerated for safety)."""
    return [rid for c in (region.get("children") or []) if (rid := _ref_id(c))]


def _iter_wools(data: dict) -> list[dict]:
    """Wools as a list of colour-grouped dicts, whether stored as list or dict."""
    wools = data.get("wools")
    if isinstance(wools, dict):
        return list(wools.values())
    if isinstance(wools, list):
        return wools
    return []


def _spawner_dispenses_wool(spawner: dict) -> bool:
    """A spawner is a wool objective only if it actually dispenses wool.

    A golden-apple / arrow / other-item spawner is a gameplay *mechanic*, not a
    wool source — its regions must not be read as wool spawner / wool room.
    """
    for item in spawner.get("items") or []:
        if "wool" in (item.get("material") or "").lower():
            return True
    return False


# Author-written apply messages are an explicit categorisation signal. Ordered
# most-specific first; "spawner" before "spawn" because it contains it.
_MESSAGE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("wool room", "wool rooms", "woolroom", "woolrooms"), "wool_room"),
    (("spawner",), "mechanic"),
    (("spawn",), "spawn"),
    (("enemy's base", "enemies' base", "opponent's base", "enemy team's base"), "spawn"),
)


def _message_category(message) -> str | None:
    """Map an apply rule's human message to a category, if it names one.

    Void/build/generic messages ("…edit the void!", "…interact with this block!")
    return None — build is derived structurally and the rest carry no identity.
    """
    if not isinstance(message, str):
        return None
    text = message.lower()
    for needles, category in _MESSAGE_RULES:
        if any(n in text for n in needles):
            return category
    return None


def _is_spawn_kit(kit_id: str) -> bool:
    """A kit id that names spawn protection/regen (resistance, regeneration in spawn).

    Spawn platforms lend a damage-resistance / regeneration kit while you stand in
    them (mushroom_gorge `spawn-protection`, `spawn-regen`). Excludes ``leave``/
    ``remove``/``reset`` kits, which fire *outside* spawn to strip that buff.
    """
    k = kit_id.lower()
    if any(x in k for x in ("leave", "remove", "reset", "exit", "outof")):
        return False
    return "spawn" in k


def _is_spawn_block_pattern(rule: dict, filters: dict) -> bool:
    """The spawn-floor protection pattern: break only a material + deny placement.

    Spawn platforms let players break only the spawn-floor blocks (iron) while
    placement is fully denied — a reliable spawn signal (rockymine).
    """
    bb, bp = rule.get("block_break"), rule.get("block_place")
    if not bb or not bp:
        return False
    breaks_material = bool(_filter_type_present(bb, filters, frozenset({"material"})))
    denies_place = bool(_filter_type_present(bp, filters, frozenset({"deny", "never"}))) \
        or bp not in filters and ("deny" in bp.lower() or "never" in bp.lower())
    return breaks_material and denies_place


# ── filter inspection ─────────────────────────────────────────────────────────

def _filter_type_present(fid: str, filters: dict, wanted: frozenset,
                         seen: set | None = None) -> dict | None:
    """Return the first descendant filter whose ``type`` is in ``wanted``.

    Walks the filter tree by id (``child`` / ``children`` references), so a
    ``void`` leaf wrapped in ``not``/``any``/``all`` is still found.
    """
    if seen is None:
        seen = set()
    if not fid or fid in seen:
        return None
    seen.add(fid)
    f = filters.get(fid)
    if not isinstance(f, dict):
        return None
    if f.get("type") in wanted:
        return f
    for ref in (f.get("child"), *(f.get("children") or [])):
        cid = _ref_id(ref)
        hit = _filter_type_present(cid, filters, wanted, seen)
        if hit:
            return hit
    return None


# ── main entry point ──────────────────────────────────────────────────────────

def derive_region_facets(data: dict) -> dict[str, dict]:
    """Derive ``{region_id: {"category", "roles"}}`` for every region.

    Output covers all regions (named *and* synthetic) so the region tree can
    colour any node; the categorization oracle only asserts on named regions.
    """
    regions: dict = data.get("regions", {}) or {}
    filters: dict = data.get("filters", {}) or {}

    # ── direct gameplay-signal sets ───────────────────────────────────────────
    spawn_ids: set[str] = {
        rid for s in (data.get("spawns") or [])
        if (rid := _ref_id(s.get("region")))
    }
    obs = data.get("observer_spawn") or {}
    observer_id = _ref_id(obs.get("region")) if obs else ""

    monument_ids: set[str] = set()
    wool_room_ids: set[str] = set()
    for wool in _iter_wools(data):
        if wool.get("wool_room_region"):
            wool_room_ids.add(wool["wool_room_region"])
        for mon in wool.get("monuments") or []:
            if mon.get("monument_region"):
                monument_ids.add(mon["monument_region"])

    # A spawner only yields wool objectives when it actually dispenses wool; a
    # spawner of golden apples / other items is a gameplay *mechanic*, and its
    # regions must not be read as wool spawners / rooms.
    wool_spawner_ids: set[str] = set()
    mechanic_ids: set[str] = set()
    for sp in (data.get("spawners") or []):
        spawn_region = sp.get("spawn_region")
        player_region = sp.get("player_region")
        if _spawner_dispenses_wool(sp):
            if spawn_region:
                wool_spawner_ids.add(spawn_region)
            if player_region:           # the wool *room* the spawner refills
                wool_room_ids.add(player_region)
        elif spawn_region:
            # Non-wool spawner (golden apple, dye, …): the dispenser point is a
            # mechanic. The *player_region* is just where players stand to collect —
            # often a real wool room the spawner feeds — so it keeps its own identity.
            mechanic_ids.add(spawn_region)

    # ── apply-rule wiring ─────────────────────────────────────────────────────
    rules_by_region: dict[str, list[tuple[str, str]]] = {}
    enter_only: dict[str, str] = {}      # region → excluded/allowed team token
    time_gated: dict[str, str] = {}      # region → duration token
    msg_hint: dict[str, str] = {}        # region → category from apply message text
    iron_spawn_ids: set[str] = set()     # break-only-material + deny-place ⇒ spawn
    spawn_kit_ids: set[str] = set()      # spawn-protection / spawn-regen kit ⇒ spawn
    placement_build_regions: set[str] = set()   # region used as a block-place filter ⇒ build
    action_mechanic_regions: set[str] = set()    # velocity/kit/lend_kit action ⇒ mechanic
    for rule in (data.get("apply_rules") or []):
        # A region used as the *filter* of a placement rule defines where building is
        # allowed (vertex's global `block_place="playable-area"`) ⇒ that region is build.
        # (Read independently of the rule's own region target, which may be absent.)
        for event in ("block_place", "block"):
            val = rule.get(event)
            if val and val in regions and val not in filters:
                placement_build_regions.add(val)
        rid = rule.get("region")
        if not rid:
            continue
        # A spawn-protection / spawn-regen kit (resistance + regeneration) marks a
        # spawn zone (mushroom_gorge `base-sides`). A `velocity` boost or any other
        # kit is a generic mechanic. (Exclude leave-/remove-spawn kits — those fire
        # *outside* spawn to strip the buff.)
        kit = rule.get("kit") or rule.get("lend_kit")
        if kit and _is_spawn_kit(kit):
            spawn_kit_ids.add(rid)
        elif rule.get("velocity") or kit:
            action_mechanic_regions.add(rid)
        for event in _RULE_EVENTS:
            fid = rule.get(event)
            if not fid:
                continue
            rules_by_region.setdefault(rid, []).append((event, fid))
            hit = _filter_type_present(fid, filters, _TIME_FILTER_TYPES)
            if hit:
                time_gated[rid] = hit.get("duration", "")
        enter = rule.get("enter")
        if isinstance(enter, str):
            if enter.startswith("only-"):
                enter_only.setdefault(rid, enter[len("only-"):])
            elif enter.startswith("not-"):
                wool_room_ids.add(rid)       # defender excluded → their wool room
        hint = _message_category(rule.get("message"))
        if hint:
            msg_hint.setdefault(rid, hint)
        if _is_spawn_block_pattern(rule, filters):
            iron_spawn_ids.add(rid)
    for rid in rules_by_region:
        rules_by_region[rid].sort(key=lambda ev: ev[0])

    ruled_regions = set(rules_by_region)

    # Renewable (regen) regions and velocity/kit-action regions are mechanics, but
    # never relabel a negative/complement rule-wrapper (it keeps rule_container).
    for ren in (data.get("renewables") or []):
        rid = ren.get("region_id")
        if rid:
            action_mechanic_regions.add(rid)
    # These are *weaker* identity signals than a wool/spawn name (a wool room can have
    # wool regen and still be a wool room), so they are applied after name heuristics —
    # they only claim regions nothing else could classify (portals, jump pads, regen).
    action_mechanic_ids = {
        rid for rid in action_mechanic_regions
        if (regions.get(rid) or {}).get("type") not in ("negative", "complement")
    }

    # ── build regions: void-enforcement structure + time-gated (contract §5) ──
    build_ids = _derive_build_ids(
        regions, filters, rules_by_region, set(time_gated), placement_build_regions)

    # ── category assignment by precedence (contract §4) ───────────────────────
    cat: dict[str, str | None] = {rid: None for rid in regions}

    def _set(ids, value):
        for rid in ids:
            if rid in cat and cat[rid] is None:
                cat[rid] = value

    if observer_id:
        cat[observer_id] = "observer_spawn"
    _set(spawn_ids, "spawn")
    _set(monument_ids, "monument")
    _set(wool_spawner_ids, "wool_spawner")
    _set(wool_room_ids, "wool_room")
    # Author-written apply messages are an explicit, high-signal hint ("…enter the
    # enemy's spawn!", "…edit the wool room!"); apply them before the structural
    # build sweep so a spawn-protection zone sitting inside the void-complement is
    # not swallowed as build.
    for rid, hint in msg_hint.items():
        if rid in cat and cat[rid] is None:
            cat[rid] = hint
    # "only break iron + deny placement" / a spawn-protection kit ⇒ spawn.
    _set(iron_spawn_ids, "spawn")
    _set(spawn_kit_ids, "spawn")
    _set(build_ids, "build")
    _set(mechanic_ids, "mechanic")

    # enter=only-<team> protected zones: disambiguate spawn vs wool room (§6).
    for rid, _team in enter_only.items():
        if cat.get(rid) is not None:
            continue
        name = rid.lower()
        if "spawn" in name:
            cat[rid] = "spawn"
        elif any(k in name for k in ("wool", "room", "monument")):
            cat[rid] = "wool_room"
        # else: neutral protected zone, leave for later passes.

    # name heuristics on primitives only (never on compounds) (§4.8).
    for rid, region in regions.items():
        if cat.get(rid) is not None:
            continue
        if region.get("type") in _COMPOUND_TYPES:
            continue
        cat[rid] = _name_heuristic(rid)

    # compound resolution (fill any still-uncategorised compounds) (§7), then
    # detect rule_group unions structurally (independent of how the union's own
    # category was assigned — message/signal pre-categorisation must not hide it).
    _resolve_compounds(regions, cat)
    rule_group_ids = _detect_rule_groups(regions, cat, ruled_regions)

    # renewable/velocity/kit mechanics are a *fallback* identity — claim a region
    # only if nothing else (signal, name, or its children) gave it one. This keeps a
    # `wool-rooms` union with wool regen a wool_room while still tagging portals /
    # jump pads / regen zones that would otherwise be `other`.
    for rid in action_mechanic_ids:
        if cat.get(rid) in (None, "other"):
            cat[rid] = "mechanic"

    # ── assemble output ───────────────────────────────────────────────────────
    out: dict[str, dict] = {}
    for rid, region in regions.items():
        category = cat.get(rid) or "other"
        roles: list[str] = []
        # flags first, in canonical order
        if region.get("type") == "negative":
            roles.append("rule_container")
        if rid in rule_group_ids:
            roles.append("rule_group")
        if rid in time_gated:
            dur = time_gated[rid]
            roles.append(f"time_gated={dur}" if dur else "time_gated")
        # then rule-wiring entries (already event-sorted)
        roles.extend(f"{event}={fid}" for event, fid in rules_by_region.get(rid, []))
        out[rid] = {"category": category, "roles": roles}
    return out


# ── derivation helpers ────────────────────────────────────────────────────────

def _name_heuristic(rid: str) -> str | None:
    """Last-resort category from a primitive's name (contract §4.8).

    ``build`` is deliberately *not* inferred from names like ``lane``/``bridge``:
    the contract (§5) derives build from void-enforcement structure, and a lane
    with no void parent is a movement mechanic, not build space. ``spawner`` maps
    to ``mechanic`` (a name-only spawner whose item we can't see is ambiguous;
    real wool spawners are caught by the item-gated signal), and is checked before
    ``spawn`` because it contains it.
    """
    name = rid.lower()
    if "monument" in name:
        return "monument"
    # "wr"/"wrs"/"wr2" are wool-room abbreviations, but must not match "wrapper"
    # (a void-mechanic region) — so match them only as whole tokens.
    tokens = re.split(r"[^a-z0-9]+", name)
    if "wool" in name or "room" in name or any(re.fullmatch(r"wr\d*s?", t) for t in tokens):
        return "wool_room"
    if "spawner" in name:
        return "mechanic"
    if "spawn" in name:
        return "spawn"
    return None


def _derive_build_ids(regions: dict, filters: dict,
                      rules_by_region: dict[str, list[tuple[str, str]]],
                      time_gated_ids: set[str],
                      placement_build_regions: set[str]) -> set[str]:
    """Build space, from three structural sources (contract §5).

    1. **Static (void-complement):** a ``negative``/``complement`` carved out by a
       ``void`` placement filter is the enforcement wrapper; its carved-out children
       are the buildable space.
    2. **Permissive placement:** a region used as the *filter* of a ``block_place``
       rule defines where building is allowed (vertex's ``block_place="playable-area"``
       global rule), so it *is* the build area.
    3. **Time-gated (dynamic):** a region whose block rule is gated by an
       ``after``/``time``/``pulse`` filter opens mid-match — it *is* the build
       region (anti-stalemate water lanes); it carries the ``time_gated`` role.

    All expand recursively into descendants, minus any member already claimed by a
    higher-precedence gameplay signal (filtered by ``_set`` at the call site).
    """
    build_roots: set[str] = set(time_gated_ids) | set(placement_build_regions)
    for rid, region in regions.items():
        typ = region.get("type")
        if typ not in ("negative", "complement"):
            continue
        if not _has_void_rule(rid, filters, rules_by_region):
            continue
        kids = _child_ids(region)
        # ``negative`` = "everywhere except X": the child X is the buildable space.
        # ``complement`` = "base − X − Y …": child[0] is the base (the void itself);
        # the *subtracted* children are the editable space carved out of it.
        build_roots.update(kids if typ == "negative" else kids[1:])

    # Build is "the not-void space that isn't a spawn or wool room" (§5): the
    # void-complement subtracts *every* editable region, so objectives (wool
    # rooms, spawns, monuments) that live inside it must be excluded. Signal-
    # categorised objectives are already protected (build only fills uncategorised
    # slots); here we also drop name-recognisable objectives, which are otherwise
    # still uncategorised when build is assigned.
    build_ids: set[str] = set()
    stack = list(build_roots)
    while stack:
        rid = stack.pop()
        if rid in build_ids or rid not in regions:
            continue
        hint = _name_heuristic(rid)
        if hint in ("spawn", "wool_room", "monument", "wool_spawner", "mechanic"):
            continue
        build_ids.add(rid)
        stack.extend(_child_ids(regions[rid]))
    return build_ids


def _has_void_rule(rid: str, filters: dict,
                   rules_by_region: dict[str, list[tuple[str, str]]]) -> bool:
    """A block-placement rule enforces void if its filter resolves to (or names) a void.

    Most maps reference a registry filter with a ``void`` leaf. Some inline the
    filter directly, in which case it isn't in the registry and only its
    descriptor string survives (e.g. ``deny(void)``, ``not-void``); we fall back
    to matching ``void`` in that descriptor in placement-rule context.
    """
    void = frozenset({"void"})
    for event, fid in rules_by_region.get(rid, []):
        if event not in ("block", "block_break", "block_place"):
            continue
        if _filter_type_present(fid, filters, void):
            return True
        if fid not in filters and "void" in fid.lower():
            return True
    return False


def _resolve_compounds(regions: dict, cat: dict[str, str | None]) -> None:
    """Resolve still-uncategorised compounds (§7).

    ``negative``  → ``other`` (whole-world enforcement wrapper, no identity).
    ``complement`` → category of its base (child[0]); subtracted children ignored.
    ``union``     → the category of its ≥2 uniform same-category peers (reached
                    through anonymous intermediate unions), else its first child.
    """
    resolving: set[str] = set()

    def resolve(rid: str) -> str:
        existing = cat.get(rid)
        if existing is not None:
            return existing
        region = regions.get(rid)
        if region is None or rid in resolving:
            return "other"
        resolving.add(rid)
        typ = region.get("type")
        kids = _child_ids(region)
        if typ == "negative":
            result = "other"
        elif typ == "complement":
            result = resolve(kids[0]) if kids else "other"
        elif typ == "union":
            # An uncategorised union over ≥2 uniform real-category peers takes that
            # category (the rule_group flag itself is set in a later pass).
            peers = _named_peers(rid, regions, resolve)
            cats = set(peers.values())
            if (len(peers) >= 2 and cats == {(c := next(iter(cats)))} and c != "other"):
                result = c
            else:
                result = resolve(kids[0]) if kids else "other"
        elif typ in ("mirror", "translate"):
            src = _ref_id(region.get("source_id"))
            result = resolve(src) if src else "other"
        else:  # intersect and any other compound: take the first operand
            result = resolve(kids[0]) if kids else "other"
        resolving.discard(rid)
        cat[rid] = result
        return result

    for rid in list(regions):
        if cat.get(rid) is None:
            resolve(rid)


def _detect_rule_groups(regions: dict, cat: dict[str, str | None],
                        ruled_regions: set[str]) -> set[str]:
    """Unions that batch a rule over ≥2 uniform real-category peers (§3).

    Structural, and independent of how the union's own category was assigned: a
    ``woolrooms`` union whose category came from its apply message is still the
    grouping that re-scopes the rule over the team wool rooms. Peers are the named,
    categorised descendants reached through anonymous intermediate unions (so a
    monument-sculpted complement like ``spawns`` is correctly *not* a rule_group).
    """
    rule_group_ids: set[str] = set()
    for rid, region in regions.items():
        if region.get("type") != "union" or rid not in ruled_regions:
            continue
        peers = _named_peers(rid, regions, lambda c: cat.get(c) or "other")
        cats = set(peers.values())
        if len(peers) >= 2 and cats == {(c := next(iter(cats)))} and c != "other":
            rule_group_ids.add(rid)
    return rule_group_ids


def _named_peers(rid: str, regions: dict, resolve) -> dict[str, str]:
    """Named, categorised descendants reached through anonymous intermediate unions.

    A named child is a terminal peer (record its category). An *anonymous* child
    that is itself a ``union`` is descended into. Any other anonymous child
    (a complement/negative/primitive) is opaque and contributes no peer — this is
    what keeps a monument-sculpted complement (``spawns``) from being a rule_group.
    """
    peers: dict[str, str] = {}
    seen: set[str] = set()

    def walk(node_id: str) -> None:
        region = regions.get(node_id)
        if region is None:
            return
        for child in _child_ids(region):
            if child in seen:
                continue
            seen.add(child)
            if not _is_synthetic(child):
                peers[child] = resolve(child)
            elif (regions.get(child) or {}).get("type") == "union":
                walk(child)
            # else: opaque anonymous non-union child → no peer

    walk(rid)
    return peers


def categorize_regions(data: dict) -> dict[str, str]:
    """Flat ``{region_id: category}`` map, with ``region_categories`` overrides.

    Back-compat shape for the region-tree encoder. The two-facet detail is
    available via :func:`derive_region_facets`. User overrides in
    ``data["region_categories"]`` win over the derivation (contract §10).
    """
    facets = derive_region_facets(data)
    cats = {rid: facet["category"] for rid, facet in facets.items()}
    for category, ids in (data.get("region_categories") or {}).items():
        for rid in ids:
            cats[rid] = category
    return cats
