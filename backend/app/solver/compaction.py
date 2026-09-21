from typing import List, Tuple, Optional, Any
import copy
from app.solver.geometry import (
    Dimensions,
    BoundingBox,
    Posture,
    generate_extreme_points,
    sort_extreme_points,
)
from app.solver.fitness import calculate_fitness, FitnessResult
from app.solver.placement import find_best_placement


def compact_x_rear(
    placed_bboxes: List[BoundingBox],
    placed_data: List[Any],
    container_dims: Dimensions,
    is_lcl: bool = False,
) -> List[BoundingBox]:
    """Pass 1: X-axis (rear-wall) compaction.

    Slide placed boxes toward the rear wall (increasing x) without exceeding
    container length, without colliding with any box that overlaps in both y and z,
    and in LCL mode without violating customer sequence depth ordering.
    Boxes are processed rear-most first (highest max_x to lowest).
    """
    n = len(placed_bboxes)
    if n == 0:
        return placed_bboxes

    # Process rear-most boxes first (highest max_x to lowest)
    indices = sorted(range(n), key=lambda i: placed_bboxes[i].max_x, reverse=True)

    for i in indices:
        b_i = placed_bboxes[i]
        limit_x = container_dims.length

        for j in range(n):
            if i == j:
                continue
            b_j = placed_bboxes[j]

            # Overlap in y and z
            overlap_y = min(b_i.max_y, b_j.max_y) - max(b_i.min_y, b_j.min_y) > 1e-6
            overlap_z = min(b_i.max_z, b_j.max_z) - max(b_i.min_z, b_j.min_z) > 1e-6

            if overlap_y and overlap_z and b_j.min_x >= b_i.max_x - 1e-6:
                if b_j.min_x < limit_x:
                    limit_x = b_j.min_x

            # LCL correctness: earlier customer must not be placed deeper than later customer cargo
            if is_lcl:
                cust_i = getattr(placed_data[i], 'customer_sequence', 0)
                cust_j = getattr(placed_data[j], 'customer_sequence', 0)
                if cust_j > cust_i and b_j.min_x < limit_x:
                    limit_x = b_j.min_x

        if limit_x > b_i.max_x + 1e-6:
            shift_x = limit_x - b_i.max_x
            placed_bboxes[i] = BoundingBox(
                b_i.min_x + shift_x,
                b_i.min_y,
                b_i.min_z,
                b_i.max_x + shift_x,
                b_i.max_y,
                b_i.max_z,
            )

    return placed_bboxes


def compact_y_sidewall(
    placed_bboxes: List[BoundingBox],
    placed_data: List[Any],
    container_dims: Dimensions,
    is_lcl: bool = False,
) -> List[BoundingBox]:
    """Pass 2: Y-axis (side-wall) compaction.

    Slide placed boxes toward the left wall (decreasing y, min-y = 0) without
    colliding with any box that overlaps in both x and z and sits to its left.
    Boxes are processed left-most first (lowest min_y to highest).
    """
    n = len(placed_bboxes)
    if n == 0:
        return placed_bboxes

    # Process left-most boxes first (lowest min_y to highest)
    indices = sorted(range(n), key=lambda i: placed_bboxes[i].min_y)

    for i in indices:
        b_i = placed_bboxes[i]
        limit_y = 0.0

        for j in range(n):
            if i == j:
                continue
            b_j = placed_bboxes[j]

            # Overlap in x and z
            overlap_x = min(b_i.max_x, b_j.max_x) - max(b_i.min_x, b_j.min_x) > 1e-6
            overlap_z = min(b_i.max_z, b_j.max_z) - max(b_i.min_z, b_j.min_z) > 1e-6

            if overlap_x and overlap_z and b_j.max_y <= b_i.min_y + 1e-6:
                if b_j.max_y > limit_y:
                    limit_y = b_j.max_y

        if limit_y < b_i.min_y - 1e-6:
            shift_y = b_i.min_y - limit_y
            placed_bboxes[i] = BoundingBox(
                b_i.min_x,
                b_i.min_y - shift_y,
                b_i.min_z,
                b_i.max_x,
                b_i.max_y - shift_y,
                b_i.max_z,
            )

    return placed_bboxes


