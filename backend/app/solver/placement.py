from typing import List, Optional, Tuple
from dataclasses import dataclass
from app.config import get_settings
from app.solver.utils import get_unit_item_id
from app.solver.geometry import (
    Dimensions,
    Position,
    BoundingBox,
    Posture,
    ExtremePoint,
    FLOOR_EPSILON,
    generate_extreme_points,
    sort_extreme_points,
    calculate_contact_ratio,
    calculate_residual_volume,
    get_permitted_postures,
    project_point_down,
    prune_dominated_extreme_points,
)
from app.solver.parsing import Box
from app.solver.block_generation import Block
from app.solver.constraints import (
    PlacementCandidate,
    check_all_constraints,
    check_weight_capacity,
    check_non_overlap,
    check_stackability,
    check_lifo,
)


@dataclass
class PlacementResult:
    position: Position
    posture: Posture
    dims: Dimensions
    actual_dims: Dimensions
    score: float


def corner_points_for(box: Box, box_dims: Dimensions, container_dims: Dimensions,
                      shipment_type: str, last_customer_sequence: int) -> List[ExtremePoint]:
    """
    Compute the rear corner anchors for a box in its current posture.

    **Rear corners only**: Anchors to the rear wall (x = L - dx) to strictly
    enforce rear-to-door loading strategy. Door corners (x = 0) are eliminated
    to prevent early blocking and premature scattering of early cargo.

    box_dims should be the *inflated* dimensions (with tolerance gap applied)
    so that the boundary filter at the end is conservative and does not
    silently reject valid rear-wall placements.

    For LCL, the two deep corners are only offered to the last customer's cargo.
    """
    dx, dy, dz = box_dims.length, box_dims.width, box_dims.height

    corners = []
    # --- Deep / rear-wall anchor only (rear-left corner) ---
    if shipment_type == "FCL" or box.customer_sequence == last_customer_sequence:
        # Deepest corner, left wall (x = L - dx, y = 0)
        corners.append(ExtremePoint(container_dims.length - dx, 0, 0))

    # Filter out corners that would place box outside container (large boxes)
    valid = []
    for c in corners:
        if (c.x >= -1e-6 and c.y >= -1e-6 and c.z >= -1e-6 and
                c.x + dx <= container_dims.length + 1e-6 and
                c.y + dy <= container_dims.width + 1e-6 and
                c.z + dz <= container_dims.height + 1e-6):
            valid.append(c)
    return valid


