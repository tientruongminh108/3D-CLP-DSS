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
            stacking_group=1,
            max_load_bearing_kg=100,
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