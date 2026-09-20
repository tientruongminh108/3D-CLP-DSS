from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.solver.geometry import BoundingBox, Position, Dimensions, Posture
from app.solver.parsing import Box
from app.solver.block_generation import Block
from app.solver.ga import Individual
from app.solver.fitness import FitnessResult
from app.core.models import (
    PlacedBox,
    UnplacedCarton,
    LoadMetrics,
    UnplacedReason,
    RunResult,
)
from datetime import datetime
import uuid


@dataclass
class Layer:
    x_min: float
    x_max: float
    boxes: List[PlacedBox]


def transform_position_by_posture(pos: Position, posture: Posture, block_dims: Optional[Dimensions] = None) -> Position:
    """Transform a position from block-local coordinates to world coordinates
    given the block's posture. The block's origin corner is at (0,0,0) in its
    local coordinate system.
    
    Posture mapping (per Table 1 / Dimensions.apply_posture):
      1. LWH: (x, y, z)
      2. WLH: (y, x, z)
      3. HLW: (z, x, y)
      4. HWL: (z, y, x)
      5. LHW: (x, z, y)
      6. WHL: (y, z, x)
    """
    x, y, z = pos.x, pos.y, pos.z
    if posture == Posture.LWH:
        return Position(x, y, z)
    elif posture == Posture.WLH:
        return Position(y, x, z)
    elif posture == Posture.HLW:
        return Position(z, x, y)
    elif posture == Posture.HWL:
        return Position(z, y, x)
    elif posture == Posture.LHW:
        return Position(x, z, y)
    elif posture == Posture.WHL:
        return Position(y, z, x)
    return Position(x, y, z)


def explode_blocks(
    placed_blocks_or_data: List,
    individual_or_bboxes: Any = None,
    placed_postures: Optional[List[Posture]] = None,
) -> List[PlacedBox]:
    """Explode block placements and individual box placements into PlacedBox instances with correct positions.
    
    Per Section 5.2.4: each block's contents have positions relative to the block's
    origin corner. When the block is placed at absolute position with a posture,
    each content box's absolute position = block_position + transform(content_rel_pos, block_posture).
    Individual boxes are placed directly at their bounding box min corner.
    """
    placed_boxes = []

    # Determine calling convention
    if placed_postures is not None and isinstance(individual_or_bboxes, list):
        placed_data = placed_blocks_or_data
        placed_bboxes = individual_or_bboxes
        postures = placed_postures
    elif hasattr(individual_or_bboxes, "placed_data") and individual_or_bboxes.placed_data is not None:
        placed_data = individual_or_bboxes.placed_data
        placed_bboxes = individual_or_bboxes.placed_bboxes or []
        postures = getattr(individual_or_bboxes, "placed_postures", None) or []
        if not postures and individual_or_bboxes.chromosome:
            postures = []
            for idx, u in enumerate(placed_data):
                if hasattr(u, "permitted_postures") and u.permitted_postures:
                    p_idx = individual_or_bboxes.chromosome[idx % len(individual_or_bboxes.chromosome)] % len(u.permitted_postures)
                    postures.append(u.permitted_postures[p_idx])
                else:
                    postures.append(Posture.LWH)
    else:
        placed_data = placed_blocks_or_data
        placed_bboxes = getattr(individual_or_bboxes, "placed_bboxes", []) or []
        postures = getattr(individual_or_bboxes, "placed_postures", None) or []
        if not postures:
            postures = [Posture.LWH] * len(placed_data)

    for unit, bbox, posture in zip(placed_data, placed_bboxes, postures):
        if isinstance(unit, Block):
            for content in unit.contents:
                rel_pos = Position(content.rel_x, content.rel_y, content.rel_z)
                world_rel_pos = transform_position_by_posture(rel_pos, posture)

                abs_x = bbox.min_x + world_rel_pos.x
                abs_y = bbox.min_y + world_rel_pos.y
                abs_z = bbox.min_z + world_rel_pos.z

                content_dims = Dimensions(
                    content.length_cm, content.width_cm, content.height_cm
                ).apply_posture(posture)

                placed_boxes.append(
                    PlacedBox(
                        box_id=content.box_id,
                        item_id=content.item_id,
                        po_no=content.po_no,
                        customer_code=content.customer_code,
                        customer_sequence=content.customer_sequence,
                        length_cm=content.length_cm,
                        width_cm=content.width_cm,
                        height_cm=content.height_cm,
                        weight_kg=content.weight_kg,
                        this_way_up=content.this_way_up,
                        stacking_group=content.stacking_group,
                        max_load_bearing_kg=content.max_load_bearing_kg,
                        permitted_postures=content.permitted_postures,
                        inflated_length=content.inflated_length,
                        inflated_width=content.inflated_width,
                        inflated_height=content.inflated_height,
                        x=abs_x,
                        y=abs_y,
                        z=abs_z,
                        posture=posture,
                        actual_length=content_dims.length,
                        actual_width=content_dims.width,
                        actual_height=content_dims.height,
                    )
                )
        else:
            actual_dims = Dimensions(
                unit.length_cm, unit.width_cm, unit.height_cm
            ).apply_posture(posture)

            placed_boxes.append(
                PlacedBox(
                    box_id=unit.box_id,
                    item_id=unit.item_id,
                    po_no=unit.po_no,
                    customer_code=unit.customer_code,
                    customer_sequence=unit.customer_sequence,
                    length_cm=unit.length_cm,
                    width_cm=unit.width_cm,
                    height_cm=unit.height_cm,
                    weight_kg=unit.weight_kg,
                    this_way_up=unit.this_way_up,
                    stacking_group=unit.stacking_group,
                    max_load_bearing_kg=unit.max_load_bearing_kg,
                    permitted_postures=unit.permitted_postures,
                    inflated_length=unit.inflated_length,
                    inflated_width=unit.inflated_width,
                    inflated_height=unit.inflated_height,
                    x=bbox.min_x,
                    y=bbox.min_y,
                    z=bbox.min_z,
                    posture=posture,
                    actual_length=actual_dims.length,
                    actual_width=actual_dims.width,
                    actual_height=actual_dims.height,
                )
            )

    return placed_boxes