def find_best_placement(
    box: Box,
    placed_boxes: List[BoundingBox],
    placed_boxes_data: List[Box],
    container_dims: Dimensions,
    current_weight: float,
    max_weight: float,
    is_lcl: bool,
    extreme_points: List[ExtremePoint],
    last_customer_sequence: int = 0,
) -> Tuple[Optional[PlacementResult], str]:
    """
    Find the best placement for a box.
    Returns (PlacementResult or None, reason) where reason is 'no_space' or 'lifo_blocked'.
    """
    settings = get_settings()
    if not check_weight_capacity(current_weight, box.weight_kg, max_weight):
        return None, "weight_capacity"

    best_result = None
    best_score = -float('inf')
    saw_lifo_only_rejection = False

    # Extract candidate item_id using the shared helper
    box_item_id = get_unit_item_id(box)

    # Pre-extract item_ids of placed items using the same helper
    placed_item_ids = [get_unit_item_id(p) for p in placed_boxes_data]

    # Pre-calculate dimensions for all permitted postures
    posture_specs = []
    box_dims = Dimensions(box.length_cm, box.width_cm, box.height_cm)
    box_inflated = Dimensions(box.inflated_length, box.inflated_width, box.inflated_height)
    for posture in box.permitted_postures:
        posture_specs.append((
            posture,
            box_dims.apply_posture(posture),
            box_inflated.apply_posture(posture),
        ))

    c_len, c_wid, c_hgt = container_dims.length, container_dims.width, container_dims.height
    contact_wt = settings.CONTACT_RATIO_WEIGHT
    residual_wt = settings.RESIDUAL_VOLUME_WEIGHT
    c_vol = container_dims.volume()
    occupied_vol = sum(
        (b.max_x - b.min_x) * (b.max_y - b.min_y) * (b.max_z - b.min_z)
        for b in placed_boxes
    )

    # Try all extreme points with all permitted postures
    for ep in extreme_points:
        ep_x, ep_y, ep_z = ep.x, ep.y, ep.z

        for posture, dims, inflated_dims in posture_specs:
            # Fast container boundary check
            if (ep_x + inflated_dims.length > c_len or
                ep_y + inflated_dims.width > c_wid or
                ep_z + inflated_dims.height > c_hgt):
                continue

            candidate_bbox = BoundingBox(
                ep_x, ep_y, ep_z,
                ep_x + inflated_dims.length,
                ep_y + inflated_dims.width,
                ep_z + inflated_dims.height,
            )

            # Fast non-overlap check
            if not check_non_overlap(candidate_bbox, placed_boxes):
                continue

            # Stackability check
            if not check_stackability(candidate_bbox, placed_boxes, box, placed_boxes_data):
                continue

            # LIFO check for LCL
            if is_lcl and not check_lifo(candidate_bbox, placed_boxes, placed_boxes_data, box.customer_sequence):
                saw_lifo_only_rejection = True
                continue

            contact_ratio = calculate_contact_ratio(candidate_bbox, placed_boxes, container_dims)
            residual_vol = calculate_residual_volume(candidate_bbox, placed_boxes, container_dims, occupied_vol)

            # Spatial Affinity: calculate contact area with boxes of the same item_id
            same_item_contact_area = 0.0
            if box_item_id and placed_boxes:
                c_min_x, c_max_x = candidate_bbox.min_x, candidate_bbox.max_x
                c_min_y, c_max_y = candidate_bbox.min_y, candidate_bbox.max_y
                c_min_z, c_max_z = candidate_bbox.min_z, candidate_bbox.max_z

                for pb, p_item_id in zip(placed_boxes, placed_item_ids):
                    if p_item_id != box_item_id:
                        continue
                    # 1. Contact in X (front/back faces touch)
                    if abs(c_min_x - pb.max_x) < 1e-4 or abs(c_max_x - pb.min_x) < 1e-4:
                        ov_y = min(c_max_y, pb.max_y) - max(c_min_y, pb.min_y)
                        if ov_y > 1e-4:
                            ov_z = min(c_max_z, pb.max_z) - max(c_min_z, pb.min_z)
                            if ov_z > 1e-4:
                                same_item_contact_area += ov_y * ov_z
                    # 2. Contact in Y (side faces touch)
                    elif abs(c_min_y - pb.max_y) < 1e-4 or abs(c_max_y - pb.min_y) < 1e-4:
                        ov_x = min(c_max_x, pb.max_x) - max(c_min_x, pb.min_x)
                        if ov_x > 1e-4:
                            ov_z = min(c_max_z, pb.max_z) - max(c_min_z, pb.min_z)
                            if ov_z > 1e-4:
                                same_item_contact_area += ov_x * ov_z
                    # 3. Contact in Z (top/bottom faces touch)
                    elif abs(c_min_z - pb.max_z) < 1e-4 or abs(c_max_z - pb.min_z) < 1e-4:
                        ov_x = min(c_max_x, pb.max_x) - max(c_min_x, pb.min_x)
                        if ov_x > 1e-4:
                            ov_y = min(c_max_y, pb.max_y) - max(c_min_y, pb.min_y)
                            if ov_y > 1e-4:
                                same_item_contact_area += ov_x * ov_y

            fp = dims.length * dims.width
            same_item_ratio = (same_item_contact_area / fp) if fp > 0 else 0.0

            # Vertical-fill bonus: reward placing a box on top of existing items
            # (ep_z > 0 means the box is stacking on something, not on the floor).
            # Bonus is proportional to height utilisation so taller stacks get a
            # slightly larger nudge — but it is capped to stay secondary to
            # contact_ratio and same_item_ratio.
            top_fill_bonus = 0.0
            if ep_z > FLOOR_EPSILON:
                top_fill_bonus = 0.8 * (ep_z / c_hgt)

            score = (
                contact_wt * contact_ratio
                + 1.5 * same_item_ratio
                + top_fill_bonus
                - residual_wt * (residual_vol / c_vol)
            )

            # Tie-break: prefer rear-most (larger x), then lower z (gravity/stability), then left-most (smaller y).
            is_better_tie = False
            if best_result is not None and abs(score - best_score) < 1e-9:
                if ep_x > best_result.position.x + 1e-9:
                    is_better_tie = True
                elif abs(ep_x - best_result.position.x) < 1e-9:
                    if ep_z < best_result.position.z - 1e-9:
                        is_better_tie = True
                    elif abs(ep_z - best_result.position.z) < 1e-9:
                        if ep_y < best_result.position.y - 1e-9:
                            is_better_tie = True

            if score > best_score + 1e-9 or is_better_tie:
                best_score = score
                best_result = PlacementResult(
                    position=Position(ep_x, ep_y, ep_z),
                    posture=posture,
                    dims=inflated_dims,
                    actual_dims=dims,
                    score=score,
                )

    if best_result is not None:
        return best_result, "placed"
    elif saw_lifo_only_rejection:
        return None, "lifo_blocked"
    else:
        return None, "no_space"


