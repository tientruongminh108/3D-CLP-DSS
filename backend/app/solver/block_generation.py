from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import math
from app.config import get_settings
from app.solver.parsing import Box
from app.solver.geometry import Dimensions, Posture


@dataclass
class Block:
    block_id: str
    boxes: List[Box]
    length_cm: float
    width_cm: float
    height_cm: float
    weight_kg: float
    customer_sequence: int
    inflated_length: float
    inflated_width: float
    inflated_height: float
    contents: List[Box] = field(default_factory=list)

    def dims(self) -> Dimensions:
        return Dimensions(self.length_cm, self.width_cm, self.height_cm)

    def inflated_dims(self) -> Dimensions:
        return Dimensions(
            self.inflated_length, self.inflated_width, self.inflated_height
        )

    @property
    def this_way_up(self) -> bool:
        """Block is This_Way_Up if any contained box requires it."""
        return any(c.this_way_up for c in self.contents)

    @property
    def permitted_postures(self) -> List[Posture]:
        """Permitted postures per Section 4.2/5.1: 2 if This_Way_Up, 6 otherwise."""
        if self.this_way_up:
            return [Posture.LWH, Posture.WLH]
        return list(Posture)

    @property
    def stacking_group(self) -> int:
        """Most restrictive (smallest) stacking group among contents."""
        return min(c.stacking_group for c in self.contents) if self.contents else 1

    @property
    def max_load_bearing_kg(self) -> Optional[float]:
        """Minimum load bearing capacity among contents."""
        limits = [c.max_load_bearing_kg for c in self.contents if c.max_load_bearing_kg is not None]
        return min(limits) if limits else None


def build_blocks(
    boxes: List[Box],
    container_length: float,
    container_width: float,
    container_height: float,
) -> Tuple[List[Block], List[Box]]:
    settings = get_settings()
    min_fill = settings.MIN_BLOCK_FILL_RATIO
    max_frac = settings.MAX_BLOCK_FRACTION

    groups = defaultdict(list)
    for box in boxes:
        key = (box.length_cm, box.width_cm, box.height_cm, box.customer_sequence)
        groups[key].append(box)

    simple_blocks = []
    leftover = []

    for key, group in groups.items():
        if len(group) < 2:
            leftover.extend(group)
            continue

        length, width, height, cust_seq = key
        single_vol = length * width * height
        box_weight = group[0].weight_kg
        stacking_group = group[0].stacking_group
        this_way_up = group[0].this_way_up
        max_load = group[0].max_load_bearing_kg
        permitted = group[0].permitted_postures
        inflated_l = group[0].inflated_length
        inflated_w = group[0].inflated_width
        inflated_h = group[0].inflated_height

        max_blocks, group_leftover = _build_simple_blocks(
            group,
            length,
            width,
            height,
            single_vol,
            box_weight,
            stacking_group,
            this_way_up,
            max_load,
            permitted,
            inflated_l,
            inflated_w,
            inflated_h,
            cust_seq,
            container_length,
            container_width,
            container_height,
            min_fill,
            max_frac,
        )

        simple_blocks.extend(max_blocks)
        leftover.extend(group_leftover)

    general_blocks = _combine_identical_blocks(
        simple_blocks,
        container_length,
        container_width,
        container_height,
        min_fill,
        max_frac,
    )

    similar_blocks = _combine_similar_blocks(
        general_blocks,
        container_length,
        container_width,
        container_height,
        min_fill,
        max_frac,
    )

    all_blocks = similar_blocks

    final_blocks = []
    final_leftover = leftover

    for block in all_blocks:
        final_blocks.append(block)

    return final_blocks, final_leftover


