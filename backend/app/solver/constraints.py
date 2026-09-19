from typing import List, Optional, Tuple
from dataclasses import dataclass
from app.config import get_settings
from app.solver.geometry import (
    BoundingBox,
    Dimensions,
    Position,
    Posture,
    check_support_ratio,
    check_load_bearing,
    check_cog_balance,
)
from app.solver.parsing import Box
from app.solver.block_generation import Block


@dataclass
class PlacementCandidate:
    position: Position
    posture: Posture
    dims: Dimensions
    actual_dims: Dimensions
    box: Box


def check_weight_capacity(
    current_weight: float,
    candidate_weight: float,
    max_weight: float,
) -> bool:
    return (current_weight + candidate_weight) <= max_weight


def check_orientation(box: Box, posture: Posture) -> bool:
    return posture in box.permitted_postures


def check_non_overlap(
    candidate: BoundingBox,
    placed_boxes: List[BoundingBox],
) -> bool:
    c_min_x, c_max_x = candidate.min_x, candidate.max_x
    c_min_y, c_max_y = candidate.min_y, candidate.max_y
    c_min_z, c_max_z = candidate.min_z, candidate.max_z
    for placed in reversed(placed_boxes):
        if not (
            c_max_x <= placed.min_x
            or placed.max_x <= c_min_x
            or c_max_y <= placed.min_y
            or placed.max_y <= c_min_y
            or c_max_z <= placed.min_z
            or placed.max_z <= c_min_z
        ):
            return False
    return True


def check_container_bounds(
    candidate: BoundingBox,
    container_dims: Dimensions,
) -> bool:
    return (
        candidate.min_x >= 0
        and candidate.min_y >= 0
        and candidate.min_z >= 0
        and candidate.max_x <= container_dims.length
        and candidate.max_y <= container_dims.width
        and candidate.max_z <= container_dims.height
    )


def check_stackability(
    candidate: BoundingBox,
    placed_boxes: List[BoundingBox],
    candidate_box: Box,
    placed_boxes_data: List[Box],
) -> bool:
    settings = get_settings()

    if not check_support_ratio(candidate, placed_boxes, settings.SUPPORT_RATIO):
        return False

    if candidate.min_z > 0:
        support_indices = []
        support_weights = []
        support_limits = []

        c_min_z = candidate.min_z
        for i, placed in enumerate(placed_boxes):
            if abs(placed.max_z - c_min_z) < 1e-6 and placed.supports(candidate):
                support_indices.append(i)
                support_weights.append(placed_boxes_data[i].weight_kg)
                support_limits.append(placed_boxes_data[i].max_load_bearing_kg)

        if not support_indices:
            return False

        for idx in support_indices:
            if placed_boxes_data[idx].stacking_group == 2:
                return False

        # Pass the BoundingBox objects for support check
        support_bboxes = [placed_boxes[i] for i in support_indices]
        if not check_load_bearing(
            candidate,
            support_bboxes,
            candidate_box.weight_kg,
            support_weights,
            support_limits,
        ):
            return False

    return True


def check_lifo(
    candidate: BoundingBox,
    placed_boxes: List[BoundingBox],
    placed_boxes_data: List[Box],
    candidate_sequence: int,
) -> bool:
    for i, placed in enumerate(placed_boxes):
        placed_data = placed_boxes_data[i]
        if placed_data.customer_sequence < candidate_sequence:
            # Earlier customer (smaller sequence) must not be blocked
            # Violation: candidate (later) is deeper AND overlaps on Y and Z
            if candidate.max_x > placed.min_x and candidate.overlaps_yz(placed):
                return False
    return True


def check_all_constraints(
    candidate: PlacementCandidate,
    placed_boxes: List[BoundingBox],
    placed_boxes_data: List[Box],
    container_dims: Dimensions,
    current_weight: float,
    max_weight: float,
    is_lcl: bool,
) -> Tuple[bool, str]:
    if not check_orientation(candidate.box, candidate.posture):
        return False, "orientation"

    if not check_container_bounds(
        BoundingBox.from_position_and_dims(candidate.position, candidate.dims),
        container_dims,
    ):
        return False, "container_bounds"

    candidate_bbox = BoundingBox.from_position_and_dims(
        candidate.position, candidate.dims
    )

    if not check_non_overlap(candidate_bbox, placed_boxes):
        return False, "non_overlap"

    if not check_weight_capacity(current_weight, candidate.box.weight_kg, max_weight):
        return False, "weight_capacity"

    if not check_stackability(
        candidate_bbox, placed_boxes, candidate.box, placed_boxes_data
    ):
        return False, "stackability"

    if is_lcl:
        if not check_lifo(
            candidate_bbox, placed_boxes, placed_boxes_data, candidate.box.customer_sequence
        ):
            return False, "lifo"

    return True, "ok"