# Change 4: periodic pruning counter to remove dominated EPs
_PRUNE_INTERVAL = 10


def _add_box_extreme_points(
    box_bbox: BoundingBox,
    extreme_points: List[ExtremePoint],
    seen_points: set,
    placed_bboxes: List[BoundingBox],
    container_dims: Dimensions,
    placement_count: int = 0,
) -> List[ExtremePoint]:
    """Incrementally update extreme points when a new box is placed.

    Change 1: Generates 6 new EPs per placement (3 original + 3 composite).
    Change 4: Every _PRUNE_INTERVAL placements, remove dominated EPs.
    """
    b_min_x, b_max_x = box_bbox.min_x, box_bbox.max_x
    b_min_y, b_max_y = box_bbox.min_y, box_bbox.max_y
    b_min_z, b_max_z = box_bbox.min_z, box_bbox.max_z

    # BUG-06 fix: use closed ±epsilon intervals so EPs sitting exactly on the
    # new box's far face (p.x == b_max_x etc.) are correctly invalidated.
    _EP_EPS = 1e-9
    updated_points = [
        p for p in extreme_points
        if not (
            b_min_x - _EP_EPS <= p.x <= b_max_x + _EP_EPS
            and b_min_y - _EP_EPS <= p.y <= b_max_y + _EP_EPS
            and b_min_z - _EP_EPS <= p.z <= b_max_z + _EP_EPS
        )
    ]

    # Change 1: 6 new EPs (3 original face projections + 3 composite)
    new_points = [
        ExtremePoint(b_max_x, b_min_y, b_min_z),  # original: X-face
        ExtremePoint(b_min_x, b_max_y, b_min_z),  # original: Y-face
        ExtremePoint(b_min_x, b_min_y, b_max_z),  # original: Z-face (top)
        ExtremePoint(b_max_x, b_max_y, b_min_z),  # composite: XY diagonal floor
        ExtremePoint(b_max_x, b_min_y, b_max_z),  # composite: XZ top
        ExtremePoint(b_min_x, b_max_y, b_max_z),  # composite: YZ top
    ]
    c_len, c_wid, c_hgt = container_dims.length, container_dims.width, container_dims.height
    for p in new_points:
        if p.x <= c_len and p.y <= c_wid and p.z <= c_hgt:
            projected = project_point_down(p, placed_bboxes, container_dims)
            if projected not in seen_points:
                seen_points.add(projected)
                updated_points.append(projected)

    # Change 4: Periodic dominance pruning to keep EP list lean
    if placement_count > 0 and placement_count % _PRUNE_INTERVAL == 0:
        updated_points = prune_dominated_extreme_points(updated_points)
        seen_points.clear()
        seen_points.update(updated_points)

    return updated_points


