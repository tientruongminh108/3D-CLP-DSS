from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, replace as dc_replace
from collections import defaultdict
from functools import cached_property
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

    @cached_property
    def this_way_up(self) -> bool:
        """Block is This_Way_Up if any contained box requires it."""
        return any(c.this_way_up for c in self.contents)

    @cached_property
    def permitted_postures(self) -> List[Posture]:
        """Permitted postures: 2 if This_Way_Up, 6 otherwise."""
        if self.this_way_up:
            return [Posture.LWH, Posture.WLH]
        return list(Posture)

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
    max_frac = [
        settings.MAX_BLOCK_FRACTION_X,
        settings.MAX_BLOCK_FRACTION_Y,
        settings.MAX_BLOCK_FRACTION_Z,
    ]

    groups = defaultdict(list)
    for box in boxes:
        key = (box.item_id, box.length_cm, box.width_cm, box.height_cm, box.customer_sequence)
        groups[key].append(box)

    simple_blocks = []
    leftover = []

    for key, group in groups.items():
        if len(group) < 2:
            leftover.extend(group)
            continue

        item_id, length, width, height, cust_seq = key
        single_vol = length * width * height
        box_weight = group[0].weight_kg
        this_way_up = group[0].this_way_up
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
            this_way_up,
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

    # Fix #11: remove the dead no-op copy loop that was here.
    return list(similar_blocks), leftover


