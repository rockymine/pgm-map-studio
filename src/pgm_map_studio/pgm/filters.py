"""Filter class hierarchy for PGM XML filters.

All filters carry an ``id`` field.  Composite filters (all/any/one) store
children as ID strings into the flat filter registry — identical pattern to
composite regions.  Single-child wrappers (not/deny/allow) store their child
as a single ID string.  Leaf filters store their specific match parameters.

``FilterRef`` represents a ``<filter id="ref"/>`` element: a reference to
another named filter.  It is resolved but never itself registered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass
class Filter:
    id: str = ""
    filter_type: str = "unknown"


# ---------------------------------------------------------------------------
# Combiners — multiple children stored as ID strings
# ---------------------------------------------------------------------------

@dataclass
class AllFilter(Filter):
    """ALLOW only if ALL children allow (AND)."""
    children: list[str] = field(default_factory=list)
    filter_type: str = "all"


@dataclass
class AnyFilter(Filter):
    """ALLOW if ANY child allows (OR)."""
    children: list[str] = field(default_factory=list)
    filter_type: str = "any"


@dataclass
class OneFilter(Filter):
    """ALLOW only if exactly ONE child allows (XOR)."""
    children: list[str] = field(default_factory=list)
    filter_type: str = "one"


# ---------------------------------------------------------------------------
# Single-child wrappers
# ---------------------------------------------------------------------------

@dataclass
class NotFilter(Filter):
    """Logical NOT of one child filter."""
    child: str = ""
    filter_type: str = "not"


@dataclass
class DenyFilter(Filter):
    """Convert child ALLOW → DENY; child DENY → ABSTAIN."""
    child: str = ""
    filter_type: str = "deny"


@dataclass
class AllowFilter(Filter):
    """Convert child ALLOW → ALLOW; child DENY → ABSTAIN."""
    child: str = ""
    filter_type: str = "allow"


# ---------------------------------------------------------------------------
# Leaf matchers
# ---------------------------------------------------------------------------

@dataclass
class TeamFilter(Filter):
    """Player's team matches.  ``team`` is the team ID (text content of the element)."""
    team: str = ""
    filter_type: str = "team"


@dataclass
class MaterialFilter(Filter):
    """Block/item material matches.  ``material`` is a name or ``name:damage`` string."""
    material: str = ""
    filter_type: str = "material"


@dataclass
class VoidFilter(Filter):
    """Block is void (air at Y=0)."""
    filter_type: str = "void"


@dataclass
class CauseFilter(Filter):
    """Event cause matches (``player``, ``world``, ``explosion``, ``trample``, etc.)."""
    cause: str = ""
    filter_type: str = "cause"


@dataclass
class BlocksFilter(Filter):
    """Block matches the original map state inside a region.

    ``region`` — region ID whose original block state is compared.
    ``child``  — ID of the material/combiner filter that tests the block.
    """
    region: str = ""
    child: str = ""
    filter_type: str = "blocks"


@dataclass
class CarryingFilter(Filter):
    """Player is carrying a specific item anywhere in their inventory."""
    material: str = ""
    damage: Optional[int] = None
    enchantments: str = ""
    ignore_metadata: bool = False
    ignore_durability: bool = True
    filter_type: str = "carrying"


@dataclass
class WearingFilter(Filter):
    """Player is wearing a specific armor piece."""
    material: str = ""
    damage: Optional[int] = None
    ignore_metadata: bool = False
    filter_type: str = "wearing"


@dataclass
class HoldingFilter(Filter):
    """Player is holding a specific item in hand."""
    material: str = ""
    damage: Optional[int] = None
    filter_type: str = "holding"


@dataclass
class AliveFilter(Filter):
    """Player is alive (not dead / observing)."""
    filter_type: str = "alive"


@dataclass
class DeadFilter(Filter):
    """Player is dead."""
    filter_type: str = "dead"