def place_boxes_greedy(
    boxes: List[Box],
    container_dims: Dimensions,
    max_weight: float,
    is_lcl: bool,
    last_customer_sequence: int = 0,
) -> Tuple[List[BoundingBox], List[Box], List[Tuple[Box, str]], float]:
    """Greedy placement with corner-first seeding and downward projection."""
    placed_bboxes = []
    placed_data = []
    unplaced = []  # List of (box, reason)
    current_weight = 0.0

    # Seed initial extreme points with origin (0, 0, 0); real rear anchors
    # depend on box dimensions and come from corner_points_for during corner_phase.
    extreme_points = [ExtremePoint(0, 0, 0)]
    seen_points = {ExtremePoint(0, 0, 0)}
    corner_phase = True
    corner_consecutive_failures = 0  # Change 7: track consecutive failures
    placement_count = 0  # Change 4: for periodic EP pruning

    for box in boxes:
        if corner_phase:
            # Try corner points first
            box_dims = Dimensions(box.length_cm, box.width_cm, box.height_cm)
            # We'll try each permitted posture at corners
            placed_at_corner = False
            
            for posture in box.permitted_postures:
                dims = box_dims.apply_posture(posture)
                # Pass inflated dims so rear-corner boundary check uses padded size
                inflated_dims = Dimensions(box.inflated_length, box.inflated_width, box.inflated_height).apply_posture(posture)
                corners = corner_points_for(box, inflated_dims, container_dims, "LCL" if is_lcl else "FCL", last_customer_sequence)
                
                for corner in corners:
                    pos = Position(corner.x, corner.y, corner.z)
                    candidate = PlacementCandidate(
                        position=pos,
                        posture=posture,
                        dims=Dimensions(box.inflated_length, box.inflated_width, box.inflated_height).apply_posture(posture),
                        actual_dims=dims,
                        box=box,
                    )
                    
                    valid, reason = check_all_constraints(
                        candidate,
                        placed_bboxes,
                        placed_data,
                        container_dims,
                        current_weight,
                        max_weight,
                        is_lcl,
                    )
                    
                    if valid:
                        new_bbox = BoundingBox.from_position_and_dims(pos, candidate.dims)
                        placed_bboxes.append(new_bbox)
                        placed_data.append(box)
                        current_weight += box.weight_kg
                        placed_at_corner = True
                        placement_count += 1
                        extreme_points = _add_box_extreme_points(
                            new_bbox, extreme_points, seen_points, placed_bboxes, container_dims, placement_count
                        )
                        break
                
                if placed_at_corner:
                    break
            
            if placed_at_corner:
                corner_phase = False  # Initial rear anchor established; use find_best_placement for subsequent units to group same SKUs
                continue
            else:
                # Only exit corner phase after 3 CONSECUTIVE failures if no box fit the anchor yet
                corner_consecutive_failures += 1
                if corner_consecutive_failures >= 3:
                    corner_phase = False

        # Normal best-fit search
        sorted_eps = sort_extreme_points(extreme_points)

        result, reason = find_best_placement(
            box,
            placed_bboxes,
            placed_data,
            container_dims,
            current_weight,
            max_weight,
            is_lcl,
            sorted_eps,
            last_customer_sequence,
        )

        if result:
            new_bbox = BoundingBox.from_position_and_dims(result.position, result.dims)
            placed_bboxes.append(new_bbox)
            placed_data.append(box)
            current_weight += box.weight_kg
            placement_count += 1
            extreme_points = _add_box_extreme_points(
                new_bbox, extreme_points, seen_points, placed_bboxes, container_dims, placement_count
            )
        else:
            unplaced.append((box, reason))

    return placed_bboxes, placed_data, unplaced, current_weight


# BUG-01 fix: removed dead duplicate prune_dominated_extreme_points that was
# defined here but never called (the import from geometry.py at line 16 was
# the live version).  Diverging implementations are a maintenance landmine.