def build_layers(placed_boxes: List[PlacedBox], layer_depth: float = 50.0) -> List[Layer]:
    """Partition placed boxes into sequential longitudinal layers along the X-axis.

    Layers are ordered from the rear wall (deepest, highest X) toward the
    container door (lowest X), so Layer 0 = rear-most slab and the last layer
    = door-facing slab.  A box is included in a layer when its X-interval
    [box.x, box.x + box.actual_length) overlaps the layer band.

    Args:
        placed_boxes: All successfully placed boxes.
        layer_depth:  Thickness of each longitudinal slice in cm (default 50).
    """
    if not placed_boxes:
        return []

    # Determine the container depth that was actually used.
    max_x = max(b.x + b.actual_length for b in placed_boxes)

    # Build bands from rear (max_x) to door (0), each of width layer_depth.
    # Band k covers [max_x - (k+1)*layer_depth, max_x - k*layer_depth].
    num_layers = int(max_x / layer_depth) + 1

    layers = []
    for k in range(num_layers):
        x_max = max_x - k * layer_depth
        x_min = max_x - (k + 1) * layer_depth
        # Boxes whose X-interval overlaps [x_min, x_max)
        layer_boxes = [
            b for b in placed_boxes
            if b.x < x_max and (b.x + b.actual_length) > x_min
        ]
        if layer_boxes:
            layers.append(Layer(x_min=x_min, x_max=x_max, boxes=layer_boxes))

    return layers


def calculate_metrics(
    placed_boxes: List[PlacedBox],
    unplaced: List[UnplacedCarton],
    container_dims: Dimensions,
    max_weight: float,
) -> LoadMetrics:
    placed_count = len(placed_boxes)
    unplaced_count = len(unplaced)
    total_cartons = placed_count + unplaced_count

    placed_volume = sum(
        b.actual_length * b.actual_width * b.actual_height for b in placed_boxes
    )
    container_volume = container_dims.length * container_dims.width * container_dims.height
    fill_rate = placed_volume / container_volume if container_volume > 0 else 0

    used_weight = sum(b.weight_kg for b in placed_boxes)
    weight_util = used_weight / max_weight if max_weight > 0 else 0

    from app.solver.geometry import calculate_cog, check_cog_balance
    from app.config import get_settings
    settings = get_settings()

    weights = [b.weight_kg for b in placed_boxes]
    cog = calculate_cog(
        [BoundingBox.from_position_and_dims(
            Position(b.x, b.y, b.z),
            Dimensions(b.actual_length, b.actual_width, b.actual_height)
        ) for b in placed_boxes],
        weights,
    )

    _, cog_dev_xy, cog_dev_z = check_cog_balance(
        cog, container_dims, settings.COG_TOLERANCE_XY, settings.COG_TOLERANCE_Z
    )

    return LoadMetrics(
        placed_count=placed_count,
        unplaced_count=unplaced_count,
        total_cartons=total_cartons,
        fill_rate=fill_rate,
        used_weight_kg=used_weight,
        max_weight_kg=max_weight,
        weight_utilization=weight_util,
        cog_x=cog.x,
        cog_y=cog.y,
        cog_z=cog.z,
        cog_deviation_xy=cog_dev_xy,
        cog_deviation_z=cog_dev_z,
    )