@dataclass
class ParticipatingFilter(Filter):
    """Player is participating (on a team, in the match)."""
    filter_type: str = "participating"


@dataclass
class ObservingFilter(Filter):
    """Player is observing."""
    filter_type: str = "observing"


@dataclass
class MatchRunningFilter(Filter):
    """Match is currently running."""
    filter_type: str = "match-running"


@dataclass
class MatchStartedFilter(Filter):
    """Match has started (includes running and finished)."""
    filter_type: str = "match-started"


@dataclass
class GroundedFilter(Filter):
    """Player is on the ground."""
    filter_type: str = "grounded"


@dataclass
class NeverFilter(Filter):
    """Always denies (static false)."""
    filter_type: str = "never"


@dataclass
class AlwaysFilter(Filter):
    """Always allows (static true)."""
    filter_type: str = "always"


@dataclass
class TimeFilter(Filter):
    """Match has been running for at least ``duration``."""
    duration: str = ""
    filter_type: str = "time"


@dataclass
class AfterFilter(Filter):
    """Allows after another filter first becomes true, with a delay.

    ``filter_ref`` — ID of the trigger filter.
    ``duration``   — delay after trigger (e.g. ``"0.5s"``).
    """
    filter_ref: str = ""
    duration: str = ""
    filter_type: str = "after"


@dataclass
class PulseFilter(Filter):
    """Periodic pulsing signal.

    ``period``     — cycle length (e.g. ``"0.1s"``).
    ``duration``   — how long the pulse is active each cycle.
    ``filter_ref`` — optional additional condition (``filter`` attribute).
    """
    period: str = ""
    duration: str = ""
    filter_ref: str = ""
    filter_type: str = "pulse"


@dataclass
class OffsetFilter(Filter):
    """Check a filter at a coordinate offset from the current block.

    ``vector`` — offset string, e.g. ``"~0,~-1,~0"`` (one below) or absolute.
    ``child``  — ID of the material/filter to test at that position.
    """
    vector: str = ""
    child: str = ""
    filter_type: str = "offset"


@dataclass
class VariableFilter(Filter):
    """Match a PGM variable value or range.

    ``var``   — variable name.
    ``value`` — exact value, range ``"1.."`` (min only), or ``"[0,5]"``.
    ``team``  — optional team scope for team-scoped variables.
    """
    var: str = ""
    value: str = ""
    team: str = ""
    filter_type: str = "variable"


@dataclass
class CompletedFilter(Filter):
    """CTW/DTC objective (wool/monument) has been completed.

    ``objective`` — the objective id (text content of the element).
    """
    objective: str = ""
    filter_type: str = "completed"


@dataclass
class ObjectiveFilter(Filter):
    """Legacy ``<objective>`` filter (deprecated, use ``<completed>``)."""
    objective: str = ""
    filter_type: str = "objective"


@dataclass
class FilterRef(Filter):
    """Reference to another named filter via ``<filter id="ref-id"/>``.

    This object is never inserted into the flat filter registry — it is resolved
    to the target filter's ID and that ID is stored in the parent's child field.
    """
    ref_id: str = ""
    filter_type: str = "filter"


@dataclass
class KillStreakFilter(Filter):
    """Player's current kill streak matches a count or range."""
    min: Optional[int] = None
    max: Optional[int] = None
    count: Optional[int] = None
    filter_type: str = "kill-streak"


@dataclass
class ClassFilter(Filter):
    """Player has selected this class."""
    name: str = ""
    filter_type: str = "class"


@dataclass
class RegionFilter(Filter):
    """Player/block is inside this region (used as a filter, not for spatial rules)."""
    region: str = ""
    filter_type: str = "region"


@dataclass
class PlayerFilter(Filter):
    """Player count in a region."""
    min: Optional[int] = None
    max: Optional[int] = None
    filter_type: str = "players"


@dataclass
class SpawnFilter(Filter):
    """Entity is a specific mob/entity type spawn event."""
    mob: str = ""
    filter_type: str = "spawn"
