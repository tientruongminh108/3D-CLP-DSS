from typing import List, Optional, Tuple
from dataclasses import dataclass
from app.config import get_settings
from app.solver.geometry import (
    Dimensions,
    Position,
    BoundingBox,
    Posture,
    ExtremePoint,
    generate_extreme_points,
    sort_extreme_points,
    calculate_contact_ratio,
    calculate_residual_volume,
    get_permitted_postures,
    project_point_down,
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
    Compute the 4 bottom corner anchors for a box under its current posture.
    For LCL, the two deep corners are only offered to the last customer's cargo.
    """
    dx, dy, dz = box_dims.length, box_dims.width, box_dims.height

    corners = []
    # Door corner, left wall (x=0, y=0)
    corners.append(ExtremePoint(0, 0, 0))
    # Door corner, right wall (x=0, y=W - dy)
    corners.append(ExtremePoint(0, container_dims.width - dy, 0))

    # Deep corners: only for FCL or last customer in LCL
    if shipment_type == "FCL" or box.customer_sequence == last_customer_sequence:
        # Deepest corner, left wall (x=L - dx, y=0)
        corners.append(ExtremePoint(container_dims.length - dx, 0, 0))
        # Deepest corner, right wall (x=L - dx, y=W - dy)
        corners.append(ExtremePoint(container_dims.length - dx, container_dims.width - dy, 0))

    # Filter out corners that would place box outside container (large boxes)
    valid = []
    for c in corners:
        if (c.x + dx <= container_dims.length and 
            c.y + dy <= container_dims.width and 
            c.z + dz <= container_dims.height):
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

    # Try all extreme points with all permitted postures
    for ep in extreme_points:
        ep_x, ep_y, ep_z = ep.x, ep.y, ep.z

        for posture, dims, inflated_dims in posture_specs:
            # Fast container boundary check
            if (ep_x + inflated_dims.length > c_len or
                ep_y + inflated_dims.width > c_wid or
                ep_z + inflated_dims.height > c_hgt):
                continue

            pos = Position(ep_x, ep_y, ep_z)
            candidate_bbox = BoundingBox.from_position_and_dims(pos, inflated_dims)

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
            residual_vol = calculate_residual_volume(candidate_bbox, placed_boxes, container_dims)

            score = contact_wt * contact_ratio - residual_wt * (residual_vol / c_vol)

            # Tie-break: smaller x, then larger z
            if score > best_score or (
                abs(score - best_score) < 1e-9 and (
                    pos.x < best_result.position.x or
                    (abs(pos.x - best_result.position.x) < 1e-9 and pos.z > best_result.position.z)
                )
            ):
                best_score = score
                best_result = PlacementResult(
                    position=pos,
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

    # Initial extreme points: just the door corner
    extreme_points = [ExtremePoint(0, 0, 0)]
    corner_phase = True

    for box in boxes:
        if corner_phase:
            # Try corner points first
            box_dims = Dimensions(box.length_cm, box.width_cm, box.height_cm)
            # We'll try each permitted posture at corners
            placed_at_corner = False
            
            for posture in box.permitted_postures:
                dims = box_dims.apply_posture(posture)
                corners = corner_points_for(box, dims, container_dims, "LCL" if is_lcl else "FCL", last_customer_sequence)
                
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
                        placed_bboxes.append(BoundingBox.from_position_and_dims(pos, candidate.dims))
                        placed_data.append(box)
                        current_weight += box.weight_kg
                        placed_at_corner = True
                        break
                
                if placed_at_corner:
                    break
            
            if placed_at_corner:
                # Update extreme points with downward projection
                new_points = [
                    ExtremePoint(placed_bboxes[-1].max_x, placed_bboxes[-1].min_y, placed_bboxes[-1].min_z),
                    ExtremePoint(placed_bboxes[-1].min_x, placed_bboxes[-1].max_y, placed_bboxes[-1].min_z),
                    ExtremePoint(placed_bboxes[-1].min_x, placed_bboxes[-1].min_y, placed_bboxes[-1].max_z),
                ]
                for p in new_points:
                    projected = project_point_down(p, placed_bboxes, container_dims)
                    extreme_points.append(projected)
                # Prune dominated
                extreme_points = prune_dominated_extreme_points(extreme_points)
                continue
            else:
                # No box could be placed at corners - end corner phase
                corner_phase = False

        # Normal best-fit search
        extreme_points = generate_extreme_points(placed_bboxes, container_dims, 0)
        extreme_points = sort_extreme_points(extreme_points)

        result, reason = find_best_placement(
            box,
            placed_bboxes,
            placed_data,
            container_dims,
            current_weight,
            max_weight,
            is_lcl,
            extreme_points,
            last_customer_sequence,
        )

        if result:
            placed_bboxes.append(
                BoundingBox.from_position_and_dims(result.position, result.dims)
            )
            placed_data.append(box)
            current_weight += box.weight_kg
        else:
            unplaced.append((box, reason))

    return placed_bboxes, placed_data, unplaced, current_weight


def prune_dominated_extreme_points(points: List[ExtremePoint]) -> List[ExtremePoint]:
    """Dominance pruning: Q dominates P if Q is at least as good on all 3 axes 
    with equality on at least 2 and strict improvement on the third."""
    if not points:
        return []
    
    # Sort by z, then y, then x
    points = sorted(points, key=lambda p: (p.z, p.y, p.x))
    
    pruned = []
    for p in points:
        dominated = False
        for q in pruned:
            if (q.x <= p.x + 1e-9 and q.y <= p.y + 1e-9 and q.z <= p.z + 1e-9):
                # Count equal axes
                equal_axes = sum([
                    abs(q.x - p.x) < 1e-9,
                    abs(q.y - p.y) < 1e-9,
                    abs(q.z - p.z) < 1e-9
                ])
                if equal_axes >= 2 and (q.x < p.x or q.y < p.y or q.z < p.z):
                    dominated = True
                    break
        if not dominated:
            pruned.append(p)
    
    return pruned


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

    for block in blocks:
        extreme_points = generate_extreme_points(placed_bboxes, container_dims, 0)
        extreme_points = sort_extreme_points(extreme_points)

        best_result = None
        best_score = -1.0

        for ep in extreme_points:
            for posture in block.boxes[0].permitted_postures if block.boxes else [Posture.LWH]:
                dims = Dimensions(block.length_cm, block.width_cm, block.height_cm).apply_posture(posture)
                inflated_dims = Dimensions(
                    block.inflated_length, block.inflated_width, block.inflated_height
                ).apply_posture(posture)

                pos = Position(ep.x, ep.y, ep.z)

                candidate_bbox = BoundingBox.from_position_and_dims(pos, inflated_dims)

                valid = True
                if not check_all_constraints(
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
                )[0]:
                    valid = False

                if not valid:
                    continue

                contact_ratio = calculate_contact_ratio(candidate_bbox, placed_bboxes, container_dims)
                residual_vol = calculate_residual_volume(candidate_bbox, placed_bboxes, container_dims)

                score = (
                    get_settings().CONTACT_RATIO_WEIGHT * contact_ratio
                    - get_settings().RESIDUAL_VOLUME_WEIGHT * (residual_vol / container_dims.volume())
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
            placed_bboxes.append(
                BoundingBox.from_position_and_dims(best_result.position, best_result.dims)
            )
            placed_blocks.append(block)
            current_weight += block.weight_kg
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

    extreme_points = [ExtremePoint(0, 0, 0)]
    corner_phase = True
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
                corners = corner_points_for(box, box_dims, container_dims, "LCL" if is_lcl else "FCL", last_customer_sequence)
                
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
                        placed_bboxes.append(BoundingBox.from_position_and_dims(pos, candidate.dims))
                        placed_data.append(box)
                        placed_postures.append(posture)
                        current_weight += box.weight_kg
                        placed = True
                        placed_at_corner = True
                        # Update chromosome with working posture
                        chromosome[i] = permitted.index(posture)
                        break
                
                if placed_at_corner:
                    # Update extreme points with downward projection
                    new_points = [
                        ExtremePoint(placed_bboxes[-1].max_x, placed_bboxes[-1].min_y, placed_bboxes[-1].min_z),
                        ExtremePoint(placed_bboxes[-1].min_x, placed_bboxes[-1].max_y, placed_bboxes[-1].min_z),
                        ExtremePoint(placed_bboxes[-1].min_x, placed_bboxes[-1].min_y, placed_bboxes[-1].max_z),
                    ]
                    for p in new_points:
                        projected = project_point_down(p, placed_bboxes, container_dims)
                        extreme_points.append(projected)
                    extreme_points = prune_dominated_extreme_points(extreme_points)
                    break  # Break out of posture loop
            
            if placed:
                break  # Break out of posture loop
            
            # Normal best-fit search using find_best_placement (consistent with place_boxes_greedy)
            extreme_points = generate_extreme_points(placed_bboxes, container_dims, 0)
            extreme_points = sort_extreme_points(extreme_points)
            
            result, reason = find_best_placement(
                box,
                placed_bboxes,
                placed_data,
                container_dims,
                current_weight,
                max_weight,
                is_lcl,
                extreme_points,
                last_customer_sequence,
            )
            
            if result:
                placed_bboxes.append(BoundingBox.from_position_and_dims(result.position, result.dims))
                placed_data.append(box)
                placed_postures.append(result.posture)
                current_weight += box.weight_kg
                placed = True
                # Update chromosome with working posture
                chromosome[i] = permitted.index(result.posture)
                break  # Break out of posture loop
        
        if not placed:
            unplaced.append((box, 'no_space'))
        
        # Check if corner phase should end - only when box fails at ALL corners
        if corner_phase:
            # Test if this box could be placed at any corner with any posture
            could_place_at_corner = False
            for test_posture in box.permitted_postures:
                test_dims = Dimensions(box.length_cm, box.width_cm, box.height_cm).apply_posture(test_posture)
                test_corners = corner_points_for(box, test_dims, container_dims, "LCL" if is_lcl else "FCL", last_customer_sequence)
                for test_corner in test_corners:
                    test_pos = Position(test_corner.x, test_corner.y, test_corner.z)
                    test_candidate = PlacementCandidate(
                        position=test_pos,
                        posture=test_posture,
                        dims=Dimensions(box.inflated_length, box.inflated_width, box.inflated_height).apply_posture(test_posture),
                        actual_dims=test_dims,
                        box=box,
                    )
                    test_valid, _ = check_all_constraints(
                        test_candidate,
                        placed_bboxes,
                        placed_data,
                        container_dims,
                        current_weight,
                        max_weight,
                        is_lcl,
                    )
                    if test_valid:
                        could_place_at_corner = True
                        break
                if could_place_at_corner:
                    break
            
            if not could_place_at_corner:
                corner_phase = False

    return placed_bboxes, placed_data, unplaced, current_weight, placed_postures