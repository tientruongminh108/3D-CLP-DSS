import pytest
from app.solver.geometry import Dimensions, BoundingBox, Position, Posture
from app.solver.parsing import Box
from app.solver.compaction import (
    compact_x_rear,
    compact_y_sidewall,
    rescan_and_insert,
    run_compaction_pass,
)


def make_box(box_id, length, width, height, weight=10.0, cust_seq=0, permitted_postures=None):
    postures = permitted_postures or [Posture.LWH]
    return Box(
        box_id=box_id,
        item_id=f"ITEM-{box_id}",
        po_no="PO-1",
        customer_code=f"CUST-{cust_seq}",
        customer_sequence=cust_seq,
        length_cm=length,
        width_cm=width,
        height_cm=height,
        weight_kg=weight,
        this_way_up=True,
        permitted_postures=postures,
        inflated_length=length,
        inflated_width=width,
        inflated_height=height,
    )


class TestCompactionPass:
    def test_compact_x_rear_slides_to_wall(self):
        """Single box should slide flush against container rear wall (max_x = container length)."""
        c_dims = Dimensions(length=100.0, width=50.0, height=50.0)
        box = make_box("B1", length=20.0, width=10.0, height=10.0)
        bbox = BoundingBox(10.0, 5.0, 0.0, 30.0, 15.0, 10.0)

        compacted = compact_x_rear([bbox], [box], c_dims, is_lcl=False)
        assert len(compacted) == 1
        assert compacted[0].max_x == pytest.approx(100.0)
        assert compacted[0].min_x == pytest.approx(80.0)
        assert compacted[0].min_y == pytest.approx(5.0)

    def test_compact_x_rear_respects_blocking_neighbor(self):
        """Rear-most box slides to wall, front-most box slides flush against rear-most box."""
        c_dims = Dimensions(length=100.0, width=50.0, height=50.0)
        box_rear = make_box("B_REAR", length=20.0, width=20.0, height=20.0)
        box_front = make_box("B_FRONT", length=20.0, width=20.0, height=20.0)

        bbox_rear = BoundingBox(50.0, 10.0, 0.0, 70.0, 30.0, 20.0)
        bbox_front = BoundingBox(10.0, 10.0, 0.0, 30.0, 30.0, 20.0)

        compacted = compact_x_rear([bbox_rear, bbox_front], [box_rear, box_front], c_dims, is_lcl=False)

        # B_REAR should slide to rear wall: [80, 100]
        # B_FRONT should slide to B_REAR's new min_x: [60, 80]
        assert compacted[0].min_x == pytest.approx(80.0)
        assert compacted[0].max_x == pytest.approx(100.0)
        assert compacted[1].min_x == pytest.approx(60.0)
        assert compacted[1].max_x == pytest.approx(80.0)
        assert not compacted[0].overlaps(compacted[1])

    def test_compact_y_sidewall_slides_to_left(self):
        """Boxes should slide toward min-y (0.0) without collision."""
        c_dims = Dimensions(length=100.0, width=50.0, height=50.0)
        b1 = make_box("B1", length=30.0, width=15.0, height=20.0)
        b2 = make_box("B2", length=30.0, width=15.0, height=20.0)

        bbox1 = BoundingBox(50.0, 10.0, 0.0, 80.0, 25.0, 20.0)
        bbox2 = BoundingBox(50.0, 30.0, 0.0, 80.0, 45.0, 20.0)

        compacted = compact_y_sidewall([bbox1, bbox2], [b1, b2], c_dims, is_lcl=False)

        # bbox1 was already to the left of bbox2, so it slides to y=0: [0, 15]
        # bbox2 slides flush against bbox1: [15, 30]
        assert compacted[0].min_y == pytest.approx(0.0)
        assert compacted[0].max_y == pytest.approx(15.0)
        assert compacted[1].min_y == pytest.approx(15.0)
        assert compacted[1].max_y == pytest.approx(30.0)
        assert not compacted[0].overlaps(compacted[1])

    def test_compact_lcl_customer_sequence_preserved(self):
        """In LCL mode, earlier customer cargo must not slide deeper than later customer cargo."""
        c_dims = Dimensions(length=100.0, width=50.0, height=50.0)
        # B_EARLY belongs to customer 1 (near door)
        # B_DEEP belongs to customer 2 (near rear)
        b_early = make_box("B_EARLY", length=20.0, width=10.0, height=10.0, cust_seq=1)
        b_deep = make_box("B_DEEP", length=20.0, width=10.0, height=10.0, cust_seq=2)

        # Placed at different Y coordinates so geometrically they don't overlap in Y
        bbox_early = BoundingBox(10.0, 0.0, 0.0, 30.0, 10.0, 10.0)
        bbox_deep = BoundingBox(60.0, 30.0, 0.0, 80.0, 40.0, 10.0)

        compacted = compact_x_rear([bbox_early, bbox_deep], [b_early, b_deep], c_dims, is_lcl=True)

        # B_DEEP (cust 2) slides to rear wall [80, 100]
        # B_EARLY (cust 1) must not slide beyond min_x of B_DEEP (80)
        assert compacted[1].max_x == pytest.approx(100.0)
        assert compacted[0].max_x <= compacted[1].min_x + 1e-6

    def test_rescan_and_insert_recovers_unplaced_item(self):
        """Compaction opens space near door, allowing previously unplaced item to fit."""
        c_dims = Dimensions(length=60.0, width=20.0, height=20.0)
        # Container has length 60. Box 1 has length 40, originally placed at [10, 50].
        # Box 2 has length 20. It couldn't fit when Box 1 was at [10, 50] (only 10cm space before and after).
        b1 = make_box("B1", length=40.0, width=20.0, height=20.0)
        b2 = make_box("B2", length=20.0, width=20.0, height=20.0)

        bbox1 = BoundingBox(10.0, 0.0, 0.0, 50.0, 20.0, 20.0)

        placed_bboxes = [bbox1]
        placed_data = [b1]
        placed_postures = [Posture.LWH]
        unplaced = [(b2, "no_space")]

        # Run complete compaction pass
        new_bboxes, new_data, new_postures, new_unplaced, new_weight, fr = run_compaction_pass(
            placed_bboxes=placed_bboxes,
            placed_data=placed_data,
            placed_postures=placed_postures,
            unplaced=unplaced,
            container_dims=c_dims,
            max_weight=1000.0,
            is_lcl=False,
            current_weight=10.0,
        )

        # Box 1 slid to [20, 60], exposing [0, 20] space
        # Box 2 (length 20) should now be placed into [0, 20]!
        assert len(new_bboxes) == 2
        assert len(new_data) == 2
        assert len(new_unplaced) == 0
        assert not new_bboxes[0].overlaps(new_bboxes[1])

    def test_compact_preserves_vertical_support(self):
        """Compaction must never slide an elevated box into thin air when its support is blocked."""
        c_dims = Dimensions(length=100.0, width=20.0, height=50.0)
        # B_FLOOR is at [0, 40], z=0. Blocked by B_BLOCK at [40, 60], z=0.
        # B_TOP rests on B_FLOOR at [0, 40], z=[20, 40].
        # In upper space (z >= 20), space is open up to x=100.
        # Compaction must NOT slide B_TOP past B_FLOOR into thin air!
        b_floor = make_box("B_FLOOR", length=40.0, width=20.0, height=20.0)
        b_block = make_box("B_BLOCK", length=20.0, width=20.0, height=20.0)
        b_top = make_box("B_TOP", length=40.0, width=20.0, height=20.0)

        bbox_floor = BoundingBox(0.0, 0.0, 0.0, 40.0, 20.0, 20.0)
        bbox_block = BoundingBox(40.0, 0.0, 0.0, 60.0, 20.0, 20.0)
        bbox_top = BoundingBox(0.0, 0.0, 20.0, 40.0, 20.0, 40.0)

        compacted = compact_x_rear(
            [bbox_floor, bbox_block, bbox_top],
            [b_floor, b_block, b_top],
            c_dims,
            is_lcl=False,
            min_support_ratio=0.60,
        )

        # B_BLOCK slides to rear wall [80, 100]
        # B_FLOOR slides flush against B_BLOCK: [40, 80]
        # B_TOP can only slide as far as it remains supported by B_FLOOR
        # Under no circumstance should B_TOP be in the air (unsupported)
        from app.solver.geometry import check_support_ratio
        top_box = next(b for b in compacted if b.min_z == 20.0)
        assert check_support_ratio(top_box, compacted, 0.60)

