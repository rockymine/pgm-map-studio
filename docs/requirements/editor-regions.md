# Requirements: Regions

**Semantic purpose:** Audit the complete spatial registry. Verify that every region has been assigned and that no regions are missing or mispositioned. This activity does not author new regions; all regions are created during prior steps.

---

## Sub-step 1: Region Inventory

**User requirements**
- Review all regions with their type, bounds, and owning activity/entity.
- No inputs required unless the user edits a region directly — editing navigates back to the originating activity.

**System requirements**
- Display the complete region registry, flat, keyed by ID.
- For each region: type, spatial attributes, owning activity, and whether it carries a direct apply rule or is an intermediate building block (child of another composite).
- Region types to display:

| Family | Types |
|---|---|
| Primitive | rectangle, cuboid, cylinder, circle, sphere, block/point |
| Composite | union, negative, complement, intersect |
| Transform | mirror, translate |
| Special | half, above, everywhere, reference |

- For composite regions: show the full ID chain of children, resolving each child ID to its type and bounds.

---

## Sub-step 2: Unassigned Region Inspection

**User requirements**
- Review any regions present in the imported XML that no editor step claimed.
- For each unassigned region: decide to assign it to an activity, edit it inline (navigates to the appropriate activity), or explicitly mark it as intentionally unclaimed.

**System requirements**
- Detect regions from the imported XML that have no owning activity after all prior steps complete.
- Surface unassigned regions prominently as requiring user attention.
- Allow the user to annotate an unassigned region as intentional, which suppresses the warning.

---

## Sub-step 3: Symmetry Violation Review

**User requirements**
- Review any regions that should be paired by the confirmed symmetry axis but whose counterpart is missing or outside positional tolerance.
- For each violation: decide to fix the counterpart (navigates to the originating activity), override the expected pairing, or dismiss the warning.

**System requirements**
- For each region with a confirmed counterpart expectation (mirror/translate), check that the counterpart exists and falls within positional tolerance.
- Surface violations as warnings identifying the specific region ID and the computed expected counterpart position.
- Allow the user to dismiss individual violations.
- If symmetry is `none`, this sub-step is suppressed entirely.

---

## Step-level system requirements

- Regions is the terminal audit step; it depends on all prior activities.
- No new regions or rules are created here; this step is read and review only.
- A map may be exported before Regions is reviewed; Regions is an audit aid, not an export gate.
