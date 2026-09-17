# 3D Container Loading DSS - Reference Guide

This document is the reference for how the system is to be built, end to end: what it reads, how it solves the packing problem, what rules it enforces, what it produces, and how the whole thing is architected as a web application around that solver. This is a **full-implementation guide, not a phased MVP** - the solver section (Section 5) is the complete target algorithm, directly adapted from Ma et al.'s block-building + genetic-algorithm + simulated-annealing 3D-CLP method (the source paper this system is based on), with this warehouse's own practical constraints (Section 4.4) and LIFO/LCL handling (Section 4.5) integrated directly into that same algorithm rather than bolted on as a separate simplified pass. There is no "build the simple version first, add the paper's method later" split anywhere in this guide: every technique the paper uses - block generation, the improved placeable-point strategy with corner-first seeding and contact-ratio scoring, the genetic algorithm with elitism and a dynamic mutation rate, and simulated annealing as the GA's local-refinement operator - is part of the one algorithm Section 5 specifies, with this warehouse's constraints and LIFO ordering woven into each stage at the point where the paper's own architecture already provides a hook for it (the permitted-posture set, the per-placement rejection chain, the fitness/penalty function, and the encoding itself).

## Contents

1. [Overview](#1-overview)
2. [Inputs](#2-inputs)
3. [Solving Procedure (End-to-End)](#3-solving-procedure-end-to-end)
4. [Problem Modeling](#4-problem-modeling)
5. [Solving Methods](#5-solving-methods)
6. [Output](#6-output)
7. [Tunable Parameters Reference](#7-tunable-parameters-reference-config-module)
8. [System Architecture (Web Application)](#8-system-architecture-web-application)
9. [Ideas Beyond the Paper (Not Yet Implemented)](#9-ideas-beyond-the-paper-not-yet-implemented)

---

## 1. Overview

### 1.1 Business context

A wood furniture bonded warehouse (tables, beds, chairs, and similar items) loads outbound shipping containers by hand, and today that process leans almost entirely on one Supervisor's experience: which cartons go where, in what order, stacked how. Because there is no systematic check before loading starts, it is common to discover partway through that the current arrangement will not work well - cartons already placed have to be pulled back out and redone to get a better fit. This rework costs time and money on every container that needs it. It also means the skill is tacit and hard to transfer: new staff learn by shadowing an experienced Supervisor rather than from any written procedure, so onboarding a new loader is slow and inconsistent.

These two problems - avoidable rework, and undocumented tribal knowledge - are what a decision support system (DSS) is meant to fix: propose a loading plan up front, before anyone touches a carton, so the arrangement is right the first time and the reasoning behind it is visible to anyone, not just the Supervisor who has done it for years.

### 1.2 What the system solves

A **3D Container Loading Problem (3D-CLP)**: given (a) a packing list of cartons to ship, (b) the physical/handling attributes of each carton type, and (c) the internal dimensions and payload limit of one specific, already-chosen container, produce a physically valid loading plan that places **every** carton - packing them as densely as the constraints allow, but never at the cost of leaving cartons out (Section 4.3) - while respecting weight capacity, orientation restrictions, no-overlap, stacking/support rules, load-bearing limits, and center-of-gravity balance (Section 4.4).

This warehouse ships both **FCL** (one container, one customer) and **LCL** (one container consolidating several customers, each unloaded at a different stop), so the system handles both: when a packing list carries more than one customer, LIFO unload ordering becomes an active constraint so that no customer's cargo is trapped behind cargo that comes off later. Which mode applies is detected automatically from the packing list, never selected by hand - Section 4.5 covers the detection rule and the full LIFO mechanism.

### 1.3 What is fixed before the algorithm runs

Decided upstream, by a person or an earlier step in the workflow, not searched over by this system:

- **The container type.** The Supervisor selects the container per the shipment's Booking Notes before the solver ever runs. Accordingly, this system takes **one container specification per run** and packs against it; it does not evaluate multiple candidate container types and pick a "best" one (see Sections 2.1 and 3 for how this simplifies the pipeline).
- **The carton contents.** The algorithm places cartons, not the individual furniture pieces inside them. How many pieces are folded into a given carton is irrelevant to packing and is not modeled.

### 1.4 What is not fixed / what the algorithm decides

For every carton - which orientation to place it in, and its (x, y, z) position inside the container - subject to the constraints in Section 4.4, so as to **place every carton** (Section 4.3) while keeping the load stable and balanced enough to move safely. Fill rate is still measured and still matters, but as a secondary, tie-breaking concern - see Section 4.3 for why this ordering, not fill-rate maximization, is the actual objective the solver optimizes for.

### 1.5 The DSS flow this guide assumes

Steps 1, 3, and 5's presentation layer are Supervisor/UI steps around the core solver; the solver itself is Sections 2-5.

1. The Supervisor selects or uploads a packing list to ship - a single PO or a batch of POs.
2. The system resolves every line against `item_master` to pull each carton type's physical and handling attributes (dimensions, weight, stacking behavior).
3. The Supervisor selects the container to load against, per the shipment's Booking Notes (already decided, per Section 1.3).
4. The system runs the solver (Sections 3-5) against that single confirmed input set.
5. The system produces the loading plan: a 3D model of the arrangement plus the operational metrics that matter for the loading crew and for measuring performance (fill rate, weight used, unplaced cartons) - Section 6 describes exactly what this includes today; a layer-by-layer walkthrough view is a natural extension of the same output data (Section 6.3) for a future UI.

---

## 2. Inputs

The system reads 3 inputs that together form a small relational join: a **packing list** (the fact table, one row per PO line), an **item master** (carton attributes, joined in by `Item_ID`), and a **single container specification** (not joined - it's the fixed context the whole run packs against, per Section 1).

### 2.1 `container_spec.csv` (or a single selected row from a container catalog)

Describes the **one** container type this run packs against. The system does not iterate over multiple container types and pick the best (see Sections 1.3 and 3) - if a catalog with multiple rows is used upstream to let the Supervisor pick, only the selected row is ever passed into the solver.

| Field | Type | Meaning |
|---|---|---|
| `Container_Type` | str | Identifier, e.g. 40HC |
| `Internal_Length_cm` | float | Internal usable length, the X axis |
| `Internal_Width_cm` | float | Internal usable width, the Y axis |
| `Internal_Height_cm` | float | Internal usable height, the Z axis |
| `Max_Weight_kg` | float | Maximum payload weight |

**Validation**: all dimensions and `Max_Weight_kg` must be greater than 0; exactly one container is active per run.

### 2.2 `packing_list.csv`

One row per PO line (a PO can have several lines; a line can request multiple cartons of the same item). This replaces order-header/order-line bookkeeping with the single flat structure the warehouse actually works from.

| Field | Type | Meaning |
|---|---|---|
| `Item_ID` | str | Foreign key to `item_master.Item_ID` |
| `PO_No` | str | Purchase order number this line belongs to |
| `Customer_Code` | str | Which customer this line's cargo belongs to. **Optional**: omit entirely (or leave every row at the same value) for a single-customer shipment - see Section 4.5 for how the system uses this to distinguish FCL from LCL automatically |
| `Description` | str | Human-readable name, carried along from `item_master` for readability without a join |
| `Qty_Pcs` | int | Number of furniture pieces on this line. Reference/reconciliation field only - not used by the solver, since the solver places cartons, not pieces (Section 1.3) |
| `Qty_Cartons` | int | Number of physical cartons requested on this line - this is the quantity the solver actually expands into boxes (Section 2.4) |

**Validation**: `Qty_Cartons` and `Qty_Pcs` must be positive integers. Every `Item_ID` must exist in `item_master.csv` (unmatched references raise a validation error rather than being dropped).

**Row order is meaningful, not incidental**: unlike the other fields, which the parser is free to reorder or re-sort as convenient, `packing_list.csv`'s row order is itself an input - it is how the delivery/unload sequence is expressed when `Customer_Code` varies (Section 4.5). The parsing module must preserve file row order end-to-end from read to solver input; no `sort_values()`, `groupby()`, or similar reordering operation may run on the packing list before Section 4.5's per-customer sequence number is derived from it. This is worth calling out explicitly because it is exactly the kind of ordering a general-purpose data-processing step (e.g. a pandas transformation reached for out of habit) can silently break without raising any error - the pipeline would still run and produce a plan, just a wrong one for LCL shipments, with nothing to signal the mistake.

### 2.3 `item_master.csv`

One row per carton type (SKU-as-packed), describing the physical properties of the **carton as it will sit in the container** - i.e. already-packed outer dimensions and gross weight, not the furniture pieces inside it. How many pieces are inside a carton is not tracked here; it has no bearing on loading.

| Field | Type | Meaning |
|---|---|---|
| `Item_ID` | str | Unique item identifier |
| `Description` | str | Human-readable name |
| `Length_cm` | float | Declared carton length (before any rotation) |
| `Width_cm` | float | Declared carton width |
| `Height_cm` | float | Declared carton height |
| `Weight_kg` | float | Gross carton weight |
| `This_Way_Up` | bool | `True`: the carton must stay upright - only its declared height may be the vertical dimension (may still be rotated 90 degrees around Z, swapping length and width). `False`: the carton may be tipped onto any face - any of its three declared dimensions may become the vertical one. |
| `Stacking_Group` | int | 1 = solid/sturdy, load-bearing furniture. 2 = lighter, framed/upholstered furniture that must not carry weight on top of it. |
| `Max_Load_Bearing_kg` | float | Maximum combined weight this carton can safely have resting on top of it (Section 4.4, constraint 5). **Optional**: if unknown for a given item, leave blank/omit and the system treats it as effectively unlimited (defaults to a very large number) rather than rejecting every stacked placement outright - see Section 4.4 for how this degrades safely without real data. |

**`This_Way_Up` is this warehouse's real-world simplification of the paper's general per-item posture model (Section 4.2, Table 1 in the paper).** The paper allows 7 intermediate cases (`t=1` through `t=7`, Table 1) covering every combination of which dimensions may be vertical, but this warehouse's actual cartons only ever fall into two of those: `This_Way_Up = True` is the paper's `t=1` (posture set `{1, 2}` - upright, optionally rotated around Z), and `This_Way_Up = False` is the paper's `t=7` (posture set `{1,2,3,4,5,6}` - fully free). There is no real SKU that's tippable onto some faces but not others, so the schema only needs to distinguish these two cases, not the full seven - see Section 4.2 for how this maps into the solver's orientation logic, and Section 4.2's note on why a genuinely intermediate case, if one ever comes up, would extend rather than break this field.

**A physical detail this model deliberately does not represent, and does not need to**: flipping a carton upside-down while keeping the same footprint orientation (i.e., the original top face now touching the floor) produces identical box dimensions to the un-flipped case - the cuboid geometric model (Section 4.1) has no notion of "which face is up" independent of which dimension is vertical, only of which dimension *is* vertical. This is not a posture the model excludes; it's a distinction the model was never able to represent in the first place, consistent with treating cargo as an idealized cuboid (the same simplifying assumption the source paper makes).

**Validation**: all dimensions and weight must be greater than 0; `Stacking_Group` must be 1 or 2; `This_Way_Up` must be boolean; `Max_Load_Bearing_kg`, if present, must be greater than 0.

### 2.4 From rows to boxes

Each `packing_list` row with `Qty_Cartons` = N is joined against `item_master` (for physical attributes), then expanded into N independent boxes, one per physical carton, since each carton is placed independently. A box's ID is built from its `Item_ID` plus a running index (e.g. `DT-8411_1`, `DT-8411_2`, ...). `PO_No` rides along from the packing-list row onto every box it expands into, for traceability in the output (Section 6).

**Tolerance gap is applied here, not deeper in the solver** (Section 4.4, constraint 7 covers the reasoning; this is where it's actually implemented). Rather than teach every downstream geometry check (non-overlap, support, extreme-point generation - Sections 4.4 and 5.1) about a separate "minimum gap" rule, the gap is baked into the dimensions once, at expansion time, and everything downstream runs completely unchanged:

- Each box's placed footprint is inflated by the configured `Tolerance_Gap_cm` (Section 7) on its length and width - a box declared as 100 x 50 cm is expanded to (100 + gap) x (50 + gap) cm for every placement, support, and overlap check the solver performs. **The full gap is added on one side only** (e.g. the +X and +Y faces), not split as half-gap per side - so two such inflated boxes placed edge-to-edge by the solver end up exactly `Tolerance_Gap_cm` apart in real (un-inflated) space, not `2 x Tolerance_Gap_cm`. Splitting the gap symmetrically across both faces would double the effective clearance between adjacent boxes, since both neighbors would independently contribute half a gap. **Height is never inflated** - Z is stacking space, not clearance space (constraint 4's whole point is that boxes rest directly on top of each other with no gap), so the inflation is strictly an X/Y-plane adjustment. The box is still rendered and reported (Section 6) at its *true* declared dimensions - the inflation is solver-internal bookkeeping, not something the Supervisor or the pick list ever sees.
- The container's usable footprint is shrunk by `Tolerance_Gap_cm` on each side, in X and Y only, before Section 5.1's search ever starts (so an extreme point can never land within one gap-width of a side wall or the container's far end). The container's usable *height* is left untouched for the same reason as above - there is no "ceiling clearance" requirement in this model, since nothing is meant to touch the ceiling in the first place. This gives the wall clearance half of the requirement in Section 4.4's constraint 7.
- Because every box already carries its own gap allowance, two boxes placed edge-to-edge by the solver automatically end up `Tolerance_Gap_cm` apart in real (un-inflated) space - the box-to-box clearance half of constraint 7 falls out of the same inflated-dimension trick with no separate pairwise check needed.

**To add a new input field**: add the column to the required-columns list and validation step for the relevant file (in the parsing module), thread it through the row-to-box conversion step into the box/container data structures (in the data-model module), and decide which downstream stage (constraints, scoring, or output) should consume it.

---

## 3. Solving Procedure (End-to-End)

General flow, following the source paper's own architecture directly (its Fig. 14 flow diagram and Section 2.4.4): inputs go into Parse and Join, then Initial Sort, then **Block Generation** to shrink the box list, then the **Genetic Algorithm** - decoding every individual through the **Improved Placeable Point Strategy** (which itself checks every constraint in Section 4.4, including LIFO when LCL is detected) - with **Simulated Annealing** invoked periodically as a local-refinement operator on the GA's best individual, then output is rendered as a 3D HTML visualization and a text pick list. The whole pipeline runs **once**, against the single container confirmed in Sections 1.3/2.1 - there is no candidate-container loop or "pick the best type" step, since that decision is made upstream, before this system runs.

**This system is a direct adaptation of the paper's algorithm, not a simplified stand-in for it.** Every stage below corresponds one-to-one with a stage in the paper (Section 5 gives the full detail and the paper-section cross-reference for each), and this warehouse's own constraints - the tolerance gap, the two-tier `This_Way_Up` posture model, the numeric load-bearing and center-of-gravity checks, and LIFO/LCL ordering - are integrated into these same stages rather than layered on afterward as a separate pass. Where this system's parameters or defaults differ from the paper's own (e.g. the support-ratio threshold, Section 4.4 constraint 4a), that is called out explicitly in Section 5; the *architecture* itself is unchanged from the paper.

### 3.1 Step by step (top-level entry point module)

**STEP 1 - Parse and join**: read and validate the packing list, item master, and the one active container spec (Section 2); join `packing_list` with `item_master`, expand `Qty_Cartons` into individual boxes (Section 2.4); detect FCL vs. LCL (Section 4.5).

**STEP 2 - Initial sort**: order the box list (Section 5.5) - customer sequence ascending first when LCL, then stacking group, then volume descending, then weight - keeping the paper's own descending-volume encoding order (paper Section 2.4.1) as a key while subordinating it to this warehouse's stacking-safety and delivery-order priorities. This fixed order is what the Genetic Algorithm's chromosome positions are indexed against; nothing after this step ever reorders the box list itself, only the posture (and, for the metaheuristic layer, the block/box grouping) assigned to each position.

**STEP 3 - Block generation**: a pre-processing pass (Section 5.1, paper Section 2.2) that consolidates boxes of identical or similar dimensions into larger composite blocks - simple blocks -> general blocks of identical size -> general blocks of similar size - before anything is placed. This shrinks the problem the Genetic Algorithm has to search over and produces flatter, more regular loading shapes. Blocks (and any leftover boxes that could not be combined) are re-sorted by Step 2's key and become the unit the rest of the pipeline places.

**STEP 4 - Genetic Algorithm with embedded Simulated Annealing** (Section 5.3, paper Section 2.4): the primary search driver. Each individual in the population is a posture assignment over the block/box list from Step 3; each individual is decoded into a full loading plan by the **Improved Placeable Point Strategy** (Section 5.2, paper Section 2.3), which does the actual placement, corner-first seeding, contact-ratio scoring, and constraint checking - including the LIFO check when LCL is active (Section 4.5). Fitness combines loaded volume with penalty terms for center-of-gravity deviation, load-bearing violations, and stability (Section 5.3.2, paper Eq. 12-16). Selection uses roulette-wheel plus elite retention; reproduction uses multi-point crossover and a dynamic-rate mutation (Section 5.3.3, paper Section 2.4.3). Every few generations, Simulated Annealing takes the current best individual and refines it through localized random re-posturing (Section 5.3.4, paper Section 2.4.3(4)) before the population continues. This loop runs for a configured number of generations or until convergence, and returns the best individual seen across the whole run.

**STEP 5 - Render output**: decode the GA's best individual one final time to produce the reported loading plan, then **explode every block placement back into its original individual boxes** (Section 5.2.4) - blocks exist only to make Steps 3-4's search faster and more effective, never as the actual unit reported to a Supervisor or a loading crew - then render a 3D HTML visualization and a text pick list from the exploded plan (Section 6).

**To add a new solving stage** (e.g. a post-processing compaction pass): insert it after Step 4 in the entry-point module, feeding it a loading plan and returning a loading plan, so it composes with the existing pipeline without touching the GA/SA/placement contract itself.

### 3.2 Where container selection actually happens

If a future version of this system needs to compare multiple container types (e.g. to recommend one rather than take it as given), that would sit as a wrapper *around* Steps 1-5 - run this same single-container pipeline once per candidate, then compare the resulting plans - rather than as a change to the pipeline itself. Nothing in Sections 4-5 assumes a fixed container; only the top-level entry point currently assumes it's called once.


---

## 4. Problem Modeling

This section describes the loading problem as an optimization model: what is being decided, what must always hold true, and what "better" means.

### 4.1 Coordinate system

Origin (0, 0, 0) is the **door corner** of the container (left-front-bottom at the door end).

- **X axis**: length (0 to length_cm, along the container, **door at x=0**, deepest/rear wall at x=length_cm) - a container's door is the short end (the `width_cm × height_cm` face), not a side wall, so it sits at the start of the *length* axis, not the width axis
- **Y axis**: width (0 to width_cm, left wall to right wall, across the container)
- **Z axis**: height (0 to height_cm, vertical, floor at z=0)

A box's position (x, y, z) is its own origin corner (left-front-bottom).

**Why this matters beyond terminology**: everything that reasons about "near the door" vs. "deep inside" - corner-first seeding (Section 5.2.2), LIFO ordering (Section 4.5), the layer-walkthrough view (Section 8.4) - reads that off the **x** coordinate, not y. Getting the axis backwards here doesn't just mislabel a picture; it would make LIFO's own "smaller x = unloaded first" convention (Section 4.5) point at the wrong physical face of the container, silently.

### 4.2 Decision variables

Following the source paper's model directly (Section 2.1.1 of the paper): for every box i, six binary variables `r_i,1 ... r_i,6` (Table 1, Fig. 2), one per posture, of which exactly one is 1 (Eq. 3) and it must belong to that item's *permitted* posture set `P_i,t` (Eq. 4) - plus the box's placement flag (placed or not) and its position `(x, y, z)`.

**The permitted posture set is per-item, driven by `item_master.csv`'s `This_Way_Up` field (Section 2.3), not a global constant.** This warehouse's real cartons only ever need two of the paper's seven `t` situations (Table 1): `This_Way_Up = True` is the paper's `t=1`, giving `P_i,1 = {1, 2}` (upright, optionally rotated 90 degrees around Z, matching the 2-posture case this system already supported before this revision); `This_Way_Up = False` is the paper's `t=7`, giving the full `P_i,7 = {1,2,3,4,5,6}` (free to tip onto any face). The solver's orientation logic (Section 5.1) reads this one field and looks up the corresponding fixed posture set - it does not need to support the intermediate `t=2` through `t=6` cases in Table 1 unless a genuinely intermediate SKU shows up in the future, at which point `item_master.csv` would need a richer field (e.g. three separate `*_Can_Be_Vertical` booleans, one per dimension) rather than the single `This_Way_Up` flag - a schema change, not an algorithm change, since the algorithm already reasons in terms of "which posture set does this item permit," regardless of how that set is declared.

**This replaces an earlier revision's 2-postures-always model.** An earlier version of this guide restricted every item in the system to at most 2 postures, on the reasoning that furniture generally shouldn't be tipped. That reasoning still holds for `This_Way_Up = True` items - which is exactly what `t=1` still expresses - but it was wrong to make it the *only* case the model supported: plenty of this warehouse's knock-down cartons are flat, symmetric, and have no real orientation requirement, and forcing them into the 2-posture case discarded placement options (and, per Section 4.3, potential completeness) those items could safely have offered.

### 4.3 Objective

**Primary objective: place every carton.** This follows directly from why this system exists at all (Section 1.1) - the two problems a DSS is meant to fix are avoidable rework (cartons pulled back out mid-load because the arrangement wasn't planned) and undocumented tribal knowledge (only an experienced Supervisor can improvise a fix when the plan runs short). A plan that leaves cartons unplaced hands both problems straight back to the Supervisor: those cartons still have to go somewhere, and figuring out where - after the "planned" part of the load is already sitting in the container - is exactly the improvisation this system is supposed to replace. A tightly-packed plan that strands a few cartons is not a partial success by this measure; it is a failure of the thing the system was built to do, however good its fill rate looks on paper.

**Secondary objective (tie-break only): maximize fill rate**, defined as used volume divided by container internal volume. This still matters - a needlessly loose arrangement wastes space and can look sloppy or unstable to a crew even when every carton is technically placed - but only ever as a way to choose between two plans that already place the same number of cartons. Fill rate is never traded against completeness: a plan that places every carton at a lower fill rate always beats a plan that leaves cartons out at a higher fill rate, with no exception and no configurable weighting between the two, since the moment fill rate is allowed to outweigh completeness even slightly, the door reopens to the exact "looks efficient, but someone still has to improvise a fix" outcome this section exists to rule out.

**Where this constrains the design, concretely**: every part of Sections 4-5 that scores or compares candidate states - the Placeable Point Strategy's per-box best-fit scoring (Section 5.2.1), the Genetic Algorithm's fitness function (Section 5.3.2) - must respect this ordering. A scoring or fitness function that trades completeness for density even a little silently reintroduces fill-rate-maximization as the real objective in practice, regardless of what this section says the priority is supposed to be; see Section 5.3.2 for exactly how the `UNPLACED_RANK_WEIGHT` term guarantees this ordering holds.

### 4.4 Constraints

Seven constraints are implemented:

1. **Capacity (weight)**: running placed weight must never exceed the container's maximum payload. Volume capacity is enforced implicitly by geometry, since a box can't be placed where it doesn't fit. Enforced in the constraints module.

2. **Orientation**: each box may only use a posture from its item's permitted posture set (Section 4.2) - `{1, 2}` if `This_Way_Up`, all six if not. Enforced in the data-model module.

3. **Non-overlap**: no two placed boxes may occupy overlapping 3D space. Enforced in the geometry module.

4. **Stackability (support and load-bearing category)**, a two-part rule:

   a. **Physical support**: a box not resting on the floor (z = 0) must have at least a configured minimum fraction (default 0.8, meaning up to 20% overhang) of its footprint area supported by box(es) whose top face is exactly at its z. **Deliberately stricter than the source paper**: the paper's own support-stability formulation (Eq. 7) uses a 0.5 threshold (more than half the footprint supported) as its baseline, and only tightens to 1.0 (full support, no overhang at all) when comparing against other algorithms that assume full support. This system defaults to 0.8 instead of the paper's 0.5 baseline as a deliberate safety margin for solid wood furniture handled by hand in this warehouse - real cargo isn't the idealized rigid cuboid the model assumes, so a wider support margin costs some fill rate but reduces the real-world risk of a carton tipping during transit or manual unloading. Configurable in Section 7 if a different margin is wanted for a specific fleet or route. **Interaction with tolerance gap (constraint 7)**: this ratio is computed against each box's gap-inflated footprint (Section 2.4), not its true declared footprint, since that's the footprint every other geometry check in this system already works against - the discrepancy this introduces is small and conservative (a slightly larger footprint in the denominator makes the ratio slightly harder to satisfy, never easier), so it was judged not worth a separate true-dimension recomputation just for this one ratio.

   b. **Load-bearing compatibility**: every supporting box must belong to a stacking group that is allowed to carry the candidate's stacking group. Sturdy Group-1 furniture can carry Group-2 on top, but Group-2 can never carry anything.

   Enforced in the constraints module.

5. **Load-bearing capacity (numeric)**: separate from the categorical rule in constraint 4, every box has a maximum weight it can safely carry on top of it (`Max_Load_Bearing_kg`, Section 2.3). For a candidate placement, sum the weight of everything that would rest on top of a given box - its direct supporters' own weight plus whatever those supporters are themselves carrying, propagated all the way up the stack - and reject the placement if that running total would exceed any supporting box's limit. This is a live numeric check, not just the Group-1/Group-2 category check in constraint 4; a box can be in the "load-bearing" category and still be refused a specific stack if the actual accumulated weight is too much for it. Enforced in the constraints module. **Data note** (Section 2.3): if `Max_Load_Bearing_kg` is missing for an item, this check treats its limit as effectively unlimited rather than blocking every placement on top of it - the constraint activates automatically as real capacity figures are added to `item_master.csv`, with no code change needed.

6. **Center of gravity (balance)**: after all boxes are placed, the shipment's overall center of mass must stay within a configured safe zone around the container's own geometric center. This matters more for road/vehicle safety than for cargo protection: an unbalanced load shifts the vehicle's handling characteristics. Because this warehouse's product mix is overwhelmingly solid wood furniture with fairly uniform density across items, each box's own geometric center is a reasonable stand-in for its individual center of mass - no separate per-item center-of-mass field is needed beyond `Weight_kg` and the box's placed position/dimensions. Concretely: compute the weighted average position of every placed box (weight-weighted by `Weight_kg`), and check it falls within configured tolerance bands around the container's ideal center `(length/2, width/2, height/2)` on each axis. See Section 5.4.2 for the detailed formulation and configuration knobs (this mirrors the source paper's center-of-gravity formulation directly, since the underlying assumption - uniform-density cuboid cargo - already holds for this warehouse's product mix). Unlike constraints 1-5 and 7, this is not a hard per-placement gate - it is folded into the Genetic Algorithm's fitness function as a penalty term (Section 5.3.2), since balance is a property of the whole plan, not any single placement.

7. **Tolerance gap (real-world clearance)**: the geometric model in Sections 4.1-4.2, like the source paper's own model, treats boxes and the container as idealized rigid cuboids that can sit flush against each other and against the walls with zero clearance. Real loading crews cannot work that way - a carton wedged with zero clearance on every side cannot physically be lifted, angled, or slid into place by hand, and a box pressed flush against the container's steel wall risks scuffing or denting on transit vibration. This system requires a configured minimum clearance, `Tolerance_Gap_cm` (Section 7, default 2 cm), both **between adjacent boxes** and **between any box and the container walls/ceiling**, in the X and Y (horizontal) directions - vertical (Z) stacking is unaffected, since boxes resting directly on top of each other is the normal, intended stacking behavior (constraint 4), not a clearance violation. Implemented as a dimension adjustment at box-expansion time (Section 2.4), not as a new per-placement check, so it applies uniformly everywhere geometry is already being checked (constraints 1-6 above) without duplicating logic. Enforced in the parsing/data-model module (Section 2.4), not the constraints module - by the time a box reaches constraint-checking, the gap is already accounted for in its working dimensions.

Not currently implemented: fragility-based handling restrictions (this warehouse's `Stacking_Group` distinction is about load-bearing sturdiness, not breakage risk, since the catalog is exclusively solid wood furniture with no glass/mirror/fragile categories).

### 4.5 FCL/LCL and LIFO unload ordering

This warehouse ships both **FCL** (Full Container Load - one container, one customer) and **LCL** (Less than Container Load - one container consolidating multiple customers' cargo, each customer unloaded at a different stop on the delivery route). These are not two different systems or two modes the Supervisor picks between - they are the same 3D-CLP with one additional constraint that is either vacuous (FCL) or active (LCL), and which one applies is read directly off the packing list, never chosen by hand.

**Detection**: count the distinct values of `Customer_Code` in the packing list (Section 2.2). Exactly one (or the column is absent/blank throughout) means FCL - proceed exactly as described everywhere else in this guide, with no ordering constraint at all. Two or more distinct values means LCL - the LIFO constraint below becomes active. This check runs once, in the parsing module, immediately after Section 2.2's row-order-preserving read, before Section 3's Step 2 (Initial Sort).

**Why row order encodes delivery sequence, not a separate field**: rather than add a numeric `Delivery_Stop` column the Supervisor would have to fill in and keep consistent, delivery order is read directly from the order `Customer_Code` values already appear in the packing list - whichever customer's rows come first in the file is unloaded first (delivered first, so loaded nearest the door), and whichever customer's rows come last is unloaded last (delivered last, so loaded deepest inside). This mirrors how a Supervisor or planner naturally assembles a consolidated packing list in the first place (stop 1's cargo listed first, stop 2's after it, and so on) rather than asking them to also annotate a redundant sequence number. The trade-off, made explicit in Section 2.2's validation note: this makes file row order load-bearing input, not incidental formatting, so the parsing module must never reorder rows before this sequence is derived.

**The LIFO rule itself** (active only when 2+ `Customer_Code` values are present): a box belonging to a customer whose rows appear *earlier* in the packing list (delivered/unloaded sooner) must never end up positioned such that a box for a *later* customer blocks its removal - concretely, an earlier-customer box may not sit strictly deeper (larger x, matching Section 4.1's door-at-x=0 convention) than a later-customer box that overlaps it on both the Y and Z axes, since that would mean physically moving the later-customer's cargo out of the way to reach the earlier customer's cargo at their stop.

**Explicit convention, stated once here to be quoted from rather than re-derived**: `Customer_Sequence` 1 = first customer encountered in the packing list = delivered first = unloaded first = correct final position is SMALL x (near the door). Higher `Customer_Sequence` = later delivery = correct final position is LARGE x (deep inside). A violation is: `earlier.Customer_Sequence < later.Customer_Sequence` AND `earlier.x > later.x` (the early-sequence box sits deeper than the late-sequence box) AND they overlap on Y and Z. **Get the inequality direction backwards in either comparison and the check silently enforces the opposite of LIFO** - it will still run, still reject some placements, and produce a plan that looks plausible, but the resulting load order actively fights unloading instead of enabling it. This is exactly the kind of error that survives casual testing (the solver still runs, still produces *a* plan, fill rate looks normal) and is only caught - expensively - when a crew tries to unload it. Section 5.2's unit tests (referenced from the build-order prompt in this project) should include at least one hand-built two-customer scenario matching "T2" and one three-customer full-reversal scenario matching "T5" in spirit: construct a plan with a *known, deliberately wrong* placement (an early-sequence box placed behind a late-sequence one) and assert the rejection chain actually catches it - not just that the happy-path (already-correct ordering) produces no false rejections, which is the easier and less useful half of this to verify.

**Where this plugs into the pipeline** (each numbered to match the equivalent already-described mechanism it extends):

1. **Initial sort (Section 5.5)**: when LCL is detected, the sort key gains a new *primary* key ahead of `Stacking_Group`: customer sequence number **ascending** (earliest-delivered customer's boxes sorted first, so they are placed first - and, because the placement search fills outward from the door, they end up nearest the door, exactly where LIFO needs them). `Stacking_Group` and `Weight_kg` remain the secondary/tertiary keys exactly as today, now applied *within* each customer's group rather than across the whole box list. In the FCL case (one customer, or none), this new primary key is constant for every box and the sort collapses back to exactly Section 5.5's current two-key behavior - no special-casing needed for FCL, the same code path handles both.

   **Why ascending, not descending** - this is the single easiest thing to get backwards in the whole LIFO design, and getting it wrong is catastrophic rather than merely suboptimal. The tempting intuition is "sort the last-delivered customer first so they get pushed deepest," but that intuition only holds for a placement search that fills *from the back wall inward*. This system's does the opposite: extreme points are seeded at the door corner (Section 5.2, `(0,0,0)`; Section 4.1 puts the door at x=0) and the scoring tie-break prefers **smaller x** (Section 5.2.1), so **whatever is processed first lands nearest the door**. Sorting last-delivered-first therefore parks the last customer's cargo right at the door, and every subsequent earlier-customer box then has nowhere legal to go - each one gets rejected by this section's own LIFO check (point 3 below), because any remaining position is deeper than cargo that must come out later. A 3-customer, 9-box worked example: ascending places 9/9; descending places 3/9 and strands the other 6 as `lifo_blocked`. The sort direction must match the direction the container actually fills, and this container fills from the door.
2. **Block generation (Section 5.1)**: boxes are grouped by `(dimensions, Customer_Sequence)`, not dimensions alone, so a single block can never straddle a customer boundary - a block is one object once formed, and there's no way to place "half a block" for one customer and the rest for another.
3. **Placement search rejection chain (Section 5.2's `find_best_placement`)**: one additional check per candidate placement, active only in the LCL case - reject a candidate if it would block any already-placed box belonging to an earlier-sequence customer (the geometric test in the paragraph above). Because boxes are already processed later-customer-first (point 1), this check is a safety net that should rarely actually trigger, not the primary mechanism - the sort order does most of the work by construction, the same relationship the rejection chain's other constraints already have with Section 5.5's sort.
4. **Genetic Algorithm and Simulated Annealing (Section 5.3)**: because box/block *order* is fixed once by Initial Sort (point 1) and never searched over - only posture is (Section 5.3.1) - there is no separate LCL-specific restriction needed on the GA's crossover/mutation or on SA's neighbor moves the way an order-searching metaheuristic would need. A posture reassignment, however produced, can never move a box into a different customer's segment or violate the customer-grouped processing order; the LIFO rejection chain (point 3) is reached identically for every individual regardless of which postures it carries. This is a structural simplification LIFO gets for free from the paper's own posture-only encoding choice (Section 5.3.1), not a separate mechanism that needed building.

**Fill-rate cost is real and worth surfacing, not hiding**: LIFO is a genuine constraint on the search space - a placement that would improve fill rate but blocks an earlier customer's cargo is rejected regardless of how much density it would add. This is the trade-off flagged from this project's earliest planning ("LIFO and Fill Rate need a balance point") made concrete: for LCL runs, Section 6's output should make it easy to see this cost, not just the final fill rate number (Section 6.3's note below).

**History**: an earlier version of this guide removed LIFO/multi-stop support entirely, reasoning that shipments were "essentially always single-destination." That reasoning held for the FCL-only case but missed that this warehouse also runs LCL shipments as a matter of course, not an edge case - the constraint isn't a rare capability worth cutting for simplicity, it's the defining feature of half the warehouse's shipment types. The mechanics reintroduced above are deliberately close to what was removed (the same sort-key/rejection-chain/SA-scoping shape), just re-triggered automatically from `Customer_Code` instead of a manually-maintained `Delivery_Stop` field, and scoped explicitly to "activate only when actually needed" so the FCL path - still the simpler and more common case - carries none of this complexity.

---

## 5. Solving Methods

This system's solving pipeline **is** the source paper's own architecture, adapted with this warehouse's constraints (Section 4.4) and LIFO/LCL ordering (Section 4.5) integrated directly into each stage: **Initial Sort** (5.5) fixes *processing order*. It runs twice by design: once on raw boxes so Block Generation groups like with like, then again on the block/box list that Block Generation produces, since merging changes what the units are. **That second pass is the definitive one** - its output is what chromosome positions are indexed against (Section 5.3.1), and nothing downstream ever reorders the list again; only the posture assigned to each position is searched over, matching the paper's own encoding choice (paper Section 2.4.1). **Block Generation** (5.1, pre-processing) then reduces problem size by pre-combining same/similar-size boxes into larger composite units, operating on that fixed order - but strictly as an internal search accelerator: every block carries forward the original boxes it was built from (`contents`), and gets exploded back into them once, at the very end (Section 5.2.4), so nothing downstream of the search ever reports or renders a block. The **Genetic Algorithm** (5.3) is the primary search driver, exploring posture assignments across a population of candidate solutions, with **Simulated Annealing embedded inside it as a local-refinement operator** (Section 5.3.4) that periodically sharpens the GA's current best individual - this is the paper's own GA+SA relationship (paper Section 2.4), not two separate, independently-selectable solving stages. Every individual the GA (and, within it, SA) touches is decoded through the same **Improved Placeable Point Strategy** (5.2), which does the actual placement, extreme-point bookkeeping, corner-first seeding, contact-ratio-plus-residual-volume scoring, and full constraint checking (including LIFO, Section 4.5) - this is the one piece every other stage calls, never re-implements.

Reading order for this section follows the order boxes actually flow through the pipeline: 5.1 (Block Generation) shrinks the box list first; 5.2 (Placeable Point Strategy, including 5.2.4's explode-back-to-boxes step) is the shared decoder every later stage depends on, so it's covered before the stages that call it; 5.3 (Genetic Algorithm, with Simulated Annealing as its embedded local operator) is the search driver that repeatedly calls 5.2; 5.4 covers this system's numeric load-bearing and center-of-gravity checks in the detail the paper itself gives them (Eq. 8-10, 13); 5.5 (Initial Sort) is technically applied earliest in Section 3's Step 2, but is placed last here because it is easiest to understand once it's clear what "processing order" is being fixed for.

### 5.1 Block generation (pre-processing step, before Section 5.2 ever runs)

**Problem this solves**: many boxes of identical or near-identical size (e.g. a large `Qty_Cartons` on one `packing_list` line) would otherwise be placed one at a time, each running its own full extreme-point search - slower, and with nothing to stop them from stacking into a narrow tower at a single anchor instead of spreading across the container. Pre-combining same-size boxes into a single larger "block" object, placed once, both speeds up the search (fewer objects for Sections 5.2-5.4 to reason about) and produces flatter, more regular loading shapes.

High-level idea, following the paper's three-stage structure (simple blocks -> general blocks of identical size -> general blocks of similar size, Section 2.2.1): group boxes of identical dimensions into 1D columns, combine same-size columns into 2D layers then 3D blocks, then allow combining boxes of merely *similar* dimensions (within a configured tolerance) as long as the combined block is at least 98% actual-cargo-volume (this threshold, sourced from Fanslau and Bortfeldt 2010, is the value the paper itself uses) - never emptier than that, so a block never silently contains a lot of wasted internal space that Section 5.2's own scoring would otherwise have caught and avoided.

**A block must never be allowed to grow to nearly the size of the container itself.** "Fits inside the container" on its own is not a strong enough stopping condition once the packing list can contain 20+ identical-size cartons on one line (this warehouse's real packing lists - Section 2.2 - routinely do; the paper's own benchmark instances did not, since BR/LN test cases rarely repeat one exact size more than a handful of times). Left unchecked, a column-building step that only checks "still fits" will keep adding boxes until the column spans nearly the whole container on that axis - a `1162 cm` column inside a `1199 cm`-long container is a real failure mode, not a hypothetical one: it consumes almost the entire usable length in one object, leaving Section 5.2's placement search almost nothing to work with once that one block is placed, which is a worse outcome than not combining those boxes into a block at all. A block that large also defeats the entire point of block generation (Section 5.1's own opening paragraph) - it isn't "fewer, more efficient objects to place," it's "one object that behaves like a wall," and walls that size were never something the constructive placement search was meant to receive as a single unit.

The fix is a second stopping condition, checked independently of "does it fit": a configured `max_block_fraction` (Section 7, default 0.4) caps how far a merge may **grow** a block along any axis, relative to the container's own extent on that axis. A block is accepted only if it satisfies both conditions - fits inside the container **and** respects the growth cap on every axis - not just the first one.

**The cap constrains growth, never a carton's own native size.** This distinction is the difference between a working fix and one that silently disables block generation for a large share of the catalog. A naive version of this check compares each axis's extent directly against `container.extent * max_block_fraction`, but on an axis a merge did not grow, the candidate's extent is simply its input's own unchanged dimension - and plenty of real cartons are individually larger than 40% of a container dimension on some axis (a 40HC's usable width is ~231 cm, so the 0.4 cap is ~92 cm, which a 110 cm-wide dining-table carton already exceeds on its own). Under the naive check, such a carton can never enter *any* block, in *any* stacking direction, because the offending axis is one that stacking along a different axis never changes. Measured on this warehouse's own catalog, the naive form disabled block generation for 9 of 30 SKU lines, covering 62 of 152 cartons - roughly 40% of a typical load left as individual boxes for a reason that has nothing to do with block size. `fits_bounds` below therefore compares against `max(container.extent * max_block_fraction, largest native input extent on that axis)`, so an un-grown axis always passes and the cap only ever bites on the axis a merge is actually extending:

```
FUNCTION build_blocks(boxes, container, min_fill_ratio, max_block_fraction):
    # Step 1: group boxes of identical dimensions together
    groups = group boxes by (length, width, height)

    simple_blocks = []
    leftover = []

    FOR EACH group IN groups:
        IF size of group < 2:
            leftover.extend(group)
            CONTINUE

        # Step 2: try to build a 1D column of this box in each of the
        # 3 axis directions, shrinking the column count until it fits
        # inside the container AND stays under max_block_fraction of
        # the container's own extent on that axis - two independent
        # stopping conditions, not one, checked via the shared
        # fits_bounds helper (defined below, alongside the merge
        # functions that also use it). Only the stacking axis changes
        # extent here (the other two axes are still exactly the
        # original box's own dimensions, already known to fit, since
        # Section 4.4's own modeling assumption is that every box is
        # individually smaller than the container) - unlike the Step 3
        # merges below, where two already-built objects are combined
        # and EVERY axis needs re-checking, not just the merge axis.
        best_column = None
        FOR EACH axis IN (X, Y, Z):
            count = size of group
            WHILE count >= 2:
                column_dims = box dims with `count` copies stacked along `axis`
                IF fits_bounds(column_dims, [box], container, max_block_fraction)
                   AND stack_is_safe(box, count, axis):
                    candidate = column of `count` boxes along `axis`
                    IF best_column is None OR candidate leaves a smaller
                       leftover gap against the container boundary:
                        best_column = candidate
                    BREAK
                count -= 1

        IF best_column is not None:
            simple_blocks.append(best_column)
            leftover.extend(boxes in group not used by best_column)
        ELSE:
            leftover.extend(group)

    # Step 3: combine same-size simple blocks/boxes into 2D layers first
    # (matching the column/layer/block hierarchy the source paper uses:
    # 1D columns -> 2D layers -> 3D general blocks), then combine layers
    # into 3D general blocks the same way columns were combined above.
    #
    # CRITICAL: this is a REPEATED PAIRWISE merge, and the two stopping
    # conditions from Step 2 (fits inside container, stays under
    # max_block_fraction on every axis) must be re-checked after EVERY
    # single merge, not just once at the end. Two already-valid,
    # already-capped columns can still combine into an object that
    # breaks both conditions - e.g. two columns each at exactly the
    # 0.4 cap on the Y axis, placed side-by-side into a layer, sum to
    # 0.8 on that axis, which may now exceed the container's own width
    # outright, not just the fraction cap. A merge function that checks
    # bounds only on its own two direct inputs and assumes the result
    # is safe by induction is exactly the bug this guide is correcting:
    # it is NOT safe by induction, because bounds are a property of the
    # combined object's own absolute size, not of whether its inputs
    # were each individually valid. (See combine_into_layers and
    # combine_layers_into_blocks below - both re-check via fits_bounds
    # after every single pairwise merge, never at the end only.)
    layers = combine_into_layers(simple_blocks + leftover, container, max_block_fraction)
    layered_blocks = combine_layers_into_blocks(layers, container, max_block_fraction)

    # Step 4: allow combining boxes of SIMILAR (not just identical) size
    # within a configured tolerance, but only accept the combination if
    # BOTH: the actual box volume divided by the bounding-block volume
    # is at least `min_fill_ratio` (paper's own value: 0.98) - this
    # stops a block from silently containing a lot of wasted internal
    # space that Section 5.2's own scoring would otherwise have caught
    # - AND the same max_block_fraction cap from Steps 2-3 still holds,
    # re-checked the same pairwise way (see combine_similar_sizes below).
    final_blocks = combine_similar_sizes(layered_blocks, min_fill_ratio, max_block_fraction)

    # Step 5: hand off to Section 5.5's Initial Sort exactly as if these
    # were ordinary boxes - a block is just a box-shaped object as far
    # as Section 5.2 is concerned, with weight = sum of contents,
    # stacking_group = the most restrictive group among its contents,
    # and This_Way_Up = True if ANY contained box requires it (a block
    # can never be tipped if even one of its contents must stay upright).
    # Crucially, each block also retains `contents`: the flat list of
    # original boxes it was built from, with each one's own true
    # position recorded relative to the block's own origin corner - see
    # Section 5.1's closing note on this, and Section 6.1's "exploding"
    # step, both of which depend on `contents` being carried through
    # every merge above rather than discarded once a block is formed.
    RETURN final_blocks


FUNCTION stack_is_safe(unit, count, axis):
    # Constraints 4b and 5 (Section 4.4) apply to boxes stacked INSIDE a
    # block exactly as they do to boxes stacked in the container - but
    # nothing else in the pipeline can enforce them there, because
    # Section 5.2's rejection chain only ever sees a finished block as a
    # single opaque object and never looks inside it. If this check is
    # missing, block generation quietly manufactures stacks the solver
    # would have refused to build one box at a time. See the note below
    # for the measured scale of that on this warehouse's own catalog.
    IF axis is not Z:
        RETURN True          # side-by-side along X or Y: nothing rests on anything

    # 4b: a Group-2 unit must never carry weight, so it can never have
    # another unit stacked on top of it - not even an identical one.
    IF unit.stacking_group == 2:
        RETURN False

    # 5: the bottom unit carries every unit above it; check the real
    # accumulated weight against its own declared limit. A missing
    # Max_Load_Bearing_kg means "effectively unlimited" (Section 2.3),
    # consistent with how constraint 5 treats it everywhere else.
    carried = (count - 1) * unit.weight_kg
    IF unit.max_load_bearing_kg is present AND carried > unit.max_load_bearing_kg:
        RETURN False

    RETURN True


FUNCTION fits_bounds(candidate, inputs, container, max_block_fraction):
    # Shared by every merge step in Section 5.1 (Steps 2-4) so the two
    # stopping conditions are defined once and applied identically
    # everywhere a merge is attempted, rather than re-implemented (and
    # potentially re-broken) at each step.
    #
    # `inputs` = the unit(s) this candidate was built from (the single
    # box for a Step-2 column, or the two units being merged in Steps
    # 3-4). It exists so the fraction cap can be applied to GROWTH only
    # - see the note below on why comparing against the raw cap alone
    # is wrong.
    FOR EACH axis IN (X, Y, Z):
        IF candidate.extent_on(axis) > container.extent_on(axis):
            RETURN False                                          # doesn't physically fit

        # The cap must never reject an extent the inputs ALREADY had before
        # this merge - on an axis the merge didn't grow, the candidate's
        # extent is just its input's own unchanged dimension, and a single
        # carton's own size is not something block generation gets to veto.
        native = max(unit.extent_on(axis) for unit in inputs)
        effective_cap = max(container.extent_on(axis) * max_block_fraction, native)

        IF candidate.extent_on(axis) > effective_cap:
            RETURN False                                          # fits, but this merge grew the axis past the cap
    RETURN True


FUNCTION combine_into_layers(units, container, max_block_fraction):
    # `units` = simple_blocks and/or individual leftover boxes from Step 2.
    # A "layer" is a 2D arrangement of same-size units sharing one
    # dimension - built by repeatedly merging pairs of same-size units
    # side-by-side along one axis, exactly like Step 2's column-building,
    # but now merging already-built columns (or individual boxes) rather
    # than raw boxes.
    remaining = list of units, grouped by (dimensions)
    layers = []

    FOR EACH group IN remaining (units of identical dimensions):
        current = first unit in group
        FOR EACH next_unit IN rest of group:
            matched = False
            FOR EACH axis IN (X, Y, Z):
                candidate = merge current and next_unit side-by-side along axis
                # Both conditions checked on the ACTUAL COMBINED candidate,
                # on ALL THREE axes - not inherited from current/next_unit's
                # own prior checks, and not limited to just the merge axis,
                # since merging along X can still be the merge that pushes
                # Y or Z over the limit if current/next_unit were already
                # close to it on those axes.
                IF fits_bounds(candidate, [current, next_unit], container, max_block_fraction):
                    current = candidate
                    matched = True
                    BREAK
            IF NOT matched:
                layers.append(current)     # can't extend further; close this layer off
                current = next_unit        # start a new layer from the unmerged unit
        layers.append(current)             # append whatever's left after the loop

    RETURN layers


FUNCTION combine_layers_into_blocks(layers, container, max_block_fraction):
    # Same repeated-pairwise-merge-with-re-check pattern as
    # combine_into_layers above, one dimension up: merges same-size
    # layers into 3D blocks along whichever remaining axis they share.
    # Deliberately NOT implemented as "merge everything that matches,
    # then check the final result once" - see the note in build_blocks'
    # Step 3 above for why that ordering is unsafe.
    remaining = list of layers, grouped by (dimensions)
    blocks = []

    FOR EACH group IN remaining (layers of identical footprint):
        current = first layer in group
        FOR EACH next_layer IN rest of group:
            candidate = merge current and next_layer along the one remaining axis (typically Z)
            IF fits_bounds(candidate, [current, next_layer], container, max_block_fraction)
               AND stack_is_safe(current.heaviest_loaded_unit, 2, merge_axis):
                # stack_is_safe is re-applied here for the same reason it is
                # applied in Step 2: stacking one layer on another puts real
                # weight on the units in the lower layer, and constraints 4b
                # and 5 do not stop applying just because the thing being
                # stacked is a layer rather than a single box. The weight now
                # resting on the lower layer is `next_layer.total_weight`,
                # checked against the lower layer's own limiting unit.
                current = candidate
            ELSE:
                blocks.append(current)
                current = next_layer
        blocks.append(current)

    RETURN blocks


FUNCTION combine_similar_sizes(blocks, min_fill_ratio, max_block_fraction):
    # Same repeated-pairwise-merge-with-re-check pattern as the two
    # functions above, but comparing SIMILAR (not identical) dimensions
    # within a configured tolerance, and gated by min_fill_ratio in
    # addition to fits_bounds - a candidate must pass BOTH before it's
    # accepted, matching Step 4's own description in build_blocks above.
    remaining = list of blocks
    final = []

    WHILE remaining is not empty:
        current = remaining.pop(0)
        matched = True
        WHILE matched:
            matched = False
            FOR EACH other IN remaining (a copy, safe to remove from while iterating):
                IF current and other have similar dimensions (within configured tolerance):
                    FOR EACH axis IN (X, Y, Z):
                        candidate = merge current and other side-by-side along axis
                        actual_cargo_volume = current.actual_volume + other.actual_volume
                        bounding_volume = candidate.length_cm * candidate.width_cm * candidate.height_cm
                        fill_ratio = actual_cargo_volume / bounding_volume
                        IF fits_bounds(candidate, [current, other], container, max_block_fraction)
                           AND fill_ratio >= min_fill_ratio:
                            current = candidate
                            remaining.remove(other)
                            matched = True
                            BREAK
                IF matched:
                    BREAK
        final.append(current)

    RETURN final
```

**Choosing `max_block_fraction`**: the default of 0.4 means no single block may span more than 40% of the container's length, width, or height - comfortably large enough to still capture the point of block generation (a 20-box column of identical cartons becomes one object instead of 20, still a large win for search speed and shape regularity) while guaranteeing that even a worst-case single block can never consume more than 2 of the container's 5 usable "slots" along any one axis, leaving the placement search real room to interleave other boxes and blocks around it. This is a genuine tunable trade-off, not a fixed constant the way the paper's own 98% fill-ratio threshold is: a smaller fraction (e.g. 0.25) produces more, smaller blocks - closer to the paper's own typical block sizes, and safer against the "block behaves like a wall" failure mode - at the cost of a larger post-block-generation box list for the Genetic Algorithm (Section 5.3) to search over; a larger fraction pushes the opposite trade-off. **A block spanning 97% of the container's length (this section's opening example) is exactly the failure mode `max_block_fraction = 0.4` exists to prevent** - such a block would be rejected at Step 2 well before its column ever grew that large, and the 23-25 boxes that would have gone into it are instead split across multiple capped-size blocks (or left as smaller blocks/individual boxes), giving Section 5.2's placement search several objects to arrange around each other instead of one that dominates the container outright.

**Interaction with tolerance gap (Section 4.4, constraint 7)**: since boxes already carry the gap-inflated dimensions by the time this stage runs (Section 2.4 applies it at expansion, before any solving stage sees a box), columns/layers built here naturally inherit correct spacing between their constituent boxes with no extra work - a column of 5 gap-inflated boxes stacked edge-to-edge is already `Tolerance_Gap_cm` apart per pair in real space, the same as if Section 5.2 had placed them individually. Nothing about block generation needs to know tolerance gap exists, and the `max_block_fraction` check above is computed off the same already-gap-inflated dimensions, so it is measuring the block's true footprint in the container, not an optimistic pre-gap figure.

Notes on fit with the current design:

- **Block generation is the one place in this pipeline that can create a stack without Section 5.2's rejection chain ever seeing it.** Every other stacking decision goes through `find_best_placement`, which checks constraints 4b (Group-2 must never carry weight) and 5 (numeric load-bearing) per placement. A block, by contrast, arrives at that function already assembled - its internal stack is a fait accompli, and the function has no visibility into it. `stack_is_safe` (above) closes that gap by applying the same two constraints at merge time, and it is not a theoretical precaution: measured against this warehouse's own catalog and packing list, block generation *without* it would have built **5 blocks stacking Group-2 cartons on Group-2 cartons** (nightstands, dining chairs, ottomans, wall shelves, an assembled TV console) and **9 blocks exceeding the bottom carton's `Max_Load_Bearing_kg`** - a 5-high wardrobe column putting 392 kg on a carton rated for 250 kg, a 7-high bed-frame column at 336 kg on a 220 kg limit, and so on. Those blocks would then have been placed, reported, and handed to a loading crew as a valid plan.
- A block's `Stacking_Group` should be the most restrictive (numerically smallest) group among its contents, so the combined object is never treated as more stackable than its most fragile member.
- A block's `This_Way_Up` (Section 2.3) must be `True` if any single box inside it is `True` - a block is only as free to tip as its most restrictive member allows, for the same reason as `Stacking_Group` above.
- **For LCL (Section 4.5), block generation must never combine boxes across a `Customer_Sequence` boundary** - a block is a single object once formed, and Section 5.5's per-customer segment ordering has no way to place "half a block" for one customer and the rest for another. Group boxes by `(dimensions, Customer_Sequence)` in Step 1, not dimensions alone, so this never comes up rather than needing to be checked for and rejected later.
- This step sits entirely before Section 5.2; it does not change the placement search, scoring, or any constraint check - it only changes what counts as "one box" (or "one posture-bearing chromosome position", Section 5.3.1) going into the search that follows.
- **A block's permitted posture set** follows the same This-Way-Up logic as any single box (Section 4.2): a block's `This_Way_Up` is `True` if any contained box requires it, which per Section 4.2 means the block itself is restricted to the 2-posture set `{1, 2}`; only a block whose every contained box has `This_Way_Up = False` gets the full 6-posture set `{1,2,3,4,5,6}`. This is what actually lets the Genetic Algorithm's per-position posture gene (Section 5.3.1) treat a block exactly like a box - it doesn't need to know whether a chromosome position holds one carton or fifty, only how many postures that position is allowed to take.
- **A block always carries `contents`: the flat list of original boxes it was built from, each with its own position recorded relative to the block's own origin corner** (not yet rotated or translated into container coordinates - that happens once, for the whole block, when Section 5.2 actually places it). Every merge step above (`combine_into_layers`, `combine_layers_into_blocks`, `combine_similar_sizes`) must carry `contents` forward when it produces a new candidate - concatenating the two inputs' own `contents` lists, with the second input's box positions offset by wherever it landed relative to the first. **This field is not optional bookkeeping**: block generation exists purely to make Sections 5.2-5.3 faster and more effective by treating many boxes as one object during the search, but a block is never the *real* physical unit being loaded - the individual boxes are. Section 6.1 depends on `contents` to reconstruct and render each block's original boxes individually rather than rendering the block itself as one giant cuboid (see Section 6.1's "exploding blocks back to boxes" note for exactly how).

### 5.2 Placeable point strategy (the shared decoder)

Every other stage in this pipeline - the Genetic Algorithm and its embedded Simulated Annealing local operator (5.3) - decodes a candidate solution by calling this same placement logic. This section describes placement and constraint checking once; nothing above it re-implements any part of this.

Extreme points: a point is a candidate anchor (x, y, z) where a box's origin corner could go.

- Starts with a single extreme point at the origin (0, 0, 0).
- After placing a box, 3 new extreme points are generated: one past the box's right face (+X), one past its back face (+Y), one past its top face (+Z).
- Dominance pruning: a point Q dominates P if Q is at least as good as P on all 3 axes (smaller-or-equal x, y, z) with equality on at least 2 axes and strict improvement on the third. Dominated points are discarded to keep the search space compact. This is the single hottest code path in the engine under both the Genetic Algorithm and Simulated Annealing, so it's hand-optimized for speed rather than written in the most literal/readable form.

Per-box placement search, pseudocode - **takes a specific posture as input (from the chromosome/individual being decoded, Section 5.3) rather than trying every allowed posture itself**, since posture assignment is what the Genetic Algorithm searches over; this function's job is purely to find the best *position* for a box whose posture is already fixed:

```

FUNCTION find_best_placement(box, posture, extreme_points, placed_boxes, container):
    IF adding box would exceed the container's max weight:
        RETURN None, 'no_space'

    dims = box dimensions under the given posture   # Section 4.2's r_i,p mapping

    best_candidate = None
    best_score = -infinity
    saw_lifo_only_rejection = False   # true if some candidate passed every
                                       # check except the LIFO one

    FOR EACH extreme_point IN extreme_points:
        headroom = available space from extreme_point to the nearest
                   obstruction (placed box or container wall) on each axis

        IF dims exceed headroom on any axis: CONTINUE
        IF placement pokes outside container: CONTINUE
        IF placement overlaps any placed box: CONTINUE
        IF placement fails support/stackability check: CONTINUE
        IF placement fails numeric load-bearing check (Section 4.4, constraint 5): CONTINUE
        IF LCL detected AND placement would block an earlier-customer box (Section 4.5):
            saw_lifo_only_rejection = True   # reached here means every OTHER check already passed
            CONTINUE

        score = best-fit score for this candidate   # see Section 5.2.1

        IF score > best_score:
            best_candidate = extreme_point
            best_score = score
        ELSE IF score == best_score:
            # tie-break: prefer smaller x, then larger z
            best_candidate = whichever of (best_candidate, candidate)
                             wins the tie-break rule above

    IF best_candidate is not None:
        RETURN best_candidate, None   # placed; no reason needed
    ELSE IF saw_lifo_only_rejection:
        RETURN None, 'lifo_blocked'   # at least one spot would have fit if not for LIFO
    ELSE:
        RETURN None, 'no_space'       # every candidate failed on ordinary grounds; LIFO was never the deciding factor
```

**Why the reason is derived this way, not from "which check rejected the most candidates"**: a box can rack up many `no_space`-style rejections (dims too big, would overlap) and also a handful of `lifo_blocked`-style ones across different extreme points - counting rejections wouldn't cleanly separate the two. The distinction that actually matters operationally is binary: *was there ever a spot that would have worked if LIFO weren't a factor at all?* If yes, the real obstacle is LIFO, however many other candidates also independently failed for unrelated reasons. `saw_lifo_only_rejection` captures exactly that question - it only ever gets set when a candidate reaches the LIFO check at all, which by construction means every earlier check in the chain already passed for that specific candidate.

**Note on center-of-gravity (constraint 6, Section 4.4)**: unlike the checks above, center-of-gravity balance is a property of the *whole plan*, not any single candidate placement - it depends on the weighted position of every box placed so far, and shifts with every new placement. It is therefore not part of this per-box rejection chain; see Section 5.3.4 for how it is evaluated instead, as a fitness-function penalty term rather than a hard per-placement gate.

**The loop that drives this function lives in Section 5.3.1 (`decode`), not here.** It is defined once, there, because it needs two things this section doesn't cover: the corner-first phase (Section 5.2.2) and posture repair (Section 5.3.1), both of which sit around `find_best_placement` rather than inside it. An earlier revision of this guide carried a second, simplified copy of that loop in this section; it drifted out of step with the real one - missing corner seeding and repair - which is exactly the hazard duplicated pseudocode creates. There is now one definition, in Section 5.3.1.

Unplaced boxes are recorded, never dropped silently.

#### 5.2.1 Placement scoring (best-fit)

Combines two signals, computed for every valid candidate placement:

```
score = (weight A) * (-residual volume) + (weight B) * (contact ratio)
```

**Residual volume** is the wasted empty volume left around the box within its extreme point's headroom; lower is better, hence the negative weight.

**Contact ratio** (total contact area divided by box surface area) measures how much of the box's surface touches the container floor/walls or other boxes; higher is better, for stability.

Both weights default to 1.0 (in the config module); adjust them to bias the search toward tighter packing vs. more stable contact.

**Relationship to the source paper**: the paper's own placement-scoring rule (Eq. 11, `S(C,P) = A_contact(C,P) / A_surface(C)`) uses contact ratio alone - the single signal this system's "contact ratio" component already captures. Adding the residual-volume term is a deliberate extension beyond the paper: contact ratio alone can be satisfied by a placement that wedges a box into a tight corner touching many surfaces while still leaving awkward, hard-to-fill gaps elsewhere, whereas penalizing residual volume directly rewards placements that leave the remaining free space more usable for later boxes. The paper's tie-break rule (smallest x, then largest z among ties) is unchanged and matches Section 5.2's tie-break exactly.

#### 5.2.2 Corner-first seeding

**Problem this solves**: starting the search from a single extreme point at the origin (Section 5.2) means the container's other 3 bottom corners are only reached indirectly, after enough boxes have been placed to generate extreme points near them - which can be late, or never, leaving those corners as awkward leftover gaps. Matches the paper's own corner-first strategy (Section 2.3.3 of the paper) directly.

**Strategy**: seed all **4 bottom corners** of the container at the start:
`(0, 0, 0)`, `(0, W - box.dim_y, 0)`, `(L - box.dim_x, 0, 0)`, `(L - box.dim_x, W - box.dim_y, 0)`.
Place initial boxes into these 4 corners first before switching to the normal best-fit search above.

```
FUNCTION corner_points_for(box, box_dims, container, shipment_type, last_customer_sequence):
    # A placed box's position is its OWN origin (left-front-bottom) corner
    # (Section 4.1), so the far-side corner anchors must be offset inward by
    # that box's own extent - otherwise the box would start AT the wall and
    # extend straight through it. This is why corner anchors depend on the
    # box being placed and cannot be precomputed from the container alone
    # (the paper does the same, its Fig. 10: P_left-rear = (L - l_i, 0, 0)).
    (dx, dy, dz) = box_dims          # dims under the posture being tried

    corners = []
    corners.append((0, 0, 0))                                                        # door corner, left wall
    corners.append((0, container.width_cm - dy, 0))                                  # door corner, right wall

    # The two DEEPEST corners are offered only when placing cargo that
    # belongs at the back of the container. In FCL that's everything; in
    # LCL it is only the last-delivered customer (Section 4.5) - see the
    # LCL note below for why offering them to anyone else is destructive.
    IF shipment_type == 'FCL' OR box.customer_sequence == last_customer_sequence:
        corners.append((container.length_cm - dx, 0, 0))                             # deepest corner, left wall
        corners.append((container.length_cm - dx, container.width_cm - dy, 0))       # deepest corner, right wall

    RETURN [c for c in corners if c is within container bounds]   # drop any that a large box makes invalid
```

Because the anchors depend on the box's own dimensions, corner seeding is evaluated **per box during the corner-filling phase**, not once up front: for each of the first boxes in `boxes_sorted`, compute that box's four corner anchors under its assigned posture and try them in order. `decode()` (Section 5.3.1) reflects this by starting its extreme-point list at the door origin only and consulting `corner_points_for` while the corner phase is still active.

Following the paper directly (Section 2.3.3): corner loading uses a "first matching strategy" rather than Section 5.2.1's best-fit scoring - once a box can be placed at one of the 4 corner points at all (passing every check in Section 5.2's rejection chain), it is placed there immediately, without evaluating whether a different posture or a different corner would score higher. Scoring is deliberately skipped here since the sole objective of this phase is to occupy the four corners, not to optimize each one individually. Once all 4 corners are filled (or no remaining box fits any of them), extreme points are updated from the newly-placed boxes' dimensions and the search proceeds exactly as Section 5.2 describes for everything else.

**For LCL (Section 4.5), the two deepest corners must be withheld from every customer except the last one.** This is not a refinement - offering all four corners in LCL mode breaks the plan outright. With the corrected ascending sort (Section 5.5), the first boxes through the corner phase belong to **customer 1**, the earliest-delivered, who must end up nearest the door. If those boxes are allowed to take the `x = length_cm - dx` corners, customer 1's cargo lands at the very back of the container. Nothing rejects it at that moment, because Section 5.2's LIFO check only compares a candidate against boxes *already placed*, and at that point there are none from later customers. The damage surfaces afterwards: every subsequent position for customers 2 and 3 now sits in front of customer-1 cargo that has to come out first, so the LIFO check rejects all of them. A worked 3-customer example makes the scale clear - after the corner phase seeds two customer-1 boxes at the deep corners, **all 16 candidate positions tested for customers 2 and 3 were rejected**, none accepted. Restricting the deep corners to the last customer's segment keeps the corner-first benefit (the back corners still get filled, by the cargo that belongs there) while making the failure structurally impossible rather than something the rejection chain has to clean up after.

#### 5.2.3 Downward projection of dangling points

**Problem this solves**: because boxes and blocks (Section 5.1) can differ in footprint size, a box with a smaller footprint stacked on top of a wider one leaves part of the wider box's top face - and the extreme points generated there - hanging over open space rather than resting on anything. A placeable point generated at such a location does not correspond to a position where a new box could actually sit, since nothing is directly beneath it. Matches the paper's own treatment of this case directly (paper Section 2.3.1, Fig. 8).

**Strategy**: whenever a newly-generated extreme point (Section 5.2's three-points-per-placement rule) does not have solid support directly beneath it - i.e. it does not sit exactly on top of a placed box's top face or the container floor - project it straight down (decreasing z) until it lands on the first surface it meets (another box's top face, or the container floor at z=0). The original dangling point is discarded; the projected point replaces it in the extreme-point list.

```
FUNCTION project_point_down(point, placed_boxes, container):
    (x, y, z) = point
    IF (x, y) is directly supported at height z:      # by a placed box's top face or z == 0
        RETURN point   # no projection needed, already valid

    candidate_z = highest top-face height, among placed boxes whose
                  footprint covers (x, y), that is strictly below z
    IF no such box exists:
        candidate_z = 0   # falls all the way to the container floor

    RETURN (x, y, candidate_z)
```

This runs as part of the same bookkeeping step that adds new extreme points after each placement (Section 5.2's "add the 3 new extreme points generated by this placement" line) - every newly-generated point is checked and, if dangling, projected down before it is added to the list a later placement search can draw from.

#### 5.2.4 Exploding blocks back into individual boxes

**Problem this solves**: Block Generation (Section 5.1) exists purely to speed up and regularize the search in Sections 5.2-5.3 by letting many boxes be placed, scored, and searched over as a single object. It is not, and was never meant to be, the unit a Supervisor sees or a crew loads against - nobody physically picks up a "block," they pick up individual cartons. If a block's placement is reported and rendered as-is, the output shows one giant cuboid where a large `Qty_Cartons` run used to be, which is both visually misleading (it looks like one oversized piece of cargo that doesn't exist) and operationally useless (there is no pick-list instruction that corresponds to "carry this 1100 cm object"). Every block placement in the GA's final decoded plan (Section 5.3.1) must therefore be expanded back into its constituent boxes before Section 6 ever sees the plan - this is a required step, not an optional cleanup pass.

**Strategy**: this is possible precisely because Section 5.1 requires every block to carry `contents` - the original boxes it was built from, each with a position already recorded relative to the block's own origin corner. Once a block itself has a final placement (an absolute position and a posture, from `decode()`, Section 5.3.1), each of its contained boxes' absolute position is just that block position combined with the box's own relative offset, adjusted for whichever posture the block was placed under (the same posture applies to every box inside it, since a block cannot be internally re-oriented once formed - Section 5.1's `This_Way_Up` inheritance rule already guarantees every contained box permits that posture).

```
FUNCTION explode_blocks(plan):
    exploded_placements = []

    FOR EACH placement IN plan.placements:
        IF placement.is_block:
            FOR EACH (original_box, relative_position) IN placement.contents:
                absolute_position = transform relative_position by placement's own
                                     posture and absolute position (Section 5.3.1's
                                     posture-to-axis-mapping, Table 1 in the paper,
                                     applies identically here to a box's position
                                     inside its block, not just to the block's own
                                     length/width/height as a whole)
                exploded_placements.append(
                    placed_box(original_box, absolute_position, placement.posture)
                )
        ELSE:
            exploded_placements.append(placement)   # already an individual box; nothing to explode

    RETURN LoadingPlan(
        placements = exploded_placements,
        unplaced_boxes = plan.unplaced_boxes,          # unaffected; already individual boxes (Section 5.1's per-group leftover)
        container = plan.container,
        shipment_type = plan.shipment_type,
    )
```

**This runs exactly once**, on the GA's final best individual's decoded plan (Section 3's Step 5) - never during the search itself. Sections 5.3's fitness function, GA population, and Simulated Annealing's neighbor evaluation all continue to operate on block-level plans throughout the entire search, since that is precisely the performance benefit Section 5.1 exists to provide; only the one plan that actually gets reported is exploded. Running `explode_blocks` on every individual during the search (instead of once, at the end) would silently throw away all of Section 5.1's speed benefit for no gain, since fitness only needs the loaded volume, weight, and constraint status - all of which are identical whether computed from the block or from its exploded contents (a block's volume is its actual cargo volume plus whatever the `min_fill_ratio` gap allows, and that sum is invariant under exploding).

**Everything downstream of this point - Section 6's visualization, pick list, and data contract, and the `run_placements` database table (Section 8.5) - operates on the exploded plan only.** No block ever reaches Section 6; a block is purely an internal Section 5.1-5.3 concept, invisible past this point. Each exploded box placement still carries its own `PO_Number`, `Description`, `Weight_kg`, and other `item_master`/`packing_list` fields (Section 2) unchanged from before it was ever combined into a block, so nothing about the box's own reported identity is lost or altered by having spent Sections 5.1-5.3 inside a block.

### 5.3 Genetic Algorithm with embedded Simulated Annealing (metaheuristic module)

This is the primary search driver, directly following the source paper's own architecture (paper Section 2.4): a Genetic Algorithm searches over posture assignments across a population of candidate solutions, with elite retention, roulette-wheel selection, multi-point crossover, and a dynamic mutation rate; every few generations, **Simulated Annealing is invoked as a local operator** that refines the current best individual through small random perturbations before the GA continues. This is not two independently-selectable solving stages - SA has no standalone entry point and is never run "instead of" the GA, exactly as in the paper, where SA exists only to sharpen the GA's own best individual, not to replace it as the search driver.

#### 5.3.1 Encoding and decoding

Following the paper directly (paper Section 2.4.1): the box/block list produced by Block Generation (Section 5.1), in the fixed order established by Initial Sort (Section 5.5), is what every individual is indexed against - **the Genetic Algorithm never searches over box order**, only over **posture**. An individual (chromosome) is `S = (s_1, s_2, ..., s_n)`, one posture value per box/block position, where each `s_i` is drawn from that position's permitted posture set: `{1, 2}` if the box/block's `This_Way_Up` is `True`, or `{1,2,3,4,5,6}` if `False` (Section 4.2). A random individual is generated by independently sampling a permitted posture for every position.

```
FUNCTION generate_individual(boxes_sorted):
    individual = []
    FOR EACH box IN boxes_sorted:
        permitted_postures = {1, 2} IF box.this_way_up ELSE {1, 2, 3, 4, 5, 6}
        individual.append(random choice from permitted_postures)
    RETURN individual


FUNCTION decode(container, boxes_sorted, individual):
    # boxes_sorted: fixed processing order from Section 5.5 - this function
    # never reorders it. individual: one posture per position, indexed the
    # same way as boxes_sorted - this is the part that varies across
    # individuals, and the only thing Section 5.3's search ever changes.
    plan = new empty loading plan
    extreme_points = [ (0, 0, 0) ]                   # door corner (x=0)
    corner_phase = True                              # Section 5.2.2 corner-first; anchors are
                                                     # computed per box via corner_points_for()

    FOR i, box IN enumerate(boxes_sorted):
        posture = individual[i]
        best, reason = find_best_placement(box, posture, extreme_points, plan.placements, container)

        # POSTURE REPAIR (see note below): the chromosome's posture is only a
        # first preference, never the final word. If it doesn't fit anywhere,
        # try this box's other permitted postures before giving up on it.
        IF best is None:
            permitted = {1, 2} IF box.this_way_up ELSE {1, 2, 3, 4, 5, 6}
            FOR EACH alt IN permitted, excluding `posture`:
                best, reason = find_best_placement(box, alt, extreme_points, plan.placements, container)
                IF best is not None:
                    posture = alt
                    individual[i] = alt       # write the working posture back into the gene
                    BREAK

        IF best is None:
            plan.unplaced_boxes.append((box, reason))   # reason: 'no_space' or 'lifo_blocked' (Section 4.5)
        ELSE:
            place box at best position under `posture`
            plan.placements.append(placed_box)
            remove the used extreme point
            new_points = the 3 new extreme points generated by this placement
            project_point_down(p, plan.placements, container) for each dangling p in new_points  # Section 5.2.3
            add new_points to extreme_points
            prune dominated extreme points   # Section 5.2

    RETURN plan
```

**Why posture repair exists, and why it is a deliberate deviation from the paper**: in the paper, a decoded individual uses exactly the postures its chromosome specifies, and a box whose posture doesn't fit simply isn't loaded - acceptable there, because the paper's objective is maximizing loaded volume (its Section 2.4.2), so a few unloaded items are a cost the search naturally trades against. Under Section 4.3's objective, they are not a cost to trade - leaving a carton out is the primary failure mode the whole system exists to prevent. Without repair, whether every carton gets placed depends on the GA happening to evolve a feasible posture at *every one* of `n` chromosome positions simultaneously, which is a lot to ask of a stochastic search when a single unlucky gene is enough to strand a box that would have fit perfectly in one of its other permitted orientations.

Repair makes the chromosome a *preference* the search optimizes rather than a constraint the decoder is bound by, so the GA's remaining job is improving fill rate and balance among plans that already place everything - which is exactly the tier structure Section 5.3.2's fitness function encodes. Writing the working posture back into the gene (`individual[i] = alt`) makes this a **Lamarckian** repair: the discovered fix is inherited rather than rediscovered from scratch every generation, so crossover and mutation build on it. The cost is a small extra decode-time expense in the cases where the first-choice posture fails - bounded by at most 5 extra `find_best_placement` calls for a non-`This_Way_Up` box, and at most 1 for a `This_Way_Up` one - paid only on boxes that would otherwise have gone unplaced.

`decode()` is called once per individual to evaluate its fitness (below), and once more on the GA's final best individual to produce the loading plan that gets reported (Section 6). Unplaced boxes are recorded, never dropped silently - exactly as in the paper's own decoding (Section 5.2's "reason" bookkeeping carries through unchanged).

#### 5.3.2 Fitness and penalty functions

Following the paper's own evaluation function directly (paper Eq. 12-16), adapted to this system's objective ordering (Section 4.3: placing every carton strictly outranks fill rate, and fill rate strictly outranks balance/load-bearing refinement):

```
E = sum of volume of every placed box/block in the plan     # paper Eq. 12

B1, B2, B3 = center-of-gravity deviation on X, Y, Z, in cm    # Section 5.4.2, paper Eq. 13
# Normalized to container size before use here - see the note below on
# why the raw (unbounded, cm-scale) B1-B3 cannot be plugged in directly.
B1_norm = B1 / (container.length_cm / 2)
B2_norm = B2 / (container.width_cm / 2)
B3_norm = B3 / (container.height_cm / 2)

B4 = 1 if every load-bearing capacity check passes, else 0   # Section 5.4.1, paper Eq. 14
B5 = 1 if every support/stability check passes, else 0       # Section 4.4 constraint 4a, paper Eq. 15

fill_term = (E / container.volume) - (cog_weight * (B1_norm + B2_norm + B3_norm))   # bounded in [-3*cog_weight, 1]

fitness = -(count(plan.unplaced_boxes) * UNPLACED_RANK_WEIGHT)
          + fill_term
          + (0 IF (B4 == 1 AND B5 == 1) ELSE INFEASIBLE_PENALTY)

# INFEASIBLE_PENALTY (Section 7) must be more negative than the worst
# possible feasible fitness, so that no infeasible plan can ever
# outrank any feasible one. The worst feasible fitness is bounded below
# by -(total_box_count * UNPLACED_RANK_WEIGHT) - 3*cog_weight (every box
# unplaced, worst possible balance), so:
#     INFEASIBLE_PENALTY = -(total_box_count * UNPLACED_RANK_WEIGHT) - 1000
# computed once per run from the actual box count, not hard-coded.
```

**Why B4/B5 are an additive penalty here, not the paper's multiplicative gate**: the paper multiplies by B4 and B5, so any load-bearing or stability violation zeroes the fitness outright. That works in the paper's own setting because its fitness (`E`, loaded volume) is always non-negative, so multiplying by zero is unambiguously the worst possible score. **It stops working the moment an unplaced-box term is added**, because that term makes fitness negative whenever anything is left out - and multiplying a negative number by zero makes it *larger*, i.e. better. Worked through concretely: a plan that violates load-bearing but places everything scores `(0.90) * 0 = 0.00`, while a fully valid plan that leaves one carton out scores `-2.0 + 0.85 = -1.15`. The infeasible plan wins, and the "defensive check" ends up rewarding exactly the violation it was meant to rule out. Switching to a large additive penalty removes the sign interaction entirely: infeasible plans land far below every feasible one regardless of how bad that feasible one is.

Both this system's decoder (Section 5.2's `find_best_placement`) and the paper's own already enforce constraints 1-5 and 7 (Section 4.4), plus LIFO when LCL is active (Section 4.5), as hard per-placement gates - so B4 and B5 should evaluate to `1` for every individual by construction, and exist as a defensive backstop rather than as the mechanism doing the enforcing. That is precisely why the penalty's *magnitude* doesn't need tuning: if it ever fires at all, something upstream is already broken, and the only requirement is that such an individual be unambiguously discarded rather than accidentally promoted. **Center-of-gravity (constraint 6) is different** - it is a property of the whole plan, not any single placement (Section 5.2's note on this), so it cannot be a hard per-placement gate the way B4/B5 are; it is folded in as the `cog_weight * (B1+B2+B3)` penalty term instead, following the paper's own Eq. 16 structure exactly. **The unplaced-box term has no equivalent in the paper's Eq. 16** because the paper's own objective is fill-rate maximization outright (its Section 2.4.2 states the goal as maximizing `E`, the loaded volume) - this system's objective ordering (Section 4.3) is stricter, so the same strict-lexicographic `UNPLACED_RANK_WEIGHT` term used in this guide's earlier SA-only design is carried over unchanged: any weight strictly greater than `1.0` guarantees reducing the unplaced count by one box always improves fitness more than any possible fill-rate-or-balance swing could, since `raw_fitness / container.volume` is bounded in `[0, 1]` by construction (`E` can never exceed the container's own volume, and the penalty term only ever reduces it further). `UNPLACED_RANK_WEIGHT` defaults to 2.0 (Section 7) for the same reason given in the guide's earlier SA-only draft: a clean, memorable constant with comfortable margin above the `1.0` minimum, not a "how much do we care" dial - that question is answered categorically by Section 4.3, not by degree.

**`cog_weight`** (Section 7) is, by contrast, a genuine tunable penalty weight in the paper's own sense (unlike `UNPLACED_RANK_WEIGHT`) - it trades off how strongly balance is favored against how strongly fill rate is favored *among plans that already place the same number of cartons*, mirroring exactly how the paper's own Eq. 16 subtracts `(B1+B2+B3)` from `E` before normalizing. It must stay small enough that no plausible `(B1+B2+B3)` value can ever rival the `1.0`-scale gap `UNPLACED_RANK_WEIGHT` already guarantees between unplaced-count tiers, so that balance can only ever break ties among equally-complete plans, never justify leaving a carton unplaced - the same lexicographic-safety reasoning this guide's earlier CoG-as-penalty sketch already worked out (see Section 5.4.3's note on this bound).

#### 5.3.3 GA operators

Following the paper directly (paper Section 2.4.3):

**(1) Selection**: **rank-based** roulette selection, combined with **elite retention** - the best individual(s) of each generation (a configured elite fraction, Section 7) are copied unchanged into the next generation, so a high-quality solution can never be lost to the algorithm's own stochastic selection.

**This deviates from the paper's Eq. 17 (`G_i = fitness_i / sum(fitness)`) for a hard mathematical reason, not a stylistic one.** Fitness-proportional roulette requires non-negative fitness values. The paper's fitness is loaded volume, always `>= 0`, so it qualifies. This system's fitness (Section 5.3.2) is **negative whenever any box is unplaced** - which is most of the population in early generations, exactly when selection pressure matters most. Feeding negative values into `f_i / sum(f)` doesn't merely degrade: it inverts. With a population scoring `[0.85, -3.15, -5.15, -9.15]` (sum `-16.60`), the resulting probabilities are `[-0.05, 0.19, 0.31, 0.55]` - the *worst* individual draws the highest probability and the *best* draws a negative one. The GA would then evolve steadily away from good solutions.

Rank-based selection sidesteps this by discarding the fitness magnitudes and using only their ordering, which is well-defined for any sign:

```
FUNCTION rank_based_selection(population, fitnesses, count):
    ranked = population sorted by fitness ASCENDING   # worst first, best last
    n = size of population
    # Linear ranking: worst gets weight 1, best gets weight n.
    weights = [1, 2, ..., n]
    RETURN `count` individuals sampled from `ranked` with probability
           proportional to `weights` (with replacement)
```

This preserves the one property selection actually needs - better individuals are more likely to reproduce - while being completely immune to fitness sign, scale, or the large discontinuities `UNPLACED_RANK_WEIGHT` and `INFEASIBLE_PENALTY` deliberately introduce. It also makes the lexicographic objective (Section 4.3) behave sensibly under selection: an individual that places one more carton always ranks above one that doesn't, so it always gets a higher selection weight, without the enormous fitness gap between the two tiers causing one individual to monopolize the entire population the way fitness-proportional selection would.

**(2) Crossover**: multi-point crossover. Two integers are randomly drawn from `[1, n]` (`n` = chromosome length) as crossover points; swapping the gene segments between the two parents at those points produces two children. Applied with a configured probability (paper default: 70%); if crossover doesn't fire, the parents pass through unchanged.

**(3) Mutation**: random mutation with a **dynamic mutation rate**. At each selected gene position, a new posture is redrawn from that position's permitted set (Section 5.3.1) - which may coincide with the original posture. The rate itself adapts: if the population's best fitness shows no improvement over a configured number of generations, the rate increases (up to a configured ceiling, paper default 50%); once improvement resumes, the rate decreases back down (to a configured floor, paper default 5%).

```
FUNCTION crossover(parent1, parent2, crossover_probability):
    IF random() >= crossover_probability:
        RETURN parent1, parent2   # unchanged

    n = length of parent1
    point_a, point_b = two distinct random integers in [1, n], sorted
    child1 = parent1[:point_a] + parent2[point_a:point_b] + parent1[point_b:]
    child2 = parent2[:point_a] + parent1[point_a:point_b] + parent2[point_b:]
    RETURN child1, child2


FUNCTION mutate(individual, boxes_sorted, mutation_rate):
    FOR i IN range(length of individual):
        IF random() < mutation_rate:
            permitted_postures = {1, 2} IF boxes_sorted[i].this_way_up ELSE {1, 2, 3, 4, 5, 6}
            individual[i] = random choice from permitted_postures
    RETURN individual
```

**For LCL (Section 4.5)**: crossover and mutation operate on posture values only, never on box order (Section 5.3.1) - the box/block list itself is fixed by Initial Sort before the GA ever runs, so there is no risk of the GA's own operators reordering customers or breaking the customer-segment structure Section 4.5's LIFO design depends on. The LIFO safety net lives entirely inside `decode()` (Section 5.3.1's `find_best_placement` call), which every individual - however its posture genes were produced - passes through identically.

#### 5.3.4 Simulated Annealing as the GA's local operator

Following the paper directly (paper Section 2.4.3(4)): every configured number of generations (paper default: 5), Simulated Annealing takes the **current best individual** in the population and refines it through a localized random search, rather than searching independently over the whole population or over box order.

**Neighbor generation**: a stochastic single-posture perturbation - pick one random position in the individual and redraw its posture from that position's permitted set (Section 5.3.1). This is deliberately a minimal, local move (paper: "randomly altering the placement posture of a single cargo within the individual"), not the swap/block-insertion moves this guide's earlier SA-only draft used - those moved boxes around in *processing order*, which no longer exists as a search dimension now that Initial Sort (Section 5.5) fixes it once, up front, and the GA (Section 5.3.1) searches only over posture.

```
FUNCTION run_simulated_annealing(container, boxes_sorted, best_individual, best_fitness):
    current = copy of best_individual
    current_fitness = best_fitness
    sa_best = current
    sa_best_fitness = current_fitness

    temperature = initial_temperature   # Section 7, or auto-tuned (see below)

    WHILE temperature > min_temperature:
        neighbor = copy of current
        i = random position in neighbor
        permitted_postures = {1, 2} IF boxes_sorted[i].this_way_up ELSE {1, 2, 3, 4, 5, 6}
        neighbor[i] = random choice from permitted_postures

        neighbor_fitness = fitness of decode(container, boxes_sorted, neighbor)   # Section 5.3.2
        delta = neighbor_fitness - current_fitness

        IF delta > 0:
            current, current_fitness = neighbor, neighbor_fitness
        ELSE IF random() < exp(delta / temperature):
            current, current_fitness = neighbor, neighbor_fitness   # accept a worse state, escape local optima

        IF current_fitness > sa_best_fitness:
            sa_best, sa_best_fitness = current, current_fitness

        temperature *= cooling_rate   # Section 7

    RETURN sa_best, sa_best_fitness   # only returned if it beats the GA's own best_individual (see below)
```

**Auto-tune** (optional, via a command-line flag): instead of a hand-set initial temperature, sample a number of random neighbors from the current best individual, measure the standard deviation (sigma) of fitness deltas, and set the initial temperature to roughly `2 * sigma`. This calibrates the starting temperature to the actual problem instance instead of using a fixed constant.

**Why SA is validated against a GA-without-SA baseline, not assumed to help**: the paper's own experiments (its Table 2, comparing a plain GA against GA+SA on the BR10-BR15 instances) show GA+SA outperforming GA alone in every tested group, which is the empirical basis for including it as a local operator rather than treating it as a purely theoretical improvement. This system inherits that same justification - SA is expected to help because refining an already-good individual through small local perturbations, with occasional uphill moves to escape local optima, is strictly a bonus on top of what the GA's own crossover/mutation/elitism already find, never a replacement for it. `run_simulated_annealing`'s return value only replaces the GA's current best individual if `sa_best_fitness > best_fitness` - SA is a pure refinement step, so it can never make the GA's tracked best individual worse.

#### 5.3.5 Full GA loop

```
FUNCTION run_genetic_algorithm(container, boxes_sorted):
    population = [ generate_individual(boxes_sorted) for _ in range(population_size) ]   # Section 7, default 30
    best_individual = None
    best_fitness = -infinity
    stagnant_generations = 0
    mutation_rate = base_mutation_rate   # Section 7, paper default range 0.05-0.5

    FOR generation IN 1..max_generations:   # Section 7, default 40
        fitnesses = [ fitness of decode(container, boxes_sorted, ind) for ind in population ]   # Section 5.3.2

        gen_best_idx = index of max(fitnesses)
        # MIN_IMPROVEMENT (Section 7, default 0.01) gates what counts as
        # real progress for stagnation purposes - see the note below on
        # why a bare `>` comparison here is not enough.
        IF fitnesses[gen_best_idx] > best_fitness + MIN_IMPROVEMENT:
            best_individual, best_fitness = population[gen_best_idx], fitnesses[gen_best_idx]
            stagnant_generations = 0
            mutation_rate = max(min_mutation_rate, mutation_rate * 0.9)   # improvement -> cool the rate down
        ELSE:
            stagnant_generations += 1
            mutation_rate = min(max_mutation_rate, mutation_rate * 1.1)   # stagnation -> heat the rate up
            IF fitnesses[gen_best_idx] > best_fitness:   # smaller-than-threshold gain: still worth KEEPING, just doesn't reset patience
                best_individual, best_fitness = population[gen_best_idx], fitnesses[gen_best_idx]

        IF generation MOD sa_interval == 0:   # Section 7, default every 5 generations
            sa_individual, sa_fitness = run_simulated_annealing(container, boxes_sorted, best_individual, best_fitness)   # Section 5.3.4
            IF sa_fitness > best_fitness + MIN_IMPROVEMENT:
                best_individual, best_fitness = sa_individual, sa_fitness
                stagnant_generations = 0        # SA found a MEANINGFUL improvement; this is not a stagnant generation
            ELSE IF sa_fitness > best_fitness:
                best_individual, best_fitness = sa_individual, sa_fitness   # keep the marginal gain, but it does not reset patience

        # EARLY STOPPING: `stagnant_generations` was already being tracked to
        # drive the dynamic mutation rate; this uses the same counter as a
        # stop condition. Most runs converge well before `max_generations`,
        # and every generation past convergence costs a full population of
        # decodes for nothing (Section 7's runtime note). The mutation rate
        # has already been heating up throughout this stagnant stretch, so by
        # the time the patience window is exhausted the search has had its
        # best chance to break out and hasn't - continuing is very unlikely
        # to help.
        #
        # WHY `MIN_IMPROVEMENT` MATTERS, NOT JUST `> best_fitness`: Simulated
        # Annealing's stochastic local search (Section 5.3.4) very often
        # finds SOME nonzero improvement even from an already-converged
        # individual - a fitness gain of 0.0003 is common and means nothing.
        # Resetting the stagnation counter on any positive delta lets SA
        # indefinitely postpone early stopping through a long trickle of
        # negligible gains, defeating the point of having a patience budget
        # at all: a simulated 200-generation run with a converged GA
        # population, refined only by SA's marginal finds every 5th
        # generation, ran to generation 135 before the ORIGINAL (threshold-
        # free) version of this check ever triggered - the patience window
        # was 10 generations, so it should have stopped by generation ~15.
        # Gating "resets the counter" on a fitness gain larger than
        # `MIN_IMPROVEMENT` (Section 7, default 0.01) fixes this while still
        # keeping every improvement found, however small - see the loop body
        # above, where a sub-threshold gain still updates `best_fitness` but
        # does not reset `stagnant_generations`.
        IF stagnant_generations >= early_stop_patience:   # Section 7, default 10
            BREAK

        elites = top (elite_fraction * population_size) individuals by fitness   # Section 7
        selected = rank_based_selection(population, fitnesses, population_size - size of elites)   # Section 5.3.3(1)

        next_generation = list(elites)
        WHILE size of next_generation < population_size:
            parent1, parent2 = pick two from selected
            child1, child2 = crossover(parent1, parent2, crossover_probability)   # Section 5.3.3(2)
            child1 = mutate(child1, boxes_sorted, mutation_rate)                  # Section 5.3.3(3)
            child2 = mutate(child2, boxes_sorted, mutation_rate)
            next_generation.append(child1)
            IF size of next_generation < population_size:
                next_generation.append(child2)

        population = next_generation

    RETURN best_individual, best_fitness
```

The pipeline's Step 5 (Section 3.1) calls `decode(container, boxes_sorted, best_individual)` one final time to produce the loading plan, then `explode_blocks(plan)` (Section 5.2.4) once on that result before it reaches Section 6 - the same `decode()` function used throughout the search, so the reported plan is guaranteed to be exactly what the returned fitness score describes (blocks and all), with the explode step being the one and only place that block-level plan gets converted into the individual-box plan a Supervisor and loading crew actually need to see.

### 5.4 Load-bearing capacity and center-of-gravity (constraints 5 and 6, Section 4.4)

This section gives the concrete formulation behind the `B1-B4` terms used in Section 5.3.2's fitness function, directly mirroring the paper's own Eq. 8-10 and Eq. 13-14.

#### 5.4.1 Load-bearing capacity (numeric)

This extends the categorical stackability check (Section 4.4, constraint 4b) with a running numeric total, directly mirroring the paper's `D_i <= R_i` formulation (paper Eq. 8).

```
FUNCTION passes_load_bearing_check(candidate_box, candidate_position, placed_boxes):
    # direct supporters = boxes whose top face is exactly at the
    # candidate's z (the same set the physical-support check in
    # Section 4.4/constraint 4a already identifies)
    direct_supporters = boxes in placed_boxes whose top face touches
                         candidate_position.z and whose footprint
                         overlaps the candidate's footprint

    FOR EACH supporter IN direct_supporters:
        # weight already resting on `supporter` from everything above
        # it in the stack, PLUS the candidate's own weight about to be
        # added on top of it
        accumulated_load = sum of weight of every box currently resting
                            (directly or transitively, through other
                            boxes) on top of `supporter`
                          + candidate_box.weight_kg

        IF accumulated_load > supporter.max_load_bearing_kg:
            RETURN False   # this supporter would be overloaded

    RETURN True
```

Notes:

- `accumulated_load` is a running total up the stack, the same way `D_i` in the paper is defined recursively (`D_i = sum over boxes j directly on i of (m_j + D_j)`, paper Eq. 8) - a box 3 levels down feels the combined weight of everything above it, not just its immediate neighbor.
- `max_load_bearing_kg` defaults to a very large number when `Max_Load_Bearing_kg` is blank in `item_master.csv` (Section 2.3), so this check is a safe no-op until real capacity figures exist for a given item - it never blocks placements just because the data hasn't been collected yet.
- This is a **hard per-placement gate** in `find_best_placement`'s rejection chain (Section 5.2), exactly like constraints 1-4 and 7 - a candidate placement that would overload any supporter is rejected outright, the same way a candidate that overlaps another box is rejected. It also underlies the `B4` term in Section 5.3.2's fitness function as the defensive re-check the paper's own Eq. 14 provides.

#### 5.4.2 Center of gravity (balance)

This is a whole-plan property, not a per-placement check (Section 5.2's note on this), directly mirroring the paper's own formulation (paper Eq. 9-10, 13).

```
FUNCTION compute_center_of_gravity(placed_boxes):
    total_weight = sum of placed_boxes' weight_kg
    IF total_weight == 0:
        RETURN (container.length_cm / 2, container.width_cm / 2, container.height_cm / 2)

    # weighted average of each box's own geometric center, weighted by
    # its weight - valid as a mass-center proxy specifically because
    # this warehouse's cargo has fairly uniform density (Section 4.4,
    # constraint 6), so geometric center and mass center are close
    weighted_x = sum(box.weight_kg * box.geometric_center_x for box in placed_boxes) / total_weight
    weighted_y = sum(box.weight_kg * box.geometric_center_y for box in placed_boxes) / total_weight
    weighted_z = sum(box.weight_kg * box.geometric_center_z for box in placed_boxes) / total_weight

    RETURN (weighted_x, weighted_y, weighted_z)


FUNCTION center_of_gravity_penalty(placed_boxes, container, cog_config):
    # cog_config carries the configured safe-zone bounds, mirroring the
    # paper's [conx1, conx2], [cony1, cony2], conz1 (paper Eq. 9) - these
    # are config values (like Minimum support ratio, Section 7), not
    # hard-coded percentages, so they can be tuned per fleet/route
    # without a code change
    (gx, gy, gz) = compute_center_of_gravity(placed_boxes)

    ideal_x = container.length_cm / 2   # paper Eq. 10: conx = x0 + L/2
    ideal_y = container.width_cm / 2    # paper Eq. 10: cony = y0 + W/2
    ideal_z = container.height_cm / 2   # paper Eq. 10: conz = z0 + H/2

    B1 = abs(gx - ideal_x)   # paper Eq. 13
    B2 = abs(gy - ideal_y)   # paper Eq. 13
    B3 = max(0, gz - ideal_z)   # paper Eq. 13 caps how HIGH the center of mass can sit, not how low

    RETURN B1, B2, B3
```

`B1`, `B2`, `B3` feed directly into Section 5.3.2's fitness function as `cog_weight * (B1 + B2 + B3)`, exactly mirroring the paper's own Eq. 16 structure - a penalty subtracted from loaded volume, not a hard gate, since (as Section 5.2 already notes) no single placement in isolation determines whether the whole plan ends up balanced.

#### 5.4.3 Keeping the center-of-gravity penalty a tie-breaker, never a trade against completeness

`B1`, `B2`, `B3` (Section 5.4.2) are absolute distances in centimeters - unbounded in principle, and large in practice: for a 40HC container, a center of gravity pinned at a far corner gives `B1+B2+B3` on the order of 850 cm. Plugging that directly into the fitness function, scaled only by `cog_weight`, breaks the objective ordering Section 4.3 requires: at the guide's own default `cog_weight = 0.3`, the raw penalty for a badly-balanced-but-complete plan can reach roughly `0.3 * 850 = 255` - which dwarfs `UNPLACED_RANK_WEIGHT = 2.0` by two orders of magnitude and would let balance concerns outrank completeness for dozens of unplaced boxes at once, exactly the failure mode this guide corrected `UNPLACED_RANK_WEIGHT` and `INFEASIBLE_PENALTY` to prevent everywhere else. **This is why Section 5.3.2 normalizes `B1`, `B2`, `B3` against half the container's own length/width/height before applying `cog_weight`** - `B1_norm = B1 / (length/2)`, and so on - so each normalized term is naturally on a `[0, ~1]` scale regardless of the container's actual dimensions, the same way `fill_term`'s other component (`E / container.volume`) already is.

With normalization in place, `cog_weight` (Section 7, default 0.3) needs only to stay small enough that it can never rival the gap `UNPLACED_RANK_WEIGHT` guarantees between unplaced-count tiers - the worst possible normalized penalty is `3 * cog_weight` (all three axes maximally deviated at once), so keeping `cog_weight` well under `UNPLACED_RANK_WEIGHT / 3` (i.e. well under `0.67` at the current default) preserves that margin with room to spare. This mirrors exactly how the paper's own Eq. 16 keeps the `(B1+B2+B3)` penalty subordinate to `E` (loaded volume) rather than letting it dominate - the differences here are that this system normalizes the terms first (the paper's `E` and `B1-B3` are already on comparable raw scales in its own units, so it never needed to), and adds one more tier (unplaced count) above both.

### 5.5 Initial sort (parsing module)

Applied once, before the Genetic Algorithm runs, and re-applied to the block/box list that Block Generation (Section 5.1) produces - the order this second pass leaves behind is the one every chromosome position is indexed against (Section 5.3.1), and nothing after it ever reorders the list again:

```
sort key = (Customer_Sequence ascending, Stacking_Group ascending, Volume descending, Weight_kg descending)
```

`Customer_Sequence` **ascending** (primary key, **LCL only**): a number derived from the order `Customer_Code` values first appear in the packing list (Section 4.5) - the earliest-delivered customer gets sequence 1 and is sorted first, so their boxes are placed first and, because the placement search fills outward from the door (Section 4.1's door-at-x=0 plus Section 5.2.1's smaller-x tie-break), end up nearest the door - exactly where LIFO needs them to be. **Section 4.5's point 1 explains at length why this must be ascending and not descending**, including the worked 3-customer example where the descending direction strands 6 of 9 boxes; that reasoning is not repeated here, but it is the single most important thing to get right in this sort. In the FCL case (a single `Customer_Code`, or the column absent), every box shares the same sequence number, so this key is constant across the whole list and contributes nothing - the sort collapses to exactly the three-key form below with no special-casing required.

`Stacking_Group` ascending (secondary key): sturdier Group-1 items are considered before lighter Group-2 items, naturally tending to put them lower in any stack. Applied *within* each customer's segment in the LCL case, or across the whole list in the FCL case - the same comparison either way, just scoped by whatever the primary key already grouped.

`Volume` descending (tertiary key): largest items first, directly following the paper's own encoding order (paper Section 2.4.1) - big items placed early secure contiguous space, whereas placing small items first fragments the container into gaps too small for anything large to fit later. This matters more here than it does in the paper, because Section 4.3 makes completeness the primary objective and box *order* is the one lever the Genetic Algorithm never gets to adjust (Section 5.3.1 searches posture only) - a bad order cannot be recovered from later in the pipeline, so it has to be right up front.

`Weight_kg` descending (quaternary key): classic heaviest-first bin-packing tie-break among items of near-identical volume; also aids stability by tending to put denser items lower.

**Why `Volume` is a separate key rather than letting `Weight_kg` stand in for it**: an earlier revision of this guide used `Weight_kg` descending alone as the tertiary key, reasoning that "heavier items are usually also bigger, for fairly uniform-density solid wood furniture." Measured against this warehouse's actual catalog, that reasoning does not hold: weight and volume correlate at only **0.27** across all items (0.68 within Stacking_Group 1, 0.63 within Group 2). The catalog mixes dense flat-packed cartons with bulky-but-light assembled ones, so weight is a poor proxy - e.g. the single largest Group-2 carton by volume (a recliner sofa chair, ~1.4 m³) sorts *fifth* by weight, behind four much smaller items, and a 0.18 m³ nightstand sorts ahead of a 0.83 m³ rocking chair. Sorting big-first by actual volume, with weight kept as the tie-break beneath it, restores the paper's own intent without discarding the stacking-safety and delivery-order keys above it.

**Relationship to the source paper**: the paper sorts purely by volume descending (Section 2.4.1). This system keeps that as a key but subordinates it to `Stacking_Group` (and, for LCL, `Customer_Sequence`): since Group-2 items can never support anything (Section 4.4, constraint 4b), processing sturdy Group-1 items first is what keeps the placement search physically valid as it goes, regardless of size - a large Group-2 item placed early would otherwise occupy floor space that a later, smaller Group-1 item might have needed to be underneath it.

This is a sensible constructive order on its own (delivery order first when it matters, load-bearing items before what rests on them, heavy-before-light for stability), but on its own it does nothing to stop many identical-size boxes from piling into a narrow tower at a single extreme point instead of spreading across the container - this is exactly the failure mode Block Generation (Section 5.1) exists to fix, by consolidating those identical-size boxes into a single block object before this sort or the placement search ever sees them individually.

---

## 6. Output

Two artifacts are produced from the loading plan (visualization module), plus a console summary (entry-point module). A layer-by-layer walkthrough view (step through the container's height/depth one course at a time, as mentioned in Section 1.5's typical flow) is not implemented yet, but Section 6.3's data contract already carries everything such a view would need (each placement's position and dimensions) - it would be a new rendering step consuming the same loading-plan object, not a change to the solver.

### 6.1 3D HTML visualization (default `outputs/loading_plan.html`, path configurable via command-line flag)

A single self-contained HTML file (three.js via CDN, no server needed). Built from the exploded plan (Section 5.2.4) - the loading plan passed into this rendering step has already had every block placement expanded back into its original individual boxes, so nothing described below ever needs to distinguish a block from a box; there is no such thing as a block by the time this section runs.

3D viewport:

- Container rendered as a grey wireframe box, sized to actual length/width/height, with a floor plane, grid, and a "FLOOR" label.
- A translucent blue "DOOR" panel marks the **x = 0** face (the `width_cm × height_cm` face - the unload/entry face, short end of the container, per Section 4.1's coordinate convention).
- **Every placed box rendered as a solid, semi-transparent, edged cuboid at its true position and dimensions - one cuboid per real, individual carton, never one cuboid per block.** This is the direct visual payoff of Section 5.2.4's explode step: a `Qty_Cartons` run of 24 identical boxes that Section 5.1 combined into one block for the search shows up here as 24 separate cuboids at their own true positions, exactly as a Supervisor or loading crew would need to see them to actually load or verify the container - not as one oversized cuboid that doesn't correspond to any single physical object.
- Color mapping depends on shipment type (Section 4.5): for **FCL**, color is mapped to `Stacking_Group` exactly as before - one color for Group 1 (sturdy, load-bearing) and another for Group 2 (must not carry weight), so the stacking arrangement is visually verifiable at a glance. For **LCL**, color is instead mapped to `Customer_Code` (one distinct color per customer), since verifying that each customer's cargo is cleanly segmented front-to-back is the more operationally important check for a multi-stop load - `Stacking_Group` is still enforced by the solver either way, it just isn't what the color channel is spent showing when there's a more pressing thing to verify visually.
- Orbit/zoom camera controls (drag to rotate, scroll to zoom).

Side panel:

- Container type name and dimensions (length x width x height, in cm).
- **Shipment type badge**: "FCL" or "LCL" (Section 4.5's detection result), shown prominently since it changes what the color mapping above means and what the load sequence list below includes.
- Stat tiles, in priority order per Section 4.3's objective (all cartons placed matters more than density): boxes placed / boxes unplaced (the unplaced count is the most prominent tile, not a middling one - shown in a warning color and visually largest/first when greater than 0, since this is the one number that tells the Supervisor whether the run actually succeeded), fill rate percent (secondary), weight used / max (kg), and center of gravity - `(gx, gy, gz)` against the container's ideal center with a pass/fail badge for the configured safe zone (Section 5.4.2), tertiary alongside fill rate since balance is itself a tie-breaking concern (Section 5.3.2), never traded against completeness.
- Load sequence list: every placed box, in load order (the order the GA's final decode, Section 5.3.1, placed it). Each row shows: sequence number, a color swatch matching its 3D box, description, PO number, and its y position in cm. **For LCL**, each row additionally shows the customer code and a visual grouping/divider between customer segments, so the Supervisor can confirm at a glance that each customer's cargo forms one clean block rather than being interleaved.
- **Center of gravity indicator**: the computed `(gx, gy, gz)` (Section 5.4.2) marked as a small crosshair inside the 3D viewport, alongside the container's ideal center - a quick visual check that the two are close together, in addition to the numeric stat tile below.

It must have two pages, one for an overview, and one for detailed layer-to-layer from the deepest of the container to the door. On the second page, when workers finish loading a layer, the Supervisor can tick and render the next layer.

This two-page structure is one of the concrete UI screens specified in Section 8 (System Architecture) - see Section 8.4, "Loading Plan Viewer", for how it fits into the overall web application, and Section 8.4's "Layer Walkthrough" screen for the tick-to-advance interaction in detail.

### 6.2 Console summary (entry-point module, printed after every run)

```
--- Loading Plan Summary ---
Container        : <container_type>
Shipment type    : <FCL | LCL>
Customers        : <n>              # omitted or "1" for FCL

*** ALL CARTONS PLACED ***         # or, if not:
*** N CARTONS COULD NOT BE PLACED - SEE BELOW ***

Boxes placed     : <n>
Boxes unplaced   : <n>              # breakdown below when > 0 and shipment type is LCL
  - no space       : <n>
  - LIFO-blocked   : <n>
Fill rate        : <pct>%           # secondary metric - see Section 4.3
LIFO rejections  : <n>               # LCL only - candidates rejected only by the LIFO check; see 6.3
Used weight      : <used> / <max> kg
Center of gravity: (<gx>, <gy>, <gz>) cm   # <WITHIN SAFE ZONE | OUTSIDE SAFE ZONE> - see Section 5.4.2

3D visualization : <path to html>
Pick list        : <path to txt>
```

The all-caps banner is deliberate, not decorative: per Section 4.3, whether every carton was placed is the primary result of a run, and a Supervisor scanning a terminal or log full of numbers should not have to parse a `Boxes unplaced: 0` line correctly to know whether the run succeeded - the banner makes success or failure legible at a glance, before any of the numeric detail below it.

The `no space` / `LIFO-blocked` breakdown (Section 6.3's `reason` field) is only printed for LCL runs with unplaced boxes - for FCL, `lifo_blocked` can never occur (Section 4.5), so showing a permanently-zero line would be noise rather than information.

The unplaced-cartons banner above (not a separate WARNING line) is what carries this signal; it always points implicitly to the pick list and the `no space`/`LIFO-blocked` breakdown for the operational detail a Supervisor needs to act on it.

### 6.3 Data contract between solving and output (data-model module)

Everything the output layer needs comes off one loading-plan object - **the exploded plan (Section 5.2.4), always**. Nothing described below is ever a block; every row is one real, individual box.

| Field / property | Meaning |
|---|---|
| container | The container this plan was packed against (Section 2.1) |
| shipment_type | `"FCL"` or `"LCL"`, per Section 4.5's automatic detection |
| placements | List of placed **individual boxes** (never blocks - Section 5.2.4 has already exploded every block placement by the time this object exists), in load order (the order the GA's final decode, Section 5.3.1, placed them, preserved through the explode step). Each placement carries `customer_code` alongside the fields already listed in Section 8.5's `run_placements` table, present (and meaningful) for LCL, constant for FCL |
| unplaced boxes | List of boxes that could not be placed anywhere, each tagged with why: `no_space` (failed on ordinary geometry/weight/stacking grounds) or `lifo_blocked` (would have fit if not for the LIFO check, LCL only - Section 5.2's `find_best_placement`) - always reported |
| used volume | Sum of placed box volumes |
| used weight | Sum of placed box weights |
| fill rate | Used volume divided by container volume |
| center of gravity | `(gx, gy, gz)`, the plan's actual computed center of gravity (Section 5.4.2), plus whether it falls within the configured safe zone |
| unload order | Placements reversed; the practical unload sequence (last box in is the first one accessible at the door) |
| lifo_rejections | Count of candidate placements rejected specifically by the LIFO check (Section 5.2's `find_best_placement`) during the final decode - `null`/absent for FCL, a non-negative integer for LCL. See the note below for what it's for. |

**To change the output format**: everything downstream reads from this loading-plan object only. Add new fields there first if new data is needed, then extend the relevant rendering step (HTML or text) in the visualization module to surface it.

**Making LIFO's fill-rate cost visible, not just its result**: Section 4.5 notes that LIFO is a genuine constraint on the search space for LCL runs - some placements that would improve fill rate are rejected outright because they'd block an earlier customer's cargo. A Supervisor comparing an LCL run's fill rate against a typical FCL run for a similarly-sized packing list should be able to tell *why* it's lower, rather than reading it as the solver simply doing a worse job. `lifo_rejections` (the table row above) is how: it counts every candidate placement rejected specifically by Section 5.2's LIFO check - as opposed to rejected by ordinary geometry/weight/stacking grounds - during the final decode (Section 5.3.1), alongside `boxes_placed`/`boxes_unplaced` rather than requiring a separate constraint or search behavior to compute. A high count is a direct, visible explanation for a lower-than-usual fill rate on an LCL run.



---

## 7. Tunable Parameters Reference (config module)

**Block generation and placement (Sections 5.1-5.2)**

| Parameter | Default | Effect |
|---|---|---|
| Tolerance gap | 2 cm | Minimum clearance enforced between adjacent boxes and between boxes and container walls, in X/Y only (Section 4.4, constraint 7) |
| Minimum support ratio | 0.8 | Min. fraction of footprint that must be supported to stack (1.0 = no overhang); paper's own baseline is 0.5 (Section 4.4, constraint 4a) |
| Block similar-size fill ratio | 0.98 | Min. actual-cargo-volume fraction a general block of similar-sized items must reach to be accepted (Section 5.1, paper's own value) |
| Max block fraction (`max_block_fraction`) | 0.4 | Caps any single block's extent, on any axis, at this fraction of the container's own extent on that axis (Section 5.1) - prevents a large `Qty_Cartons` run of identical-size boxes from combining into one block that spans nearly the whole container; a genuine tunable trade-off between block-generation's speed/regularity benefit and leaving the placement search enough separate objects to interleave |
| Score weight - residual volume | 1.0 | Weight on (negative) wasted residual volume in placement scoring (Section 5.2.1) |
| Score weight - contact ratio | 1.0 | Weight on contact-area ratio in placement scoring (Section 5.2.1, paper Eq. 11) |
| Max load-bearing default | very large (effectively unlimited) | Used when `Max_Load_Bearing_kg` is blank for an item (Section 2.3, Section 5.4.1) |

**Genetic Algorithm and embedded Simulated Annealing (Section 5.3)**

| Parameter | Default | Effect |
|---|---|---|
| GA population size | 30 | Number of individuals per generation (Section 5.3.5). The paper uses 100, tuned for its own BR/LN benchmark instances; 30 is this system's default - see the runtime note below |
| GA max generations | 40 | Upper bound on generations (Section 5.3.5). The paper uses 100; with early stopping below, most runs finish well short of this either way |
| GA early-stop patience | 10 | Stop once the best fitness has not improved by at least `Minimum improvement threshold` for this many consecutive generations (Section 5.3.5) - reuses the `stagnant_generations` counter that already drives the dynamic mutation rate |
| Minimum improvement threshold | 0.01 | The smallest fitness gain, in a single generation or from one Simulated Annealing invocation, that counts as real progress for early-stop purposes (Section 5.3.5). Smaller gains still update `best_fitness`, they just don't reset the patience counter - without this, SA's frequent sub-threshold finds can indefinitely postpone early stopping (a simulated converged run kept going to generation 135 against a patience of 10 before this fix) |
| GA crossover probability | 0.7 | Probability multi-point crossover fires on a selected parent pair (Section 5.3.3(2), paper default) |
| GA mutation rate - base | 0.05-0.5 | Starting range for the dynamic mutation rate (Section 5.3.3(3), paper default range) |
| GA mutation rate - floor | 0.05 | Minimum the dynamic mutation rate can cool down to on sustained improvement (paper default) |
| GA mutation rate - ceiling | 0.50 | Maximum the dynamic mutation rate can heat up to on sustained stagnation (paper default) |
| GA elite fraction | 0.10 | Fraction of each generation copied unchanged into the next (elite retention, Section 5.3.3(1)) |
| Unplaced rank weight | 2.0 | Guarantees placing one more carton always outranks any fill-rate-or-balance difference in the GA's fitness (Section 5.3.2) - not a tunable trade-off; keep above 1.0 |
| Infeasible penalty | `-(total_box_count * 2.0) - 1000`, computed per run | Additive penalty applied when B4 or B5 fails (Section 5.3.2). Not a dial: it only has to be more negative than the worst feasible fitness so an infeasible plan can never outrank a feasible one. Must be computed from the run's own box count, not hard-coded |
| CoG penalty weight (`cog_weight`) | 0.3 | Weight on the *normalized* center-of-gravity deviation penalty `(B1_norm+B2_norm+B3_norm)` in the fitness function (Section 5.3.2, paper Eq. 16) - a genuine tunable trade-off between balance and fill rate among equally-complete plans; keep under `Unplaced rank weight / 3` (≈0.67 at current defaults, Section 5.4.3) so the worst-case penalty can never outweigh a single unplaced box |
| SA interval | every 5 generations | How often Simulated Annealing is invoked as a local operator on the GA's best individual (Section 5.3.4, paper default) |
| SA initial temperature | 100 °C | Starting SA temperature (ignored if auto-tune is enabled; paper default) |
| SA minimum temperature | 1 °C | Temperature at which the SA local-search loop stops (paper default) |
| SA cooling rate | 0.9 | Per-iteration geometric cooling multiplier (paper default) |
| CoG safe-zone tolerance (`x/y_tolerance_min/max`, `z_tolerance_max`) | ± 5% of length/width; +10% of height | Bounds defining the safe zone around the container's ideal center of gravity (Section 5.4.2, paper's `conx1/conx2`, `cony1/cony2`, `conz1`) |

All are overridable via command-line flags on the entry-point module.

**Runtime budget - why the GA defaults above are smaller than the paper's.** The paper's own settings (population 100, 100 generations) cost about **10,880 full `decode()` calls** per run: 10,000 from the GA itself, plus SA firing every 5 generations (20 times) for 44 iterations each under the listed temperature schedule (100 -> 1 at x0.9). Each decode places every block/box through the full Placeable Point Strategy (Section 5.2), and in pure Python over a 150-200 carton shipment (Section 2.2) that lands in the tens-of-minutes-to-hours range - far past what a Supervisor waiting on a loading plan will tolerate.

This system's defaults (population 30, 40 generations, early-stop patience 10) cut that to **1,552 decodes worst case, and ~670 on a typical run that converges around generation 18** - roughly 7x and 16x reductions respectively:

| One decode takes | Worst case (no early stop) | Typical (converges ~gen 18) |
|---|---|---|
| 0.1 s | ~2.6 min | ~1.1 min |
| 0.3 s | ~7.8 min | ~3.4 min |
| 0.5 s | ~12.9 min | ~5.6 min |

That is consistent with the "tens of seconds to a few minutes" figure Sections 8.1 and 8.6 assume when justifying the async job pattern - which is the point of choosing these defaults rather than the paper's. The paper's instances are also a poor guide here: its BR/LN benchmarks rarely repeat one exact carton size more than a handful of times, whereas this warehouse's packing lists routinely put 20+ identical cartons on a single line, so Block Generation (Section 5.1) shrinks the unit count far more aggressively here than it does there, and a smaller population searches a correspondingly smaller space.

If a run does need more search effort, raise `GA population size` before `GA max generations` - a wider population explores more posture combinations per unit of wall-clock time than a longer run of a narrow one, and early stopping already truncates generations that aren't earning their cost. Only after that is it worth profiling the decode itself; the extreme-point scan and overlap checks (Section 5.2) are the hot path.

---

## 8. System Architecture (Web Application)

Sections 1-7 describe the solver as a standalone, offline computation: read 3 CSVs, run Steps 1-5 (Section 3), write an HTML file and a text pick list to disk. That solver does not change in this section - everything below is the application wrapped around it so a Supervisor can drive it from a browser instead of a command line, and so a loading plan becomes something the warehouse can look up, revisit, and walk through on the floor, not just a one-off file dropped in an `outputs/` folder. **"Web application" here means a local browser UI talking to a local backend, not a hosted or internet-facing service** - see Section 8.6 for why this stays a single offline machine, and why the REST/async architecture below is still worth it even without a real network involved.

### 8.1 Architecture style and why

**Three tiers**: a browser-based frontend, a backend API that owns the solver and a small database, and the database itself. This is a conventional client-server web architecture, not a novel design - the reasoning below is about *why* this fits this specific problem, which is what matters for defending the choice.

**Why the solver needs to sit behind an API, not run client-side**: the solver (Sections 3-5) is existing Python - this system's constructive/metaheuristic modules are Python, consistent with the source paper's own experimental setup (its Section 3, "Algorithm implementation language: Python 3.9"). Browsers don't run Python. The two conventional options are (a) rewrite the solver in JavaScript/WASM to run entirely client-side, or (b) keep the solver in Python, run it server-side, and expose it over HTTP. Option (a) means maintaining two implementations of the same constraint logic (Section 4.4) in two languages, or a nontrivial transpilation step, for a Phase-1 prototype - not a good trade for a graduation-project timeline. Option (b) keeps exactly one solver implementation, reuses it unchanged, and is the standard shape for this kind of "long-running compute behind a UI" problem. This guide assumes (b).

**Why not a request-response API (call solver, wait, get HTML back)**: a plain synchronous endpoint (`POST /solve` that blocks until the solver finishes, then returns the result) is the simplest possible design, and would be fine if the solver reliably finished in a couple of seconds. It doesn't: the Genetic Algorithm with embedded Simulated Annealing (Section 5.3), even at this system's deliberately reduced defaults (population 30, up to 40 generations with early stopping - Section 7's runtime note explains why these are smaller than the paper's own 100/100), takes on the order of one to several minutes end-to-end for a shipment in the 150-200 carton range this warehouse actually ships (the packing lists in Section 2 are sized accordingly) - each generation requires decoding every individual in the population through the full Placeable Point Strategy (Section 5.2), and SA's own local-search loop (Section 5.3.4) adds further decode calls each time it runs. A synchronous HTTP request held open that long is fragile in practice - browser and reverse-proxy default timeouts commonly sit well under that, the Supervisor has no way to tell "still working" from "stuck," and closing the browser tab or losing WiFi for a moment loses the whole run with no way to check on it afterward. Section 8.3 uses an asynchronous job pattern instead: submit a run, get a job ID back immediately, poll (or receive a push notification via WebSocket, Section 8.3) for status, fetch the result once done. This is the standard fix for "this backend operation is slow enough that the browser shouldn't wait synchronously," and it is worth defending as a deliberate choice in a graduation thesis: it is what turns an unpredictable multi-minute Python computation into a UI that stays responsive and honest about what it's doing. This reasoning holds even when everything runs on one local machine with no internet involved (Section 8.6) - a `localhost` request can still block the browser tab for minutes at a time, and the Supervisor still needs to see progress rather than a frozen page.

**Why a database at all, for something that reads 3 CSVs**: today, the solver's *inputs* are CSVs (Section 2) and its *outputs* are files (Section 6) - nothing persists between runs except whatever files happen to still be sitting in `outputs/`. That is fine for a one-off script, but a Supervisor-facing DSS needs to answer "what did we ship in container 40HC-0512 last Tuesday," "show me every run against this packing list," or "did this SKU's dimensions get corrected before or after the run that used them" - questions a stateless file-in/file-out tool cannot answer once the files are overwritten or moved. The database (Section 8.5) is what turns each solver run from a disposable file artifact into a queryable record. `item_master` and `packing_list` (Section 2) move from CSV files into database tables the frontend can read and write through the API (Section 8.4's "Data Management" screens); `container_spec` (Section 2.1) becomes a small reference table the Supervisor picks from instead of a file passed on a command line.

### 8.2 High-level component diagram

```
+-----------------------------------------------------------------+
|                        BROWSER (Frontend)                       |
|                                                                   |
|  Packing List   Item Master    Container   Solver Run   Loading  |
|    Editor         Editor         Picker      Trigger    Plan     |
|                                                          Viewer   |
|                                                       (3D + Layer |
|                                                        Walkthrough)|
+---------------------------+---------------------------------------+
                            | HTTP (REST) + WebSocket (job status)
                            v
+-----------------------------------------------------------------+
|                      BACKEND API (FastAPI)                       |
|                                                                   |
|   Routers:  /containers  /items  /packing-lists  /runs           |
|                                                                   |
|   Job Queue / Background Worker                                  |
|     -> wraps the EXISTING Section 3 pipeline unchanged:          |
|        Parse & Join -> Initial Sort -> Constructive Heuristic    |
|        -> (optional) Simulated Annealing -> Loading Plan object  |
|                                                                   |
|   Serialization layer:                                           |
|     -> Loading Plan object (Section 6.3) => JSON for the API     |
|        (replaces/supplements the HTML-file output of Section 6.1;|
|        the frontend's 3D Loading Plan Viewer renders this JSON   |
|        with three.js in-browser instead of opening a static file)|
+---------------------------+---------------------------------------+
                            | SQL
                            v
+-----------------------------------------------------------------+
|                    DATABASE (Section 8.5)                        |
|   containers | items | packing_lists | packing_list_lines |     |
|   runs | run_placements | run_unplaced                          |
+-----------------------------------------------------------------+
```

The solver core (the box in the middle labeled "wraps the EXISTING Section 3 pipeline unchanged") is exactly Sections 3-5 of this guide, called as a function - `run_pipeline(container, boxes) -> LoadingPlan` - not rewritten. Everything in Section 8 is new wrapping around that one function call.

### 8.3 Backend API design

**Stack**: FastAPI (Python) chosen specifically because it sits directly on top of the existing Python solver with zero translation layer, gets interactive API documentation (Swagger/OpenAPI) generated automatically from the route definitions - useful for a thesis defense demo, since the API is self-documenting without extra slide-writing - and has first-class async support, which the job-queue pattern below depends on.

**Endpoints**, grouped by resource:

```
Containers
  GET    /containers                 list the container catalog (Section 2.1)
  POST   /containers                 add a container spec
  GET    /containers/{id}            fetch one

Items (item_master, Section 2.3)
  GET    /items                      list all carton types
  POST   /items                      add a new item
  GET    /items/{item_id}            fetch one
  PUT    /items/{item_id}            update dimensions/weight/stacking/etc.
  DELETE /items/{item_id}            remove (only if unreferenced by any packing list)

Packing Lists (Section 2.2)
  GET    /packing-lists              list uploaded/created packing lists
  POST   /packing-lists              create one (paste rows, or see CSV upload below)
  POST   /packing-lists/upload       upload a CSV matching Section 2.2's schema; validated
                                      against Section 2.2/2.3's rules before it's accepted
  GET    /packing-lists/{id}         fetch one, with its lines expanded and joined
                                      against item_master (Section 2.4's row-to-box join,
                                      but surfaced here for the Supervisor to review BEFORE
                                      committing to a run - catches bad data early)
  PUT    /packing-lists/{id}         edit lines
  DELETE /packing-lists/{id}

Runs (a solver invocation against one packing list + one container)
  POST   /runs                       body: {packing_list_id, container_id, options}
                                      -> immediately returns {run_id, status: "queued"}
  GET    /runs/{run_id}              -> {status: "queued"|"running"|"done"|"failed",
                                          progress (see below), result (once done)}
  GET    /runs/{run_id}/result       -> the full Loading Plan (Section 6.3) as JSON
  GET    /runs/{run_id}/pick-list    -> the text pick list (Section 6.2), for printing
  GET    /runs                       list past runs (filterable by packing list, container,
                                      date range) - this is what makes "what did we ship
                                      last Tuesday" (Section 8.1) answerable
  WS     /runs/{run_id}/ws           WebSocket: pushes status/progress updates as they
                                      happen, so the frontend doesn't have to poll (below)
```

**Why `POST /runs` returns immediately instead of blocking**: this is the asynchronous job pattern flagged as necessary in Section 8.1. The handler's job is only to validate the request, enqueue the work, and return a `run_id` - it does not itself run the solver. A separate background worker (a FastAPI `BackgroundTasks` call for the simplest version, or a proper task queue like Celery/RQ with Redis if the prototype needs to survive a backend restart mid-run) picks up the job, calls the *exact same* `run_pipeline(container, boxes)` function Section 3 already describes, and writes the result to the database (Section 8.5) when done.

**Progress reporting during a long run**: since the Genetic Algorithm (Section 5.3.5) runs a bounded number of generations (`GA max generations`, Section 7 - default 40; early stopping may finish sooner, so the bar should be treated as an upper bound that can jump straight to complete), the worker can report `progress = current_generation / max_generations` at a regular interval (e.g. every generation) without any change to Section 5.3's algorithm itself - just an optional callback invoked inside the existing `FOR generation IN 1..max_generations` loop. Simulated Annealing's own local-search loop (Section 5.3.4), when it fires every `sa_interval` generations, is fast relative to a full GA generation (it only ever decodes single-posture perturbations of one individual, not a whole population) and does not need its own separate progress signal - it is reported as part of whichever generation invoked it. Block Generation (Section 5.1), which runs once before the GA starts, is a single deterministic pass with no natural "percent done" signal, so during that phase the frontend simply shows an indeterminate spinner with a text label ("Combining cargo into blocks..."); generation-level progress-bar granularity applies once the Genetic Algorithm starts.

**Polling vs. WebSocket**: polling (`GET /runs/{run_id}` every 1-2 seconds from the frontend) is simpler to build and is a completely adequate default for a Phase-1 prototype - it needs no new infrastructure beyond the REST endpoints already listed. The WebSocket endpoint is listed as an upgrade path, not a requirement: it removes polling overhead and gives snappier progress-bar updates, but the two are interchangeable from the frontend's perspective (both end up updating the same "run status" piece of UI state, Section 8.4), so start with polling and add the WebSocket only if the UI feels sluggish in practice.

**Validation happens at the API boundary, not just in the solver**: Section 2's validation rules (positive dimensions, `Stacking_Group` in {1,2}, foreign-key integrity between `packing_list` and `item_master`, etc.) are enforced on `POST`/`PUT` to `/items` and `/packing-lists` *before* anything is stored - a bad row is rejected with a clear error message at the moment it's entered or uploaded, not discovered later when a run silently produces a worse plan than it should have. This is a stricter posture than a one-shot CLI script needs, precisely because the database (Section 8.5) is now a persistent, shared source of truth that many runs will read from - one bad row entered once can quietly corrupt every future run that touches it if it isn't caught at the door.

### 8.4 Frontend screens

**Stack choice**: any component-based framework works (React, Vue, Svelte); this guide doesn't mandate one, since the screen list and data contracts below are framework-agnostic. Whichever is chosen, the 3D viewport (Loading Plan Viewer, below) reuses three.js - the same library Section 6.1's standalone HTML file already uses - just fed live JSON from the API (Section 8.3) instead of having the scene baked into a static file at solve-time.

**Screen list**:

1. **Item Master editor** - a table view over `GET/POST/PUT/DELETE /items`, mirroring `item_master.csv`'s columns (Section 2.3) as form fields, with the same validation rules (Section 2.3) surfaced as inline field errors rather than a rejected request the user has to decode.

2. **Packing List editor / uploader** - either paste/build rows directly against `POST /packing-lists`, or drag-and-drop a CSV matching Section 2.2's schema to `POST /packing-lists/upload`. After upload, show the resolved join against `item_master` (dimensions, weight, stacking group per line) so the Supervisor can visually sanity-check the shipment - e.g. spot a suspiciously heavy line - before spending a solver run on it. **Also surface the FCL/LCL detection result (Section 4.5) here**, immediately after upload/paste - a distinct-`Customer_Code`-count badge ("FCL" or "LCL - N customers") - so the Supervisor knows before running whether LIFO will apply, rather than discovering it only after the run completes. If LCL, the preview table should visually group/order rows by customer in the order they'll be delivered (i.e. the order they already appear in the file, per Section 2.2/4.5), so an accidentally-interleaved upload (customer A, B, A, B instead of A, A, B, B) is visible and fixable before it reaches the solver.

3. **Container picker** - a simple dropdown/list over `GET /containers`, reflecting Section 2.1's "Supervisor selects the container per the Booking Notes before the solver runs" step (Section 1.3). This is a selection UI, never a multi-select or "let the system choose" control, since Section 1.3 is explicit that container choice is fixed upstream, not searched over by the solver.

4. **Run Trigger + Status** - a "Run" button that calls `POST /runs` with the selected packing list + container (+ optionally the GA generation/population counts and the tolerance gap value, from Section 7's tunable parameters, exposed as an "Advanced options" collapse rather than surfaced by default, since most day-to-day runs shouldn't need them touched). Simulated Annealing is not a separate on/off toggle here, since it has no standalone mode (Section 5.3) - it is always embedded in the Genetic Algorithm's run, invoked automatically every `SA interval` generations. This transitions into the progress view described in Section 8.3 (indeterminate spinner during the Block Generation phase, then a generation-by-generation progress bar once the Genetic Algorithm starts). This screen owns the polling or WebSocket subscription (Section 8.3) and is the only screen that needs to know a run is "in flight."

5. **Loading Plan Viewer** - the screen Section 6.1 already specifies the content for; this is where that content lives in the web app instead of a standalone HTML file. **Two pages**, exactly as Section 6.1 requires:

   - **Overview page**: the full 3D scene at once - every placed box, colored by `Stacking_Group` (FCL) or `Customer_Code` (LCL), per Section 6.1's shipment-type-dependent color mapping - the door panel, the shipment-type badge, the stat tiles (fill rate, boxes placed/unplaced, weight used/max, plus `lifo_rejections` when LCL), and the load-sequence list (with customer grouping when LCL) - all sourced from one `GET /runs/{run_id}/result` call. This is a like-for-like port of Section 6.1's existing content into a page that reads from the API instead of being pre-rendered into a static file.

   - **Layer Walkthrough page**: steps through the container one layer at a time, **floor first, then progressively higher courses** - a "layer" here is a Z-height band (all boxes whose z falls within the current band are shown), since that is how a loading crew actually builds up a container physically. The Supervisor has a "Layer complete, next layer" control; ticking it advances the view to reveal the next layer's boxes rather than showing everything at once. Within a layer, boxes are still rendered at their true x/y position, so the crew can see depth-from-door (x, per Section 4.1's door-at-x=0 convention) and left/right placement (y) exactly as they'll encounter it while loading. This is a pure rendering/UI-state feature - it needs no new backend endpoint beyond the same `GET /runs/{run_id}/result` the Overview page already calls, since Section 6.3's placement data (each box's x, y, z, and dimensions) already contains everything needed to group boxes into layers and reveal them incrementally; the layering logic lives entirely in the frontend.

6. **Run History** - a table over `GET /runs`, filterable by packing list, container, and date range, answering the "what did we ship last Tuesday" question from Section 8.1. Each row links to that run's Loading Plan Viewer (screen 5) and its pick list (`GET /runs/{run_id}/pick-list`, Section 6.2) for reprinting.

**What stays out of scope for this prototype** (candidate Phase-2 UI work, not addressed here): user accounts/authentication, multi-warehouse or multi-tenant support, editing a loading plan by hand after the solver produces it (drag-and-drop box repositioning), and side-by-side comparison of two runs against the same packing list. None of these change Sections 2-7's solver contract if added later - they are all screens or endpoints layered on top of the same `LoadingPlan` object and `runs` table (Section 8.5).

### 8.5 Database schema

**Choice of database**: any relational database works (PostgreSQL, SQLite); the schema below is written database-agnostic. SQLite is a reasonable default for a Phase-1 prototype specifically - zero setup, a single file, easy to hand in alongside the code for a thesis submission - with a straightforward upgrade path to PostgreSQL later since the schema doesn't use anything SQLite-specific.

Seven tables. The first three are near-direct translations of Section 2's CSV schemas into relational form; the rest exist to persist solver runs (Section 8.1's core justification for having a database at all).

```sql
-- Section 2.1
CREATE TABLE containers (
    id                  INTEGER PRIMARY KEY,
    container_type      TEXT NOT NULL,
    internal_length_cm  REAL NOT NULL CHECK (internal_length_cm > 0),
    internal_width_cm   REAL NOT NULL CHECK (internal_width_cm > 0),
    internal_height_cm  REAL NOT NULL CHECK (internal_height_cm > 0),
    max_weight_kg       REAL NOT NULL CHECK (max_weight_kg > 0)
);

-- Section 2.3
CREATE TABLE items (
    item_id               TEXT PRIMARY KEY,
    description           TEXT NOT NULL,
    length_cm             REAL NOT NULL CHECK (length_cm > 0),
    width_cm              REAL NOT NULL CHECK (width_cm > 0),
    height_cm             REAL NOT NULL CHECK (height_cm > 0),
    weight_kg             REAL NOT NULL CHECK (weight_kg > 0),
    this_way_up            BOOLEAN NOT NULL,
    stacking_group        INTEGER NOT NULL CHECK (stacking_group IN (1, 2)),
    max_load_bearing_kg   REAL CHECK (max_load_bearing_kg IS NULL OR max_load_bearing_kg > 0)
    -- NULL here is exactly Section 2.3's "leave blank/omit" case - the
    -- solver's own default-to-very-large-number behavior (Section 4.4,
    -- constraint 5) is unchanged; the API layer doesn't invent a
    -- database-level default, it just passes NULL through and lets the
    -- solver's existing logic handle it, so there's one place (the
    -- solver) that owns what "missing" means, not two.
);

-- Section 2.2, header
CREATE TABLE packing_lists (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,          -- e.g. "August batch - CUST-A-JP"
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Section 2.2, lines - one row per packing_list.csv row
CREATE TABLE packing_list_lines (
    id                INTEGER PRIMARY KEY,
    packing_list_id   INTEGER NOT NULL REFERENCES packing_lists(id) ON DELETE CASCADE,
    line_order        INTEGER NOT NULL,   -- position in the original packing_list.csv/paste, 0-based
    item_id           TEXT NOT NULL REFERENCES items(item_id),
    po_no             TEXT NOT NULL,
    customer_code     TEXT,               -- NULL/blank = FCL; 2+ distinct values in a packing list = LCL (Section 4.5)
    qty_pcs           INTEGER NOT NULL CHECK (qty_pcs > 0),
    qty_cartons       INTEGER NOT NULL CHECK (qty_cartons > 0)
    -- description is NOT duplicated here (unlike packing_list.csv,
    -- Section 2.2) - now that item_master lives in the same database
    -- as a real table with a foreign key, there's no reason to carry a
    -- denormalized copy of item_master.description alongside it; the
    -- API joins items in whenever a line needs to be displayed
    -- (screen 2, Section 8.4). This removes the "what if item_master's
    -- name changes and packing_list.csv's copy goes stale" risk noted
    -- as an open question when this system was still CSV-only.
);
-- `line_order` exists because, unlike a CSV file, a SQL table has no
-- inherent row order a SELECT is guaranteed to preserve - and Section
-- 2.2/4.5 make packing-list row order a load-bearing input (it's how
-- LCL delivery sequence is expressed). Every read of this table that
-- feeds the solver (Section 3.1's Step 1) MUST `ORDER BY line_order`
-- explicitly; relying on insertion order or any other implicit
-- ordering is exactly the kind of silent-corruption risk Section 2.2
-- already warns about for the CSV case, now reintroduced at the
-- database layer if this column is missing or ignored.

-- One row per solver invocation (Section 8.3's POST /runs)
CREATE TABLE runs (
    id                 INTEGER PRIMARY KEY,
    packing_list_id    INTEGER NOT NULL REFERENCES packing_lists(id),
    container_id       INTEGER NOT NULL REFERENCES containers(id),
    status             TEXT NOT NULL CHECK (status IN ('queued','running','done','failed')),
    shipment_type      TEXT CHECK (shipment_type IN ('FCL','LCL')),  -- NULL until detected at Step 1 (Section 4.5); set before solving starts
    customer_count     INTEGER,             -- distinct Customer_Code count that produced shipment_type; 1 (or NULL) for FCL
    ga_population_size     INTEGER NOT NULL DEFAULT 100,   -- Section 5.3.5 / Section 7 default
    ga_max_generations     INTEGER NOT NULL DEFAULT 100,   -- Section 5.3.5 / Section 7 default
    sa_interval_generations INTEGER NOT NULL DEFAULT 5,    -- how often SA runs as a local operator (Section 5.3.4) / Section 7 default
    cog_penalty_weight      REAL NOT NULL DEFAULT 0.3,     -- Section 5.3.2 / Section 7 default
    tolerance_gap_cm   REAL NOT NULL DEFAULT 2.0,  -- Section 4.4 constraint 7 / Section 7 default
    fill_rate          REAL,                -- NULL until status = 'done' (Section 6.3)
    used_weight_kg     REAL,
    boxes_placed       INTEGER,
    boxes_unplaced     INTEGER,
    lifo_rejections    INTEGER,             -- NULL for FCL; count of placements rejected specifically by the LIFO check (Section 6.3's fill-rate-cost note), for LCL
    center_of_gravity_x_cm REAL,            -- (gx, gy, gz) from the final decode (Section 5.4.2), NULL until status = 'done'
    center_of_gravity_y_cm REAL,
    center_of_gravity_z_cm REAL,
    error_message      TEXT,                -- populated only if status = 'failed'
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at       TIMESTAMP
);

**Why `shipment_type` and `customer_count` are stored per-run instead of derived on the fly every time**: they're cheap to compute (Section 4.5's detection is a single distinct-count over `packing_list_lines.customer_code`), but storing the result at solve time - rather than recomputing it whenever a past run is viewed - keeps a run's record honest if the underlying packing list is later edited (e.g. a customer added after the run already happened). The `runs` row should describe what actually happened during that run, not what today's data would produce if re-detected now.

**Why `tolerance_gap_cm` is stored per-run instead of only as a global config default**: unlike a pure performance knob (GA generation count), the gap value changes the *physical result* of a run - a wider gap means fewer boxes fit, a narrower gap risks a plan that's tighter than a crew can actually work with. Recording the value each run actually used (not just today's global default, which could change later) is what makes a past run's fill rate reproducible and explainable months later - "why did last month's run only reach 82% fill rate" has a real answer if the gap it used is on that row, and no answer at all if only today's config default is available to check against.

-- One row per placed box in a finished run (Section 6.3's "placements")
CREATE TABLE run_placements (
    id            INTEGER PRIMARY KEY,
    run_id        INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    box_id        TEXT NOT NULL,        -- e.g. "DT-8411_3" (Section 2.4's box ID scheme)
    item_id       TEXT NOT NULL REFERENCES items(item_id),
    po_no         TEXT NOT NULL,
    customer_code TEXT,                 -- carried from packing_list_lines; NULL/constant for FCL, meaningful for LCL (Section 4.5)
    x_cm          REAL NOT NULL,
    y_cm          REAL NOT NULL,
    z_cm          REAL NOT NULL,
    length_cm     REAL NOT NULL,        -- as-placed dimensions (post-orientation, Section 4.2)
    width_cm      REAL NOT NULL,
    height_cm     REAL NOT NULL,
    load_sequence INTEGER NOT NULL      -- position in load order (Section 6.3's "placements" order)
);

-- One row per unplaced box in a finished run (Section 6.3's "unplaced boxes")
CREATE TABLE run_unplaced (
    id       INTEGER PRIMARY KEY,
    run_id   INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    box_id   TEXT NOT NULL,
    item_id  TEXT NOT NULL REFERENCES items(item_id),
    po_no    TEXT NOT NULL,
    reason   TEXT NOT NULL CHECK (reason IN ('no_space', 'lifo_blocked'))
    -- 'no_space': every candidate extreme point failed on ordinary
    -- geometry/weight/stacking/load-bearing grounds (Section 4.1's
    -- checks other than the LIFO one) -- the operationally correct
    -- response is a bigger container or a lighter shipment.
    -- 'lifo_blocked': at least one candidate would have fit on every
    -- OTHER ground, but every such candidate was rejected specifically
    -- by the LIFO check (Section 4.5) -- the operationally correct
    -- response is different: reconsider delivery order, split the
    -- shipment, or accept partial LIFO violation as a business
    -- decision. Conflating this with 'no_space' would send a Supervisor
    -- looking for a bigger container to fix a problem that isn't
    -- actually about space at all.
);
```

**Why `run_placements`/`run_unplaced` duplicate box dimensions instead of just joining to `items`**: `items.length_cm`/`width_cm`/`height_cm` are the carton's *declared* dimensions before orientation (Section 2.3); `run_placements.length_cm`/`width_cm`/`height_cm` are the *as-placed* dimensions after the solver chose a posture for that specific box from its permitted set (Section 4.2) - any of the 6 postures may reassign which declared dimension ends up as X, Y, or Z, not just a length/width swap. These can differ per placement, so they have to be stored per-row, not derived by joining back to `items` - otherwise the Loading Plan Viewer (Section 8.4, screen 5) would render every box in its declared orientation regardless of what the solver actually decided.

**Mapping back to Section 6.3's data contract**: a `LoadingPlan` object (Section 6.3) becomes, in this schema, one `runs` row (for the summary fields - fill rate, used weight, boxes placed/unplaced) plus its associated `run_placements` rows (for `placements`, ordered by `load_sequence`) and `run_unplaced` rows (for `unplaced_boxes`). `GET /runs/{run_id}/result` (Section 8.3) assembles exactly this shape back into JSON - the database schema and the solver's own in-memory data contract (Section 6.3) describe the same object, just at rest vs. in memory.

### 8.6 Deployment shape for a prototype

**Offline, single-machine, no internet required.** This warehouse has one Supervisor working at one terminal, so there is no case for internet-facing hosting, authentication, or multi-machine access at this stage - everything below runs entirely on the local network (or a single machine with no network at all). Recommended shape: the FastAPI backend (Section 8.3) and the SQLite database (Section 8.5) run as one process/file on that single machine, bound to `localhost` (or a LAN address if a second terminal in the same warehouse ever needs to reach it - still no internet, just a local network hop); the frontend (Section 8.4) is a static build served either from the same backend (FastAPI can serve static files directly, avoiding a second server entirely) or opened directly in a browser pointed at `localhost`. The background worker (Section 8.3) runs in-process via FastAPI's `BackgroundTasks` for the simplest version - no separate worker process, no Redis, no message broker - which is sufficient as long as it's acceptable for a long-running job to be lost if the backend restarts mid-run. That's a reasonable trade-off for a Phase-1 prototype; swapping in a real task queue (Celery/RQ with Redis, already flagged as an alternative in Section 8.3) so jobs survive a restart is a candidate hardening step for later, not something Section 8.7's build order below assumes is done first.

**Why keep the REST/async architecture (Section 8.1-8.3) instead of going back to a plain desktop app**: running locally removes the browser/reverse-proxy timeout concern that partly motivated the async job pattern in Section 8.1, but the other reason still holds - the Genetic Algorithm with embedded Simulated Annealing (Section 5.3) can take tens of seconds to a few minutes, and a UI that blocks for that long with no progress feedback is a poor experience regardless of whether it's local or remote. Keeping the same `POST /runs` -> poll/WebSocket -> `GET /runs/{run_id}/result` shape costs nothing extra to run locally (it's still just `localhost` calls) and means the exact same code would work unchanged if this warehouse later needs a second terminal on the same local network, or a real server, without a rewrite.

**What this deliberately rules out for now**: user accounts/authentication (only one Supervisor, one machine - nothing to authenticate against), a reverse proxy or TLS/HTTPS setup (no external traffic to protect), and any cloud/hosting decision. All of these are meaningful additions only if the system moves beyond one warehouse's one terminal - not a prototype concern.

### 8.7 Suggested build order

Not a rigid dependency graph - a suggested sequence that keeps something demoable at every step, which matters for a thesis timeline where showing incremental progress is often part of the evaluation itself.

1. **Wrap the existing solver in one API endpoint first**, even synchronous (`POST /solve` that blocks and returns JSON) - this proves the FastAPI-around-Python-solver integration (Section 8.1's core architectural bet) works at all, before spending time on the job-queue machinery in Section 8.3.
2. **Add the database and CRUD endpoints** for containers/items/packing-lists (Section 8.5, 8.3) - this is what lets the frontend stop hard-coding a test packing list and start reading/writing real data.
3. **Convert the solve endpoint to the asynchronous job pattern** (Section 8.3) once the synchronous version is proven - add the `runs` table, background task, polling endpoint.
4. **Build the frontend screens in the order a Supervisor would actually touch them**: Item Master editor -> Packing List editor -> Container picker -> Run Trigger -> Loading Plan Viewer Overview page -> Layer Walkthrough page -> Run History. This order also happens to move from "simplest CRUD screen" to "most novel UI work" (the 3D viewer), which is a reasonable way to de-risk a limited-time project - the parts most likely to take longer than expected come last, once everything they depend on already exists.
5. **WebSocket progress push** (Section 8.3) is explicitly last, and optional - only worth doing if polling turns out to feel sluggish once the rest of the system is working end-to-end.

Notably absent from this list: any deployment/hosting step. Since Section 8.6 fixes this as a single local machine with no internet exposure, there is nothing to provision, containerize, or put behind a domain - running `uvicorn` and opening a browser to `localhost` is the entire "deployment."

---

## 9. Ideas Beyond the Paper (Not Yet Implemented)

Everything in Section 5 - Block Generation, the Improved Placeable Point Strategy with corner-first seeding and contact-ratio scoring, the Genetic Algorithm with elitism and dynamic mutation, and Simulated Annealing as its embedded local operator - is part of the one target algorithm this guide specifies, adapted directly from the source paper, and is in scope for full implementation, not a future phase. This section is different: it is a scratchpad for ideas that go **beyond** what the paper itself does, kept separate precisely because they are optional refinements on top of the complete paper-based algorithm, not part of it. None of this is required for the system to match the paper; all of it is here only in case a specific shortfall shows up in practice and is worth spending extra complexity to fix.

### 9.1 LIFO-aware neighbor moves for Simulated Annealing

Section 5.3.4's Simulated Annealing operator perturbs posture only, never box/block order, because Initial Sort (Section 5.5) fixes processing order once, up front, and the paper's own GA encoding (Section 5.3.1) never searches over it. This is simpler than an order-searching metaheuristic and sidesteps any risk of SA breaking the customer-segment structure Section 4.5's LIFO design depends on - but it also means SA can never discover a cross-customer reordering that would in fact be LIFO-safe and would improve overall fill rate. For instance, a single small box belonging to an earlier customer that geometrically could sit just in front of a later customer's cargo without ever blocking it (Section 4.5's precise X/Z-overlap test, not merely "any later box exists behind it") is never considered, because box order isn't part of the search space at all.

A future extension could add a second, order-aware neighbor move - available only when LCL is active - that proposes a same-customer-segment reordering (not a cross-segment move, which would still need to respect delivery sequence) and evaluates it through the same fitness function (Section 5.3.2). This would only ever be a refinement on top of the paper's own posture-only encoding, layered in as an additional move type SA can pick from, not a replacement for it - and it adds real complexity (every proposed neighbor state would need a full LIFO feasibility check, not just "is this still posture-only"), so it's worth building only if LCL fill rates in practice turn out meaningfully worse than the FCL baseline.

### 9.2 Multiple container types per run

Section 3.2 already notes that comparing multiple container types would sit as a wrapper *around* the existing single-container pipeline (Steps 1-5) - run the same pipeline once per candidate container, then compare the resulting plans - rather than as a change to the pipeline itself. This remains unimplemented and would only become relevant if the Supervisor's own container-selection step (Section 1.3) is ever replaced with a system recommendation instead of a manual choice from Booking Notes.

### 9.3 Editable loading plans and run comparison

Flagged already in Section 8.4's "what stays out of scope" note: letting a Supervisor manually drag-and-drop reposition a box after the solver produces a plan, and viewing two runs against the same packing list side by side. Both are pure UI/data-layer additions on top of the existing `LoadingPlan` object and `runs` table (Section 8.5) - they do not require any change to Section 5's algorithm, since they operate on a plan the algorithm has already produced.
