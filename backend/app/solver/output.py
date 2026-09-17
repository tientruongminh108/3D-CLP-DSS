from typing import List, Dict, Any
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
    z_min: float
    z_max: float
    boxes: List[PlacedBox]


def transform_position_by_posture(pos: Position, posture: Posture, block_dims: Dimensions) -> Position:
    """Transform a position from block-local coordinates to world coordinates
    given the block's posture. The block's origin corner is at (0,0,0) in its
    local coordinate system."""
    x, y, z = pos.x, pos.y, pos.z
    l, w, h = block_dims.length, block_dims.width, block_dims.height
    
    if posture == Posture.LWH:
        return Position(x, y, z)
    elif posture == Posture.WLH:
        return Position(y, x, z)
    elif posture == Posture.HLW:
        return Position(h - z, x, y)
    elif posture == Posture.HWL:
        return Position(h - z, y, x)
    elif posture == Posture.LHW:
        return Position(x, h - z, y)
    elif posture == Posture.WHL:
        return Position(y, h - z, x)
    return Position(x, y, z)


def explode_blocks(placed_blocks: List[Block], individual: Individual) -> List[PlacedBox]:
    """Explode block placements back into individual boxes with correct positions.
    
    Per Section 5.2.4: each block's contents have positions relative to the block's
    origin corner. When the block is placed at absolute position with a posture,
    each content box's absolute position = block_position + transform(content_rel_pos, block_posture).
    """
    placed_boxes = []

    # Build a mapping from block to its placement info
    block_to_placement = {}
    for bbox in individual.placed_bboxes:
        # We need to match by finding which block this bbox corresponds to
        # For now, we'll iterate through placed_blocks and find the matching one
        pass
    
    # Instead, let's use the individual's placed_data which should have the boxes
    # But blocks are in individual's units... let's use a different approach
    # The individual's chromosome was evaluated, and we have placed_bboxes for blocks
    
    for i, block in enumerate(placed_blocks):
        if i >= len(individual.placed_bboxes):
            break
            
        block_bbox = individual.placed_bboxes[i]
        # Get the posture used for this block
        if i < len(individual.chromosome) and block.boxes:
            posture_idx = individual.chromosome[i] % len(block.boxes[0].permitted_postures)
            posture = block.boxes[0].permitted_postures[posture_idx]
        else:
            posture = Posture.LWH

        block_pos = Position(block_bbox.min_x, block_bbox.min_y, block_bbox.min_z)
        block_dims = Dimensions(block.length_cm, block.width_cm, block.height_cm)

        for content in block.contents:
            # Transform relative position by block's posture
            rel_pos = Position(content.rel_x, content.rel_y, content.rel_z)
            world_rel_pos = transform_position_by_posture(rel_pos, posture, block_dims)
            
            # Absolute position = block position + transformed relative position
            abs_x = block_pos.x + world_rel_pos.x
            abs_y = block_pos.y + world_rel_pos.y
            abs_z = block_pos.z + world_rel_pos.z

            # The content box's actual dimensions under the block's posture
            content_dims = Dimensions(content.length_cm, content.width_cm, content.height_cm)
            actual_dims = content_dims.apply_posture(posture)

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
                    actual_length=actual_dims.length,
                    actual_width=actual_dims.width,
                    actual_height=actual_dims.height,
                )
            )

    return placed_boxes


def build_layers(placed_boxes: List[PlacedBox], layer_height: float = 50.0) -> List[Layer]:
    if not placed_boxes:
        return []

    max_z = max(b.z + b.actual_height for b in placed_boxes)
    num_layers = int(max_z / layer_height) + 1

    layers = []
    for i in range(num_layers):
        z_min = i * layer_height
        z_max = (i + 1) * layer_height
        layer_boxes = [
            b for b in placed_boxes
            if b.z < z_max and (b.z + b.actual_height) > z_min
        ]
        if layer_boxes:
            layers.append(Layer(z_min=z_min, z_max=z_max, boxes=layer_boxes))

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
    run_id: str = None,
    status: str = "completed",
    error_message: str = None,
) -> RunResult:
    if run_id is None:
        run_id = str(uuid.uuid4())

    exploded_boxes = explode_blocks(placed_blocks, individual)
    
    # Add individually placed boxes (leftover boxes that were placed directly)
    all_placed_boxes = list(exploded_boxes)
    
    if placed_individual_boxes:
        # These are the leftover boxes that were placed individually
        # We need to find their positions from decode_chromosome results
        # placed_individual_boxes comes from pipeline's separation logic
        if placed_bboxes and placed_data:
            # Build a map from box_id to bbox for quick lookup
            # placed_data contains both blocks and individual boxes in the same order as all_units
            # We need to match placed_individual_boxes to their bboxes
            box_to_bbox = {}
            for i, box in enumerate(placed_data):
                if box is not None and not isinstance(box, Block):
                    if i < len(placed_bboxes):
                        box_to_bbox[box.box_id] = placed_bboxes[i]
            
            for box in placed_individual_boxes:
                if box.box_id in box_to_bbox:
                    bbox = box_to_bbox[box.box_id]
                    posture = Posture.LWH
                    if box.permitted_postures:
                        posture = box.permitted_postures[0]
                    
                    content_dims = Dimensions(box.length_cm, box.width_cm, box.height_cm)
                    actual_dims = content_dims.apply_posture(posture)
                    
                    all_placed_boxes.append(
                        PlacedBox(
                            box_id=box.box_id,
                            item_id=box.item_id,
                            po_no=box.po_no,
                            customer_code=box.customer_code,
                            customer_sequence=box.customer_sequence,
                            length_cm=box.length_cm,
                            width_cm=box.width_cm,
                            height_cm=box.height_cm,
                            weight_kg=box.weight_kg,
                            this_way_up=box.this_way_up,
                            stacking_group=box.stacking_group,
                            max_load_bearing_kg=box.max_load_bearing_kg,
                            permitted_postures=box.permitted_postures,
                            inflated_length=box.inflated_length,
                            inflated_width=box.inflated_width,
                            inflated_height=box.inflated_height,
                            x=bbox.min_x,
                            y=bbox.min_y,
                            z=bbox.min_z,
                            posture=posture,
                            actual_length=actual_dims.length,
                            actual_width=actual_dims.width,
                            actual_height=actual_dims.height,
                        )
                    )

    layers = build_layers(all_placed_boxes)
    unplaced_cartons = build_unplaced_cartons(unplaced_boxes, unplaced_blocks, is_lcl)
    metrics = calculate_metrics(all_placed_boxes, unplaced_cartons, container_dims, container_spec.max_weight_kg)

    layer_data = []
    for layer in layers:
        layer_data.append({
            "z_min": layer.z_min,
            "z_max": layer.z_max,
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
        placed_boxes=exploded_boxes,
        unplaced_cartons=unplaced_cartons,
        layers=layer_data,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow() if status == "completed" else None,
        error_message=error_message,
    )