def _build_simple_blocks(
    boxes: List[Box],
    length: float,
    width: float,
    height: float,
    single_vol: float,
    box_weight: float,
    stacking_group: int,
    this_way_up: bool,
    max_load: float,
    permitted: List[Posture],
    inflated_l: float,
    inflated_w: float,
    inflated_h: float,
    cust_seq: int,
    container_length: float,
    container_width: float,
    container_height: float,
    min_fill: float,
    max_frac: float,
) -> Tuple[List[Block], List[Box]]:
    blocks = []
    leftover = []

    axis_lengths = [length, width, height]
    axis_inflated = [inflated_l, inflated_w, inflated_h]
    max_count = len(boxes)
    best_block = None
    best_count = 0
    best_axis = -1

    for axis in range(3):
        other_axes = [i for i in range(3) if i != axis]

        for count in range(2, max_count + 1):
            dims = [0, 0, 0]
            dims[axis] = axis_lengths[axis] * count
            dims[other_axes[0]] = axis_lengths[other_axes[0]]
            dims[other_axes[1]] = axis_lengths[other_axes[1]]

            inflated_dims = [0, 0, 0]
            inflated_dims[axis] = axis_inflated[axis] * count
            inflated_dims[other_axes[0]] = axis_inflated[other_axes[0]]
            inflated_dims[other_axes[1]] = axis_inflated[other_axes[1]]

            if not _fits_bounds(
                dims,
                inflated_dims,
                container_length,
                container_width,
                container_height,
                max_frac,
                axis_lengths,
                axis_inflated,
                stacking_axis=axis,
            ):
                break

            # No fill_ratio check for simple blocks (Step 2) per guide
            # Fill ratio only applies to Steps 3-4 (combining blocks)

            # Set relative positions for contents
            contents = []
            for i in range(count):
                box = boxes[i]
                rel_pos = [0.0, 0.0, 0.0]
                rel_pos[axis] = axis_inflated[axis] * i
                content_box = Box(
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
                    rel_x=rel_pos[0],
                    rel_y=rel_pos[1],
                    rel_z=rel_pos[2],
                )
                contents.append(content_box)

            if count > best_count:
                best_count = count
                best_block = Block(
                    block_id=f"B_{cust_seq}_{length}x{width}x{height}_axis{axis}_{count}",
                    boxes=boxes[:count],
                    length_cm=dims[0],
                    width_cm=dims[1],
                    height_cm=dims[2],
                    weight_kg=box_weight * count,
                    customer_sequence=cust_seq,
                    inflated_length=inflated_dims[0],
                    inflated_width=inflated_dims[1],
                    inflated_height=inflated_dims[2],
                    contents=contents,
                )
                best_axis = axis

    if best_block:
        blocks.append(best_block)
        # Add unused boxes to leftover
        leftover.extend(boxes[best_count:])
    else:
        # No block could be created, all boxes go to leftover
        leftover.extend(boxes)

    return blocks, leftover


def _fits_bounds(
    dims: List[float],
    inflated_dims: List[float],
    container_length: float,
    container_width: float,
    container_height: float,
    max_frac: float,
    native_dims: List[float],
    native_inflated: List[float],
    stacking_axis: int = None,
) -> bool:
    """
    Check if block fits within container and MAX_BLOCK_FRACTION limits.
    
    Per Section 5.1: block cross-section (axes perpendicular to stacking axis)
    must not exceed 40% of container dimensions. Stacking axis can grow up to
    container length.
    """
    container_dims = [container_length, container_width, container_height]

    for i in range(3):
        # Must fit in container
        if inflated_dims[i] > container_dims[i]:
            return False

        # On stacking axis: no fraction limit (can grow to container length)
        # On cross-section axes: enforce MAX_BLOCK_FRACTION
        if stacking_axis is not None and i == stacking_axis:
            continue  # No fraction limit on stacking axis
        
        limit = container_dims[i] * max_frac
        if inflated_dims[i] > limit:
            return False

    return True