def place_blocks_greedy(
    blocks: List[Block],
    container_dims: Dimensions,
    max_weight: float,
    is_lcl: bool,
    last_customer_sequence: int = 0,
) -> Tuple[List[BoundingBox], List[Block], List[Block], float]:
    placed_bboxes = []
    placed_blocks = []
    unplaced = []
    current_weight = 0.0

    # BUG-12 fix: use the same incremental EP strategy as place_boxes_greedy
    # instead of O(N²) full regeneration on every iteration.
    extreme_points = [ExtremePoint(0, 0, 0)]
    seen_points = {ExtremePoint(0, 0, 0)}
    placement_count = 0

    # Hoist settings weights out of the inner loop (Fix #6)
    _settings = get_settings()
    _contact_wt = _settings.CONTACT_RATIO_WEIGHT
    _residual_wt = _settings.RESIDUAL_VOLUME_WEIGHT
    _c_vol = container_dims.volume()

    for block in blocks:
        sorted_eps = sort_extreme_points(extreme_points)

        best_result = None
        best_score = -1.0

        for ep in sorted_eps:
            for posture in block.boxes[0].permitted_postures if block.boxes else [Posture.LWH]:
                dims = Dimensions(block.length_cm, block.width_cm, block.height_cm).apply_posture(posture)
                inflated_dims = Dimensions(
                    block.inflated_length, block.inflated_width, block.inflated_height
                ).apply_posture(posture)

                pos = Position(ep.x, ep.y, ep.z)

                candidate_bbox = BoundingBox.from_position_and_dims(pos, inflated_dims)

                valid, _ = check_all_constraints(
                    PlacementCandidate(
                        position=pos,
                        posture=posture,
                        dims=inflated_dims,
                        actual_dims=dims,
                        box=block.boxes[0] if block.boxes else None,
                    ),
                    placed_bboxes,
                    [b for b in placed_blocks for _ in b.boxes],
                    container_dims,
                    current_weight,
                    max_weight,
                    is_lcl,
                )

                if not valid:
                    continue

                contact_ratio = calculate_contact_ratio(candidate_bbox, placed_bboxes, container_dims)
                residual_vol = calculate_residual_volume(candidate_bbox, placed_bboxes, container_dims)

                score = (
                    _contact_wt * contact_ratio
                    - _residual_wt * (residual_vol / _c_vol)
                )

                if score > best_score:
                    best_score = score
                    best_result = PlacementResult(
                        position=pos,
                        posture=posture,
                        dims=inflated_dims,
                        actual_dims=dims,
                        score=score,
                    )

        if best_result:
            new_bbox = BoundingBox.from_position_and_dims(best_result.position, best_result.dims)
            placed_bboxes.append(new_bbox)
            placed_blocks.append(block)
            current_weight += block.weight_kg
            placement_count += 1
            extreme_points = _add_box_extreme_points(
                new_bbox, extreme_points, seen_points, placed_bboxes, container_dims, placement_count
            )
        else:
            unplaced.append(block)

    return placed_bboxes, placed_blocks, unplaced, current_weight


