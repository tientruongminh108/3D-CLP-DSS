import pytest
from app.solver.block_generation import build_blocks, Block
from app.solver.parsing import Box
from app.solver.geometry import Posture


def create_test_boxes(count: int, length=100, width=50, height=40, weight=20, cust_seq=0):
    boxes = []
    for i in range(count):
        boxes.append(Box(
            box_id=f"BOX_{i}",
            item_id="TEST",
            po_no="PO-1",
            customer_code="CUST-A" if cust_seq > 0 else None,
            customer_sequence=cust_seq,
            length_cm=length,
            width_cm=width,
            height_cm=height,
            weight_kg=weight,
            this_way_up=True,
            permitted_postures=[Posture.LWH, Posture.WLH],
            inflated_length=length + 2,
            inflated_width=width + 2,
            inflated_height=height,
        ))
    return boxes


def test_build_blocks_simple():
    # Length=50 so 4 boxes (inflated 52*4=208cm) fit within 1200*0.25=300cm cap
    boxes = create_test_boxes(4, length=50, width=50, height=40)
    blocks, leftover = build_blocks(boxes, 1200, 235, 270)

    assert len(blocks) > 0
    assert len(leftover) == 0
    assert len(blocks[0].contents) >= 2


def test_build_blocks_leftover():
    boxes = create_test_boxes(1)
    blocks, leftover = build_blocks(boxes, 1200, 235, 270)

    assert len(blocks) == 0
    assert len(leftover) == 1


def test_build_blocks_mixed_sizes():
    boxes = create_test_boxes(4, length=100, width=50, height=40)
    boxes += create_test_boxes(3, length=80, width=60, height=50)

    blocks, leftover = build_blocks(boxes, 1200, 235, 270)

    assert len(blocks) >= 2


def test_large_quantity_identical_consolidation():
    """Verify that a large quantity of boxes sharing identical dimensions (e.g. 69 cartons)
    consolidates into multi-box blocks instead of stranding them in leftover."""
    # 69 boxes: 15 of ITEM_A, 54 of ITEM_B (identical dimensions 108.6 x 59.7 x 80.4)
    boxes = []
    for i in range(15):
        boxes.append(Box(
            box_id=f"BOX_A_{i}",
            item_id="ITEM_A",
            po_no="PO-1",
            customer_code=None,
            customer_sequence=0,
            length_cm=108.6,
            width_cm=59.7,
            height_cm=80.4,
            weight_kg=30.0,
            this_way_up=True,
            permitted_postures=[Posture.LWH, Posture.WLH],
            inflated_length=110.6,
            inflated_width=61.7,
            inflated_height=80.4,
        ))
    for i in range(54):
        boxes.append(Box(
            box_id=f"BOX_B_{i}",
            item_id="ITEM_B",
            po_no="PO-1",
            customer_code=None,
            customer_sequence=0,
            length_cm=108.6,
            width_cm=59.7,
            height_cm=80.4,
            weight_kg=30.0,
            this_way_up=True,
            permitted_postures=[Posture.LWH, Posture.WLH],
            inflated_length=110.6,
            inflated_width=61.7,
            inflated_height=80.4,
        ))

    container_l, container_w, container_h = 1200.0, 235.0, 270.0
    blocks, leftover = build_blocks(boxes, container_l, container_w, container_h)

    # 1. Total units must be substantially reduced compared to the buggy 68 units (1 block + 67 leftover)
    total_units = len(blocks) + len(leftover)
    assert total_units < 68, f"Expected total units < 68, got {total_units} ({len(blocks)} blocks, {len(leftover)} leftover)"

    # 2. Strict box conservation: all 69 boxes must be accounted for exactly once
    block_boxes = [b for blk in blocks for b in blk.contents]
    assert len(block_boxes) + len(leftover) == 69, "Every box must be either in a block or in leftover"
    all_box_ids = [b.box_id for b in block_boxes] + [b.box_id for b in leftover]
    assert len(set(all_box_ids)) == 69, "No box ID should be duplicated or dropped"

    # 3. Block quality: multi-box contents and high fill ratio
    assert len(blocks) >= 8, f"Expected at least 8 multi-box blocks from 69 boxes, got {len(blocks)}"
    for blk in blocks:
        assert len(blk.contents) >= 2, "Blocks must contain at least 2 boxes"
        assert blk.fill_ratio >= 0.98, f"Fill ratio should be ~1.0 for identical boxes, got {blk.fill_ratio}"


def test_fits_bounds_per_axis():
    from app.solver.block_generation import _fits_bounds

    c_l, c_w, c_h = 1200.0, 235.0, 270.0
    per_axis_frac = [0.20, 0.50, 0.50]

    # Y dimension = 100 cm fits within 0.50 cap (117.5 cm)
    assert _fits_bounds(
        [200.0, 100.0, 40.0], [200.0, 100.0, 40.0],
        c_l, c_w, c_h, per_axis_frac,
        [100.0, 50.0, 40.0], [100.0, 50.0, 40.0]
    ) is True

    # But with uniform 0.20 cap, Y cap would be 47.0 cm, so 100.0 cm fails
    uniform_frac = [0.20, 0.20, 0.20]
    assert _fits_bounds(
        [200.0, 100.0, 40.0], [200.0, 100.0, 40.0],
        c_l, c_w, c_h, uniform_frac,
        [100.0, 50.0, 40.0], [100.0, 50.0, 40.0]
    ) is False

    # Backwards compatibility: passing a single float
    assert _fits_bounds(
        [200.0, 100.0, 40.0], [200.0, 100.0, 40.0],
        c_l, c_w, c_h, 0.20,
        [100.0, 50.0, 40.0], [100.0, 50.0, 40.0]
    ) is False


def test_relaxed_layer_merging():
    """Verify that columns merge further along relaxed axes (e.g. Z axis up to 0.50) into multi-layer blocks."""
    boxes = create_test_boxes(8, length=100, width=50, height=40)
    blocks, leftover = build_blocks(boxes, 1200.0, 235.0, 270.0)

    assert len(leftover) == 0
    # At least one block has grown along the height (Z) axis to > 40 cm
    assert any(b.height_cm > 40.0 for b in blocks)
    assert sum(len(b.contents) for b in blocks) == 8