def _combine_identical_blocks(
    blocks: List[Block],
    container_length: float,
    container_width: float,
    container_height: float,
    min_fill: float,
    max_frac: float,
) -> List[Block]:
    groups = defaultdict(list)
    for block in blocks:
        key = (
            block.length_cm,
            block.width_cm,
            block.height_cm,
            block.customer_sequence,
        )
        groups[key].append(block)

    combined = []
    for key, group in groups.items():
        if len(group) < 2:
            combined.extend(group)
            continue

        length, width, height, cust_seq = key
        single_vol = length * width * height
        weight = group[0].weight_kg / (len(group[0].boxes) if group[0].boxes else 1)
        stacking_group = group[0].boxes[0].stacking_group if group[0].boxes else 1
        this_way_up = group[0].boxes[0].this_way_up if group[0].boxes else True
        max_load = group[0].boxes[0].max_load_bearing_kg if group[0].boxes else None
        permitted = group[0].boxes[0].permitted_postures if group[0].boxes else []
        inflated_l = group[0].inflated_length / (len(group[0].boxes) if group[0].boxes else 1)
        inflated_w = group[0].inflated_width / (len(group[0].boxes) if group[0].boxes else 1)
        inflated_h = group[0].inflated_height / (len(group[0].boxes) if group[0].boxes else 1)

        best_blocks = []
        remaining = group[:]

        while len(remaining) >= 2:
            b1 = remaining.pop(0)
            b2 = remaining.pop(0)

            for axis in range(3):
                new_dims = [b1.length_cm, b1.width_cm, b1.height_cm]
                new_inflated = [b1.inflated_length, b1.inflated_width, b1.inflated_height]

                new_dims[axis] += b2.length_cm if axis == 0 else (
                    b2.width_cm if axis == 1 else b2.height_cm
                )
                new_inflated[axis] += b2.inflated_length if axis == 0 else (
                    b2.inflated_width if axis == 1 else b2.inflated_height
                )

                if _fits_bounds(
                    new_dims,
                    new_inflated,
                    container_length,
                    container_width,
                    container_height,
                    max_frac,
                    [length, width, height],
                    [inflated_l, inflated_w, inflated_h],
                    stacking_axis=axis,
                ):
                    new_vol = new_dims[0] * new_dims[1] * new_dims[2]
                    fill_ratio = (len(b1.boxes) + len(b2.boxes)) * single_vol / new_vol

                    if fill_ratio >= min_fill:
                        # Offset b2's contents by b1's extent along the merge axis
                        offset = [0.0, 0.0, 0.0]
                        offset[axis] = b1.inflated_length if axis == 0 else (
                            b1.inflated_width if axis == 1 else b1.inflated_height
                        )
                        
                        merged_contents = []
                        for c in b1.contents:
                            merged_contents.append(c)
                        for c in b2.contents:
                            # Create copy with offset relative position
                            merged_contents.append(Box(
                                box_id=c.box_id,
                                item_id=c.item_id,
                                po_no=c.po_no,
                                customer_code=c.customer_code,
                                customer_sequence=c.customer_sequence,
                                length_cm=c.length_cm,
                                width_cm=c.width_cm,
                                height_cm=c.height_cm,
                                weight_kg=c.weight_kg,
                                this_way_up=c.this_way_up,
                                stacking_group=c.stacking_group,
                                max_load_bearing_kg=c.max_load_bearing_kg,
                                permitted_postures=c.permitted_postures,
                                inflated_length=c.inflated_length,
                                inflated_width=c.inflated_width,
                                inflated_height=c.inflated_height,
                                rel_x=c.rel_x + offset[0],
                                rel_y=c.rel_y + offset[1],
                                rel_z=c.rel_z + offset[2],
                            ))

                        merged = Block(
                            block_id=f"B_{cust_seq}_{new_dims[0]}x{new_dims[1]}x{new_dims[2]}_merged",
                            boxes=b1.boxes + b2.boxes,
                            length_cm=new_dims[0],
                            width_cm=new_dims[1],
                            height_cm=new_dims[2],
                            weight_kg=b1.weight_kg + b2.weight_kg,
                            customer_sequence=cust_seq,
                            inflated_length=new_inflated[0],
                            inflated_width=new_inflated[1],
                            inflated_height=new_inflated[2],
                            contents=merged_contents,
                        )
                        best_blocks.append(merged)
                        break
            else:
                best_blocks.append(b1)
                remaining.insert(0, b2)
                break

        best_blocks.extend(remaining)
        combined.extend(best_blocks)

    return combined