def _unit_volume(unit: Any) -> float:
    if hasattr(unit, 'length_cm') and hasattr(unit, 'width_cm') and hasattr(unit, 'height_cm'):
        return float(unit.length_cm * unit.width_cm * unit.height_cm)
    if hasattr(unit, 'volume') and callable(unit.volume):
        return float(unit.volume())
    return 0.0


def rescan_and_insert(
    placed_bboxes: List[BoundingBox],
    placed_data: List[Any],
    placed_postures: List[Posture],
    unplaced: List[Tuple[Any, str]],
    container_dims: Dimensions,
    current_weight: float,
    max_weight: float,
    is_lcl: bool = False,
) -> Tuple[List[BoundingBox], List[Any], List[Posture], List[Tuple[Any, str]], float]:
    """Pass 3: Re-scan for insertion opportunities.

    Regenerate extreme points from the compacted placements and attempt to place
    previously-unplaced items into newly-opened space, smallest-volume-first.
    """
    if not unplaced:
        return placed_bboxes, placed_data, placed_postures, unplaced, current_weight

    extreme_points = generate_extreme_points(placed_bboxes, container_dims)
    sorted_eps = sort_extreme_points(extreme_points)

    last_customer_sequence = max(
        (getattr(u, 'customer_sequence', 0) for u in placed_data),
        default=0,
    )

    # Sort unplaced items smallest volume first, then smallest weight
    unplaced_sorted = sorted(
        unplaced,
        key=lambda pair: (_unit_volume(pair[0]), getattr(pair[0], 'weight_kg', 0.0)),
    )

    remaining_unplaced: List[Tuple[Any, str]] = []

    for unit, old_reason in unplaced_sorted:
        placement_res, reason = find_best_placement(
            box=unit,
            placed_boxes=placed_bboxes,
            placed_boxes_data=placed_data,
            container_dims=container_dims,
            current_weight=current_weight,
            max_weight=max_weight,
            is_lcl=is_lcl,
            extreme_points=sorted_eps,
            last_customer_sequence=last_customer_sequence,
        )

        if placement_res:
            new_bbox = BoundingBox.from_position_and_dims(placement_res.position, placement_res.dims)
            placed_bboxes.append(new_bbox)
            placed_data.append(unit)
            placed_postures.append(placement_res.posture)
            current_weight += unit.weight_kg

            # Refresh extreme points with the newly placed box
            extreme_points = generate_extreme_points(placed_bboxes, container_dims)
            sorted_eps = sort_extreme_points(extreme_points)
        else:
            remaining_unplaced.append((unit, reason))

    return placed_bboxes, placed_data, placed_postures, remaining_unplaced, current_weight


def run_compaction_pass(
    placed_bboxes: List[BoundingBox],
    placed_data: List[Any],
    placed_postures: List[Posture],
    unplaced: List[Tuple[Any, str]],
    container_dims: Dimensions,
    max_weight: float,
    is_lcl: bool,
    current_weight: float,
) -> Tuple[List[BoundingBox], List[Any], List[Posture], List[Tuple[Any, str]], float, FitnessResult]:
    """Execute complete post-processing compaction pass:
    1. X-axis rear-wall slide
    2. Y-axis side-wall slide
    3. Re-scan and insertion of unplaced items
    4. Recompute fitness result reflecting compacted + inserted solution.
    """
    placed_bboxes = [copy.deepcopy(b) for b in placed_bboxes]
    placed_data = list(placed_data)
    placed_postures = list(placed_postures)
    unplaced = list(unplaced)

    # 1. X compaction
    placed_bboxes = compact_x_rear(placed_bboxes, placed_data, container_dims, is_lcl)

    # 2. Y compaction
    placed_bboxes = compact_y_sidewall(placed_bboxes, placed_data, container_dims, is_lcl)

    # 3. Insertion re-scan
    placed_bboxes, placed_data, placed_postures, unplaced, current_weight = rescan_and_insert(
        placed_bboxes=placed_bboxes,
        placed_data=placed_data,
        placed_postures=placed_postures,
        unplaced=unplaced,
        container_dims=container_dims,
        current_weight=current_weight,
        max_weight=max_weight,
        is_lcl=is_lcl,
    )

    # 4. Recompute fitness
    fitness_res = calculate_fitness(
        placed_bboxes=placed_bboxes,
        placed_data=placed_data,
        unplaced=unplaced,
        container_dims=container_dims,
        max_weight=max_weight,
    )

    return placed_bboxes, placed_data, placed_postures, unplaced, current_weight, fitness_res