def _build_simple_blocks(
    boxes: List[Box],
    length: float,
    width: float,
    height: float,
    single_vol: float,
    box_weight: float,
    this_way_up: bool,
    permitted: List[Posture],
    inflated_l: float,
    inflated_w: float,
    inflated_h: float,
    cust_seq: int,
    container_length: float,
    container_width: float,
    container_height: float,
    min_fill: float,
    max_frac: List[float],
) -> Tuple[List[Block], List[Box]]:
    if isinstance(max_frac, (int, float)):
        max_frac = [float(max_frac), float(max_frac), float(max_frac)]
    blocks = []
    leftover = []
    remaining = list(boxes)

    axis_lengths = [length, width, height]
    axis_inflated = [inflated_l, inflated_w, inflated_h]
    block_counter = 0

    max_nx = max(1, int(container_length // inflated_l))
    max_ny = max(1, int(container_width // inflated_w))
    max_nz = max(1, int(container_height // inflated_h))

    while len(remaining) >= 2:
        valid_configs = []
        for nx in range(1, max_nx + 1):
            for ny in range(1, max_ny + 1):
                for nz in range(1, max_nz + 1):
                    k = nx * ny * nz
                    if k < 2 or k > len(remaining):
                        continue
                    dims = [length * nx, width * ny, height * nz]
                    infl = [inflated_l * nx, inflated_w * ny, inflated_h * nz]
                    if _fits_bounds(
                        dims,
                        infl,
                        container_length,
                        container_width,
                        container_height,
                        max_frac,
                        axis_lengths,
                        axis_inflated,
                    ):
                        cubicity = min(dims) / max(dims)
                        footprint_aspect = min(dims[0], dims[1]) / max(dims[0], dims[1])
                        valid_configs.append((k, nx, ny, nz, dims, infl, cubicity, footprint_aspect))

        if not valid_configs:
            break

        def rank_key(cfg):
            k, nx, ny, nz, dims, infl, cubicity, footprint_aspect = cfg
            rem = len(remaining) % k
            num_axes_gt_1 = (1 if nx > 1 else 0) + (1 if ny > 1 else 0) + (1 if nz > 1 else 0)
            total_absorbed = len(remaining) - rem
            # Standard 3D-CLP ranking:
            # 1. Maximize total boxes absorbed in this iteration (minimizes leftovers)
            # 2. Prefer cubicity (most cubic / square block - "vuông vức nhất có thể")
            # 3. Prefer 2D footprint squareness (Dx ≈ Dy)
            # 4. Prefer 3D compactness (num_axes_gt_1)
            # 5. Prefer vertical stacking (nz) over floor sprawl
            # 6. Prefer larger block size k
            return (total_absorbed, round(cubicity, 2), round(footprint_aspect, 2), num_axes_gt_1, nz, k)

        valid_configs.sort(key=rank_key, reverse=True)
        best_k, best_nx, best_ny, best_nz, best_dims, best_infl, _, _ = valid_configs[0]

        num_blocks = len(remaining) // best_k
        for _ in range(num_blocks):
            block_counter += 1
            chosen_boxes = remaining[:best_k]
            remaining = remaining[best_k:]

            contents = []
            box_idx = 0
            for ix in range(best_nx):
                for iy in range(best_ny):
                    for iz in range(best_nz):
                        b = chosen_boxes[box_idx]
                        box_idx += 1
                        contents.append(Box(
                            box_id=b.box_id,
                            item_id=b.item_id,
                            po_no=b.po_no,
                            customer_code=b.customer_code,
                            customer_sequence=b.customer_sequence,
                            length_cm=b.length_cm,
                            width_cm=b.width_cm,
                            height_cm=b.height_cm,
                            weight_kg=b.weight_kg,
                            this_way_up=b.this_way_up,
                            permitted_postures=b.permitted_postures,
                            inflated_length=b.inflated_length,
                            inflated_width=b.inflated_width,
                            inflated_height=b.inflated_height,
                            rel_x=inflated_l * ix,
                            rel_y=inflated_w * iy,
                            rel_z=inflated_h * iz,
                        ))

            blocks.append(Block(
                block_id=f"B_{cust_seq}_{best_dims[0]:.1f}x{best_dims[1]:.1f}x{best_dims[2]:.1f}_3D_{best_nx}x{best_ny}x{best_nz}_{block_counter}",
                boxes=chosen_boxes,
                length_cm=best_dims[0],
                width_cm=best_dims[1],
                height_cm=best_dims[2],
                weight_kg=box_weight * best_k,
                customer_sequence=cust_seq,
                inflated_length=best_infl[0],
                inflated_width=best_infl[1],
                inflated_height=best_infl[2],
                contents=contents,
            ))

    leftover.extend(remaining)
    return blocks, leftover


def _fits_bounds(
    dims: List[float],
    inflated_dims: List[float],
    container_length: float,
    container_width: float,
    container_height: float,
    max_frac: List[float],
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
    if isinstance(max_frac, (int, float)):
        max_frac = [float(max_frac), float(max_frac), float(max_frac)]

    container_dims = [container_length, container_width, container_height]

    for i in range(3):
        # Must physically fit in container
        if inflated_dims[i] > container_dims[i]:
            return False

        native = native_inflated[i] if native_inflated else dims[i]
        effective_cap = max(container_dims[i] * max_frac[i], native)
        if inflated_dims[i] > effective_cap:
            return False

    return True


def _combine_identical_blocks(
    blocks: List[Block],
    container_length: float,
    container_width: float,
    container_height: float,
    min_fill: float,
    max_frac: List[float],
) -> List[Block]:
    if isinstance(max_frac, (int, float)):
        max_frac = [float(max_frac), float(max_frac), float(max_frac)]
    groups = defaultdict(list)
    for block in blocks:
        item_id = block.contents[0].item_id if block.contents else ""
        key = (
            item_id,
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

        cust_seq = key[4]
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
                            # Fix 1: For identical-dimension blocks the fill ratio is
                            # ALWAYS 1.0 (all boxes are the same size — zero void space).
                            # Skip the redundant computation and merge unconditionally
                            # whenever _fits_bounds passes.
                            offset = [0.0, 0.0, 0.0]
                            offset[axis] = b1_infl[axis]

                            merged_contents = list(b1.contents)
                            for c in b2.contents:
                                merged_contents.append(dc_replace(
                                    c,
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
    max_frac: List[float],
) -> List[Block]:
    if isinstance(max_frac, (int, float)):
        max_frac = [float(max_frac), float(max_frac), float(max_frac)]
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

        # BUG-13 fix: replace list.pop(j) (O(N) shift) with an index-set approach.
        # Build a working list; track which indices have been merged.
        changed = True
        current = list(group)
        while changed:
            changed = False
            merged_set: set = set()  # indices in `current` that have been consumed
            next_round: list = []

            for i in range(len(current)):
                if i in merged_set:
                    continue
                b1 = current[i]
                did_merge = False

                for j in range(i + 1, len(current)):
                    if j in merged_set:
                        continue
                    b2 = current[j]

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
                            new_dims, new_inflated,
                            container_length, container_width, container_height,
                            max_frac, native_d, native_i, stacking_axis=axis,
                        ):
                            actual_vol = sum(
                                c.length_cm * c.width_cm * c.height_cm
                                for c in b1.contents + b2.contents
                            )
                            new_vol = new_dims[0] * new_dims[1] * new_dims[2]
                            fill_ratio = actual_vol / new_vol if new_vol > 0 else 0

                            if fill_ratio >= min_fill:
                                offset = [0.0, 0.0, 0.0]
                                offset[axis] = (
                                    b1.inflated_length if axis == 0 else (
                                        b1.inflated_width if axis == 1 else b1.inflated_height
                                    )
                                )

                                merged_contents = list(b1.contents)
                                for c in b2.contents:
                                    merged_contents.append(dc_replace(
                                        c,
                                        rel_x=c.rel_x + offset[0],
                                        rel_y=c.rel_y + offset[1],
                                        rel_z=c.rel_z + offset[2],
                                    ))

                                merged_block = Block(
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
                                merged_set.add(i)
                                merged_set.add(j)
                                next_round.append(merged_block)
                                changed = True
                                did_merge = True
                                break  # break axis loop

                    if did_merge:
                        break  # break j loop

                if not did_merge:
                    next_round.append(b1)

            current = next_round

        combined.extend(current)

    return combined