def _combine_similar_blocks(
    blocks: List[Block],
    container_length: float,
    container_width: float,
    container_height: float,
    min_fill: float,
    max_frac: float,
) -> List[Block]:
    tolerance = 0.1

    def dims_similar(b1: Block, b2: Block) -> bool:
        return (
            abs(b1.length_cm - b2.length_cm) / max(b1.length_cm, b2.length_cm) <= tolerance
            and abs(b1.width_cm - b2.width_cm) / max(b1.width_cm, b2.width_cm) <= tolerance
            and abs(b1.height_cm - b2.height_cm) / max(b1.height_cm, b2.height_cm) <= tolerance
            and b1.customer_sequence == b2.customer_sequence
        )

    groups = []
    used = set()

    for i, b1 in enumerate(blocks):
        if i in used:
            continue
        group = [b1]
        used.add(i)
        for j, b2 in enumerate(blocks[i + 1 :], i + 1):
            if j not in used and dims_similar(b1, b2):
                group.append(b2)
                used.add(j)
        groups.append(group)

    combined = []
    for group in groups:
        if len(group) < 2:
            combined.extend(group)
            continue

        best_blocks = []
        remaining = group[:]

        while len(remaining) >= 2:
            b1 = remaining.pop(0)
            b2 = remaining.pop(0)

            for axis in range(3):
                new_dims = [b1.length_cm, b1.width_cm, b1.height_cm]
                new_inflated = [b1.inflated_length, b1.inflated_width, b1.inflated_height]

                new_dims[axis] += b2.length_cm if axis == 0 else (
                    b2.width_cm if axis == 1 else b2.height_cm
                )
                new_inflated[axis] += b2.inflated_length if axis == 0 else (
                    b2.inflated_width if axis == 1 else b2.inflated_height
                )

                if _fits_bounds(
                    new_dims,
                    new_inflated,
                    container_length,
                    container_width,
                    container_height,
                    max_frac,
                    [b1.length_cm, b1.width_cm, b1.height_cm],
                    [b1.inflated_length, b1.inflated_width, b1.inflated_height],
                    stacking_axis=axis,
                ):
                    total_boxes = len(b1.contents) + len(b2.contents)
                    avg_vol = (
                        sum(
                            c.length_cm * c.width_cm * c.height_cm
                            for c in b1.contents + b2.contents
                        )
                        / total_boxes
                    )
                    new_vol = new_dims[0] * new_dims[1] * new_dims[2]
                    fill_ratio = (total_boxes * avg_vol) / new_vol

                    if fill_ratio >= min_fill:
                        # Offset b2's contents by b1's extent along the merge axis
                        offset = [0.0, 0.0, 0.0]
                        offset[axis] = b1.inflated_length if axis == 0 else (
                            b1.inflated_width if axis == 1 else b1.inflated_height
                        )
                        
                        merged_contents = []
                        for c in b1.contents:
                            merged_contents.append(c)
                        for c in b2.contents:
                            merged_contents.append(Box(
                                box_id=c.box_id,
                                item_id=c.item_id,
                                po_no=c.po_no,
                                customer_code=c.customer_code,
                                customer_sequence=c.customer_sequence,
                                length_cm=c.length_cm,
                                width_cm=c.width_cm,
                                height_cm=c.height_cm,
                                weight_kg=c.weight_kg,
                                this_way_up=c.this_way_up,
                                stacking_group=c.stacking_group,
                                max_load_bearing_kg=c.max_load_bearing_kg,
                                permitted_postures=c.permitted_postures,
                                inflated_length=c.inflated_length,
                                inflated_width=c.inflated_width,
                                inflated_height=c.inflated_height,
                                rel_x=c.rel_x + offset[0],
                                rel_y=c.rel_y + offset[1],
                                rel_z=c.rel_z + offset[2],
                            ))

                        merged = Block(
                            block_id=f"B_{b1.customer_sequence}_{new_dims[0]}x{new_dims[1]}x{new_dims[2]}_similar",
                            boxes=b1.boxes + b2.boxes,
                            length_cm=new_dims[0],
                            width_cm=new_dims[1],
                            height_cm=new_dims[2],
                            weight_kg=b1.weight_kg + b2.weight_kg,
                            customer_sequence=b1.customer_sequence,
                            inflated_length=new_inflated[0],
                            inflated_width=new_inflated[1],
                            inflated_height=new_inflated[2],
                            contents=merged_contents,
                        )
                        best_blocks.append(merged)
                        break
            else:
                best_blocks.append(b1)
                remaining.insert(0, b2)
                break

        best_blocks.extend(remaining)
        combined.extend(best_blocks)

    return combined