def build_unplaced_cartons(
    unplaced_boxes: List[Box],
    unplaced_blocks: List[Block],
    is_lcl: bool,
) -> List[UnplacedCarton]:
    result = []
    seen_box_ids = set()

    for box in unplaced_boxes:
        if box.box_id in seen_box_ids:
            continue
        seen_box_ids.add(box.box_id)
        
        reason = UnplacedReason.NO_SPACE
        if is_lcl:
            reason = UnplacedReason.NO_SPACE
        result.append(
            UnplacedCarton(
                box_id=box.box_id,
                item_id=box.item_id,
                po_no=box.po_no,
                customer_code=box.customer_code,
                customer_sequence=box.customer_sequence,
                reason=reason,
                length_cm=box.length_cm,
                width_cm=box.width_cm,
                height_cm=box.height_cm,
                weight_kg=box.weight_kg,
            )
        )

    for block in unplaced_blocks:
        for content in block.contents:
            if content.box_id in seen_box_ids:
                continue
            seen_box_ids.add(content.box_id)
            
            reason = UnplacedReason.NO_SPACE
            if is_lcl:
                reason = UnplacedReason.NO_SPACE
            result.append(
                UnplacedCarton(
                    box_id=content.box_id,
                    item_id=content.item_id,
                    po_no=content.po_no,
                    customer_code=content.customer_code,
                    customer_sequence=content.customer_sequence,
                    reason=reason,
                    length_cm=content.length_cm,
                    width_cm=content.width_cm,
                    height_cm=content.height_cm,
                    weight_kg=content.weight_kg,
                )
            )

    return result


def build_run_result(
    individual: Individual,
    container_dims: Dimensions,
    container_spec,
    placed_blocks: List[Block],
    unplaced_blocks: List[Block],
    all_boxes: List[Box],
    unplaced_boxes: List[Box],
    is_lcl: bool,
    placed_individual_boxes: List[Box] = None,
    placed_bboxes: List = None,
    placed_data: List = None,
    placed_postures: List = None,
    run_id: str = None,
    status: str = "completed",
    error_message: str = None,
    options=None,
) -> RunResult:
    if run_id is None:
        run_id = str(uuid.uuid4())

    if placed_bboxes is None and individual is not None:
        placed_bboxes = getattr(individual, "placed_bboxes", None)
    if placed_data is None and individual is not None:
        placed_data = getattr(individual, "placed_data", None)
    if placed_postures is None and individual is not None:
        placed_postures = getattr(individual, "placed_postures", None)

    if placed_bboxes is not None and placed_data is not None and placed_postures is not None:
        all_placed_boxes = explode_blocks(placed_data, placed_bboxes, placed_postures)
    else:
        all_placed_boxes = explode_blocks(placed_blocks, individual)

    COLOR_PALETTE = [
        "#3b82f6",  # Blue
        "#10b981",  # Emerald
        "#f59e0b",  # Amber
        "#8b5cf6",  # Purple
        "#ec4899",  # Pink
        "#06b6d4",  # Cyan
        "#ef4444",  # Red
        "#84cc16",  # Lime
        "#14b8a6",  # Teal
        "#f97316",  # Orange
    ]

    # Assign sequential step_index and color to all placed boxes.
    # Sort rear-to-door (descending x) within each customer sequence so that
    # Step 1 begins at the rear wall, matching the loading strategy.
    all_placed_boxes.sort(key=lambda b: (b.customer_sequence, -b.x, b.z, b.y))
    for idx, b in enumerate(all_placed_boxes):
        b.step_index = idx + 1
        color_idx = (b.customer_sequence - 1) % len(COLOR_PALETTE)
        b.color = COLOR_PALETTE[color_idx]

    layers = build_layers(all_placed_boxes)
    unplaced_cartons = build_unplaced_cartons(unplaced_boxes, unplaced_blocks, is_lcl)
    metrics = calculate_metrics(all_placed_boxes, unplaced_cartons, container_dims, container_spec.max_weight_kg)

    layer_data = []
    for layer in layers:
        layer_data.append({
            "x_min": layer.x_min,
            "x_max": layer.x_max,
            "boxes": [
                {
                    "box_id": b.box_id,
                    "item_id": b.item_id,
                    "x": b.x,
                    "y": b.y,
                    "z": b.z,
                    "length": b.actual_length,
                    "width": b.actual_width,
                    "height": b.actual_height,
                    "posture": b.posture,
                    "customer_sequence": b.customer_sequence,
                    "step_index": b.step_index,
                    "color": b.color,
                }
                for b in layer.boxes
            ],
        })

    from app.core.models import Container
    container = Container(
        id=0,
        container_type=container_spec.container_type,
        internal_length_cm=container_spec.internal_length_cm,
        internal_width_cm=container_spec.internal_width_cm,
        internal_height_cm=container_spec.internal_height_cm,
        max_weight_kg=container_spec.max_weight_kg,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    return RunResult(
        run_id=run_id,
        status=status,
        container=container,
        metrics=metrics,
        placed_boxes=all_placed_boxes,
        unplaced_cartons=unplaced_cartons,
        layers=layer_data,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow() if status == "completed" else None,
        error_message=error_message,
        options=options,
    )