def decode_chromosome(
    chromosome: List[int],
    units: List[Box],
    container_dims: Dimensions,
    max_weight: float,
    is_lcl: bool,
) -> Tuple[List[BoundingBox], List[Box], List[Tuple[Box, str]], float, List[Posture]]:
    """
    Decode a chromosome into a loading plan.
    Implements posture repair: if first-choice posture doesn't fit, try other permitted postures.
    Uses find_best_placement for consistent best-fit search and reason tracking.
    """
    placed_bboxes = []
    placed_data = []
    placed_postures = []
    unplaced = []  # List of (box, reason)
    current_weight = 0.0

    # Seed initial extreme points with origin (0, 0, 0); real rear anchors
    # depend on box dimensions and come from corner_points_for during corner_phase.
    extreme_points = [ExtremePoint(0, 0, 0)]
    seen_points = {ExtremePoint(0, 0, 0)}
    corner_phase = True
    corner_consecutive_failures = 0  # Change 7: consecutive corner failure counter
    placement_count = 0  # Change 4: for periodic EP pruning
    last_customer_sequence = max(u.customer_sequence for u in units) if units else 0

    for i, posture_idx in enumerate(chromosome):
        if i >= len(units):
            break

        box = units[i]

        # Posture repair: try chromosome's posture first, then alternatives
        permitted = box.permitted_postures
        if not permitted:
            unplaced.append((box, 'no_space'))
            continue

        first_posture = permitted[posture_idx % len(permitted)]
        postures_to_try = [first_posture] + [p for p in permitted if p != first_posture]

        placed = False

        for posture in postures_to_try:
            # If still in corner phase, try corner points first
            if corner_phase:
                box_dims = Dimensions(box.length_cm, box.width_cm, box.height_cm).apply_posture(posture)
                # Use inflated dims for corner boundary check so rear corners are not
                # falsely rejected when L - inflated_dx maps to a valid non-negative x.
                inflated_dims = Dimensions(box.inflated_length, box.inflated_width, box.inflated_height).apply_posture(posture)
                corners = corner_points_for(box, inflated_dims, container_dims, "LCL" if is_lcl else "FCL", last_customer_sequence)

                placed_at_corner = False

                for corner in corners:
                    pos = Position(corner.x, corner.y, corner.z)
                    candidate = PlacementCandidate(
                        position=pos,
                        posture=posture,
                        dims=Dimensions(box.inflated_length, box.inflated_width, box.inflated_height).apply_posture(posture),
                        actual_dims=box_dims,
                        box=box,
                    )

                    valid, reason = check_all_constraints(
                        candidate,
                        placed_bboxes,
                        placed_data,
                        container_dims,
                        current_weight,
                        max_weight,
                        is_lcl,
                    )

                    if valid:
                        new_bbox = BoundingBox.from_position_and_dims(pos, candidate.dims)
                        placed_bboxes.append(new_bbox)
                        placed_data.append(box)
                        placed_postures.append(posture)
                        current_weight += box.weight_kg
                        placed = True
                        placed_at_corner = True
                        # Update chromosome with working posture
                        chromosome[i] = permitted.index(posture)
                        placement_count += 1
                        extreme_points = _add_box_extreme_points(
                            new_bbox, extreme_points, seen_points, placed_bboxes, container_dims, placement_count
                        )
                        break

                if placed_at_corner:
                    corner_phase = False  # Initial rear anchor established; use find_best_placement for subsequent units to group same SKUs
                    break  # Break out of posture loop
                else:
                    # This posture didn't fit at any corner. Stay in corner_phase
                    # and try the next posture's corners before giving up on corner-phase entirely.
                    continue

            if placed:
                break  # Break out of posture loop

            # Normal best-fit search using find_best_placement (consistent with place_boxes_greedy)
            sorted_eps = sort_extreme_points(extreme_points)

            result, reason = find_best_placement(
                box,
                placed_bboxes,
                placed_data,
                container_dims,
                current_weight,
                max_weight,
                is_lcl,
                sorted_eps,
                last_customer_sequence,
            )

            if result:
                new_bbox = BoundingBox.from_position_and_dims(result.position, result.dims)
                placed_bboxes.append(new_bbox)
                placed_data.append(box)
                placed_postures.append(result.posture)
                current_weight += box.weight_kg
                placed = True
                # Update chromosome with working posture
                chromosome[i] = permitted.index(result.posture)
                placement_count += 1
                extreme_points = _add_box_extreme_points(
                    new_bbox, extreme_points, seen_points, placed_bboxes, container_dims, placement_count
                )
                break  # Break out of posture loop
            else:
                # find_best_placement already tested all permitted postures against all extreme points.
                # If it failed, no posture can fit at any current extreme point.
                break

        # BUG-08 fix: remove the redundant O(P×C) corner re-evaluation block.
        # The old code re-ran check_all_constraints for every posture×corner combination
        # just to set `could_place_at_corner` — then immediately called find_best_placement
        # anyway.  Instead: track failures from the posture loop directly and fall
        # through to find_best_placement on failure without duplicating work.
        if corner_phase and not placed:
            corner_consecutive_failures += 1
            if corner_consecutive_failures >= 3:
                corner_phase = False
            # Fall through to general EP search
            sorted_eps = sort_extreme_points(extreme_points)
            result, reason = find_best_placement(
                box,
                placed_bboxes,
                placed_data,
                container_dims,
                current_weight,
                max_weight,
                is_lcl,
                sorted_eps,
                last_customer_sequence,
            )
            if result:
                new_bbox = BoundingBox.from_position_and_dims(result.position, result.dims)
                placed_bboxes.append(new_bbox)
                placed_data.append(box)
                placed_postures.append(result.posture)
                current_weight += box.weight_kg
                placed = True
                chromosome[i] = permitted.index(result.posture)
                placement_count += 1
                extreme_points = _add_box_extreme_points(
                    new_bbox, extreme_points, seen_points, placed_bboxes, container_dims, placement_count
                )
                # A general EP succeeded — don't penalise the corner-failure counter
                corner_consecutive_failures = max(0, corner_consecutive_failures - 1)

        if not placed:
            unplaced.append((box, 'no_space'))

    return placed_bboxes, placed_data, unplaced, current_weight, placed_postures