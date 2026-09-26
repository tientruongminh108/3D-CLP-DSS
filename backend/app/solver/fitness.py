from typing import List, Tuple
from dataclasses import dataclass
from collections import defaultdict
from itertools import chain
from app.config import get_settings
from app.solver.geometry import BoundingBox, Position, calculate_cog, check_cog_balance, FLOOR_EPSILON
from app.solver.parsing import Box
from app.solver.block_generation import Block


@dataclass
class FitnessResult:
    fitness: float
    placed_volume: float
    unplaced_count: int
    cog_deviation_xy: float
    cog_deviation_z: float
    stacking_violations: int
    stability_violations: int


def calculate_fitness(
    placed_bboxes: List[BoundingBox],
    placed_data: List[Box],
    unplaced: List[Tuple[Box, str]],
    container_dims,
    max_weight: float,
) -> FitnessResult:
    settings = get_settings()

    placed_volume = sum(
        (b.max_x - b.min_x) * (b.max_y - b.min_y) * (b.max_z - b.min_z)
        for b in placed_bboxes
    )
    container_volume = container_dims.length * container_dims.width * container_dims.height
    fill_rate = placed_volume / container_volume if container_volume > 0 else 0

    unplaced_count = len(unplaced)

    # Center of gravity calculation (normalized per Section 5.3.2, 5.4.3)
    weights = [b.weight_kg for b in placed_data]
    cog = calculate_cog(placed_bboxes, weights)
    
    # Normalized CoG deviations per Section 5.3.2
    ideal_x = container_dims.length / 2
    ideal_y = container_dims.width / 2
    ideal_z = container_dims.height / 2
    
    B1_norm = abs(cog.x - ideal_x) / (container_dims.length / 2) if container_dims.length > 0 else 0
    B2_norm = abs(cog.y - ideal_y) / (container_dims.width / 2) if container_dims.width > 0 else 0
    B3_norm = max(0, cog.z - ideal_z) / (container_dims.height / 2) if container_dims.height > 0 else 0
    
    # Legacy raw deviations for reporting
    _, cog_dev_xy, cog_dev_z = check_cog_balance(
        cog, container_dims, settings.COG_TOLERANCE_XY, settings.COG_TOLERANCE_Z
    )

    # Check constraints for penalty terms (B4, B5)
    stacking_violations = 0
    stability_violations = 0

    # Build a z-level index so supporters are looked up in O(1)
    # instead of scanning all N boxes for each of N candidates.
    z_to_supporters = defaultdict(list)
    for j, other in enumerate(placed_bboxes):
        # Key on rounded max_z to handle floating-point near-equality
        z_to_supporters[round(other.max_z, 6)].append((j, other))

    for i, bbox in enumerate(placed_bboxes):
        if bbox.min_z > FLOOR_EPSILON:
            support_area = 0.0
            footprint = (bbox.max_x - bbox.min_x) * (bbox.max_y - bbox.min_y)
            box_unit_wt = getattr(placed_data[i], 'boxes', [placed_data[i]])[0].weight_kg
            for j, other in z_to_supporters.get(round(bbox.min_z, 6), []):
                if other.supports(bbox):
                    support_area += other.contact_area(bbox)
                    sup_unit_wt = getattr(placed_data[j], 'boxes', [placed_data[j]])[0].weight_kg
                    if box_unit_wt > sup_unit_wt + 1e-3:
                        stacking_violations += 1
            if footprint > 0 and (support_area / footprint) < settings.SUPPORT_RATIO:
                stability_violations += 1

    # Fitness per Section 5.3.2:
    # fitness = -(unplaced_count * UNPLACED_RANK_WEIGHT)
    #           + (E / container_volume)
    #           - cog_weight * (B1_norm + B2_norm + B3_norm)
    #           - INFEASIBLE_PENALTY if B4==0 or B5==0
    
    max_box_weight = max(
        (getattr(b, 'weight_kg', 0.0)
         for b in chain(placed_data, (u for u, _ in unplaced))),
        default=1.0,
    ) or 1.0

    unplaced_weight_penalty = sum(
        settings.UNPLACED_RANK_WEIGHT * (1.0 + getattr(u, 'weight_kg', 0.0) / max_box_weight)
        for u, _ in unplaced
    )

    fill_term = fill_rate - settings.FITNESS_COG_PENALTY_WEIGHT * (B1_norm + B2_norm + B3_norm)

    total_box_count = len(placed_data) + unplaced_count
    INFEASIBLE_PENALTY = -(total_box_count * settings.UNPLACED_RANK_WEIGHT) - 1000

    feasible = (stacking_violations == 0 and stability_violations == 0)

    fitness = (
        -unplaced_weight_penalty
        + fill_term
        + (0 if feasible else INFEASIBLE_PENALTY)
    )

    return FitnessResult(
        fitness=fitness,
        placed_volume=placed_volume,
        unplaced_count=unplaced_count,
        cog_deviation_xy=cog_dev_xy,
        cog_deviation_z=cog_dev_z,
        stacking_violations=stacking_violations,
        stability_violations=stability_violations,
    )