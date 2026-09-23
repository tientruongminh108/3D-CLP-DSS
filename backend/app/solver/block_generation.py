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
        if not hasattr(self, '_cached_this_way_up'):
            self._cached_this_way_up = any(c.this_way_up for c in self.contents)
        return self._cached_this_way_up

    @property
    def permitted_postures(self) -> List[Posture]:
        """Permitted postures per Section 4.2/5.1: 2 if This_Way_Up, 6 otherwise."""
        if not hasattr(self, '_cached_permitted_postures'):
            if self.this_way_up:
                self._cached_permitted_postures = [Posture.LWH, Posture.WLH]
            else:
                self._cached_permitted_postures = list(Posture)
        return self._cached_permitted_postures

    @property
    def stacking_group(self) -> int:
        """Most restrictive (smallest) stacking group among contents."""
        if not hasattr(self, '_cached_stacking_group'):
            self._cached_stacking_group = min(c.stacking_group for c in self.contents) if self.contents else 1
        return self._cached_stacking_group

    @property
    def max_load_bearing_kg(self) -> Optional[float]:
        """Minimum load bearing capacity among contents."""
        if not hasattr(self, '_cached_max_load_bearing_kg'):
            limits = [c.max_load_bearing_kg for c in self.contents if c.max_load_bearing_kg is not None]
            self._cached_max_load_bearing_kg = min(limits) if limits else None
        return self._cached_max_load_bearing_kg

    @property
    def fill_ratio(self) -> float:
        """Ratio of actual cargo volume of contents to the bounding box volume."""
        vol = self.length_cm * self.width_cm * self.height_cm
        if vol <= 0:
            return 0.0
        cargo_vol = sum(c.length_cm * c.width_cm * c.height_cm for c in self.contents)
        return cargo_vol / vol



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
    remaining = list(boxes)

    axis_lengths = [length, width, height]
    axis_inflated = [inflated_l, inflated_w, inflated_h]
    block_counter = 0

    while len(remaining) >= 2:
        best_count = 0
        best_axis = -1

        for axis in range(3):
            other_axes = [i for i in range(3) if i != axis]

            for count in range(2, len(remaining) + 1):
                dims = [0.0, 0.0, 0.0]
                dims[axis] = axis_lengths[axis] * count
                dims[other_axes[0]] = axis_lengths[other_axes[0]]
                dims[other_axes[1]] = axis_lengths[other_axes[1]]

                inflated_dims = [0.0, 0.0, 0.0]
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

                if count > best_count:
                    best_count = count
                    best_axis = axis

        if best_count < 2:
            break

        block_counter += 1
        chosen_boxes = remaining[:best_count]
        remaining = remaining[best_count:]

        other_axes_for_best = [i for i in range(3) if i != best_axis]
        dims = [0.0, 0.0, 0.0]
        dims[best_axis] = axis_lengths[best_axis] * best_count
        dims[other_axes_for_best[0]] = axis_lengths[other_axes_for_best[0]]
        dims[other_axes_for_best[1]] = axis_lengths[other_axes_for_best[1]]

        inflated_dims = [0.0, 0.0, 0.0]
        inflated_dims[best_axis] = axis_inflated[best_axis] * best_count
        inflated_dims[other_axes_for_best[0]] = axis_inflated[other_axes_for_best[0]]
        inflated_dims[other_axes_for_best[1]] = axis_inflated[other_axes_for_best[1]]

        # Set relative positions for contents
        contents = []
        for i in range(best_count):
            box = chosen_boxes[i]
            rel_pos = [0.0, 0.0, 0.0]
            rel_pos[best_axis] = axis_inflated[best_axis] * i
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

        block = Block(
            block_id=f"B_{cust_seq}_{length}x{width}x{height}_axis{best_axis}_{best_count}_{block_counter}",
            boxes=chosen_boxes,
            length_cm=dims[0],
            width_cm=dims[1],
            height_cm=dims[2],
            weight_kg=box_weight * best_count,
            customer_sequence=cust_seq,
            inflated_length=inflated_dims[0],
            inflated_width=inflated_dims[1],
            inflated_height=inflated_dims[2],
            contents=contents,
        )
        blocks.append(block)

    leftover.extend(remaining)
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
    
    Per Section 5.1 of guide: A block must never be allowed to grow to nearly
    the size of the container itself. The cap constrains growth, never a carton's
    own native size:
    effective_cap = max(container_extent * max_block_fraction, native_extent)
    """
    container_dims = [container_length, container_width, container_height]

    for i in range(3):
        # Must physically fit in container
        if inflated_dims[i] > container_dims[i]:
            return False

        native = native_inflated[i] if native_inflated else dims[i]
        effective_cap = max(container_dims[i] * max_frac, native)
        if inflated_dims[i] > effective_cap:
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

        cust_seq = key[3]
        current_blocks = list(group)
        changed = True
        pass_num = 0

        while changed:
            pass_num += 1
            changed = False
            next_round = []
            used = set()

            for i in range(len(current_blocks)):
                if i in used:
                    continue
                b1 = current_blocks[i]
                merged_with_j = False

                for j in range(i + 1, len(current_blocks)):
                    if j in used:
                        continue
                    b2 = current_blocks[j]

                    for axis in range(3):
                        other_axes = [k for k in range(3) if k != axis]
                        b1_dims = [b1.length_cm, b1.width_cm, b1.height_cm]
                        b2_dims = [b2.length_cm, b2.width_cm, b2.height_cm]

                        # Only merge if dimensions on the other two axes match
                        if (abs(b1_dims[other_axes[0]] - b2_dims[other_axes[0]]) > 1e-4 or
                            abs(b1_dims[other_axes[1]] - b2_dims[other_axes[1]]) > 1e-4):
                            continue

                        b1_infl = [b1.inflated_length, b1.inflated_width, b1.inflated_height]
                        b2_infl = [b2.inflated_length, b2.inflated_width, b2.inflated_height]

                        new_dims = list(b1_dims)
                        new_dims[axis] += b2_dims[axis]

                        new_inflated = list(b1_infl)
                        new_inflated[axis] += b2_infl[axis]

                        native_dims = [max(b1_dims[k], b2_dims[k]) for k in range(3)]
                        native_inflated = [max(b1_infl[k], b2_infl[k]) for k in range(3)]

                        if _fits_bounds(
                            new_dims,
                            new_inflated,
                            container_length,
                            container_width,
                            container_height,
                            max_frac,
                            native_dims,
                            native_inflated,
                            stacking_axis=axis,
                        ):
                            new_vol = new_dims[0] * new_dims[1] * new_dims[2]
                            actual_cargo_vol = sum(
                                c.length_cm * c.width_cm * c.height_cm
                                for c in b1.contents + b2.contents
                            )
                            fill_ratio = actual_cargo_vol / new_vol if new_vol > 0 else 0

                            if fill_ratio >= min_fill:
                                offset = [0.0, 0.0, 0.0]
                                offset[axis] = b1_infl[axis]

                                merged_contents = list(b1.contents)
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
                                    block_id=f"B_{cust_seq}_{new_dims[0]}x{new_dims[1]}x{new_dims[2]}_merged_p{pass_num}",
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
                                next_round.append(merged)
                                used.add(i)
                                used.add(j)
                                changed = True
                                merged_with_j = True
                                break

                    if merged_with_j:
                        break

                if not merged_with_j:
                    next_round.append(b1)
                    used.add(i)

            current_blocks = next_round

        combined.extend(current_blocks)

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

        final_group = []
        remaining = list(group)

        while remaining:
            b1 = remaining.pop(0)
            merged = False

            for j in range(len(remaining)):
                b2 = remaining[j]

                for axis in range(3):
                    other_axes = [k for k in range(3) if k != axis]
                    b1_dims = [b1.length_cm, b1.width_cm, b1.height_cm]
                    b1_infl = [b1.inflated_length, b1.inflated_width, b1.inflated_height]
                    b2_dims = [b2.length_cm, b2.width_cm, b2.height_cm]
                    b2_infl = [b2.inflated_length, b2.inflated_width, b2.inflated_height]

                    new_dims = [0.0, 0.0, 0.0]
                    new_inflated = [0.0, 0.0, 0.0]
                    new_dims[axis] = b1_dims[axis] + b2_dims[axis]
                    new_inflated[axis] = b1_infl[axis] + b2_infl[axis]
                    for o in other_axes:
                        new_dims[o] = max(b1_dims[o], b2_dims[o])
                        new_inflated[o] = max(b1_infl[o], b2_infl[o])

                    native_d = [max(b1_dims[k], b2_dims[k]) for k in range(3)]
                    native_i = [max(b1_infl[k], b2_infl[k]) for k in range(3)]

                    if _fits_bounds(
                        new_dims,
                        new_inflated,
                        container_length,
                        container_width,
                        container_height,
                        max_frac,
                        native_d,
                        native_i,
                        stacking_axis=axis,
                    ):
                        actual_vol = sum(
                            c.length_cm * c.width_cm * c.height_cm
                            for c in b1.contents + b2.contents
                        )
                        new_vol = new_dims[0] * new_dims[1] * new_dims[2]
                        fill_ratio = actual_vol / new_vol if new_vol > 0 else 0

                        if fill_ratio >= min_fill:
                            # Offset b2's contents by b1's extent along the merge axis
                            offset = [0.0, 0.0, 0.0]
                            offset[axis] = (
                                b1.inflated_length if axis == 0 else (
                                    b1.inflated_width if axis == 1 else b1.inflated_height
                                )
                            )

                            merged_contents = list(b1.contents)
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
                            remaining.pop(j)
                            remaining.append(merged)
                            merged = True
                            break

                if merged:
                    break

            if not merged:
                final_group.append(b1)

        combined.extend(final_group)

    return combined