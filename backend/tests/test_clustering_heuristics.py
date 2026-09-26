import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.solver.parsing import Box
from app.solver.block_generation import Block
from app.solver.geometry import Dimensions, Position, BoundingBox, Posture, ExtremePoint
from app.solver.sorting import initial_sort, resort_after_blocks
from app.solver.utils import get_unit_item_id
from app.solver.placement import corner_points_for, find_best_placement


def make_box(box_id, item_id, l, w, h, wt=10.0, cust="CUST1", seq=1):
    return Box(
        box_id=box_id,
        item_id=item_id,
        po_no="PO1",
        customer_code=cust,
        customer_sequence=seq,
        length_cm=l,
        width_cm=w,
        height_cm=h,
        weight_kg=wt,
        this_way_up=False,
        permitted_postures=[Posture.LWH, Posture.WLH],
        inflated_length=l,
        inflated_width=w,
        inflated_height=h,
    )


class TestClusteringHeuristics(unittest.TestCase):
    def test_sorting_groups_same_item_together(self):
        box_a1 = make_box("b1", "ITEM_A", 50, 40, 30)
        box_a2 = make_box("b2", "ITEM_A", 50, 40, 30)
        block_a = Block("B_A", [box_a1, box_a2], 100, 40, 30, 20, 1, 100, 40, 30, [box_a1, box_a2])
        leftover_a = make_box("b3", "ITEM_A", 50, 40, 30)

        box_b1 = make_box("b4", "ITEM_B", 40, 30, 20)
        box_b2 = make_box("b5", "ITEM_B", 40, 30, 20)
        block_b = Block("B_B", [box_b1, box_b2], 80, 30, 20, 10, 1, 80, 30, 20, [box_b1, box_b2])
        leftover_b = make_box("b6", "ITEM_B", 40, 30, 20)

        # Unsorted mixture
        units = [leftover_a, block_b, leftover_b, block_a]
        sorted_units = resort_after_blocks(units, "FCL")

        item_sequence = [get_unit_item_id(u) for u in sorted_units]
        print("\nFCL sorted item sequence:", item_sequence)

        # All ITEM_A units should be consecutive, and all ITEM_B units should be consecutive
        self.assertEqual(item_sequence[:2], ["ITEM_A", "ITEM_A"])
        self.assertEqual(item_sequence[2:], ["ITEM_B", "ITEM_B"])

        # Within ITEM_A, the larger block should come before the leftover box
        self.assertEqual(sorted_units[0].block_id, "B_A")
        self.assertEqual(sorted_units[1].box_id, "b3")

    def test_corner_points_no_door_corners(self):
        box = make_box("b1", "ITEM_A", 50, 40, 30)
        dims = Dimensions(50, 40, 30)
        c_dims = Dimensions(1200, 240, 260)

        corners = corner_points_for(box, dims, c_dims, "FCL", 1)
        print("\nGenerated corners:", [(c.x, c.y, c.z) for c in corners])

        # All generated corners must have x > 0 (strictly rear-wall anchors)
        for c in corners:
            self.assertGreater(c.x, 0.0, "Corner should not be placed at the door (x=0) early!")
            self.assertAlmostEqual(c.x, 1200 - 50, delta=1e-4)

    def test_same_item_affinity_bonus(self):
        c_dims = Dimensions(1200, 240, 260)
        placed_box_a = BoundingBox(1150, 0, 0, 1200, 40, 30)
        placed_data_a = make_box("b1", "ITEM_A", 50, 40, 30)

        # Candidate 1: same item (ITEM_A) placed adjacent along Y (y=40..80) vs placed far away (y=150..190)
        cand_box_a = make_box("b2", "ITEM_A", 50, 40, 30)

        # EP adjacent to placed box (x=1150, y=40, z=0)
        ep_adjacent = ExtremePoint(1150, 40, 0)
        # EP far away from placed box (x=1150, y=150, z=0)
        ep_far = ExtremePoint(1150, 150, 0)

        res_adj, _ = find_best_placement(cand_box_a, [placed_box_a], [placed_data_a], c_dims, 10, 1000, False, [ep_adjacent])
        res_far, _ = find_best_placement(cand_box_a, [placed_box_a], [placed_data_a], c_dims, 10, 1000, False, [ep_far])

        self.assertIsNotNone(res_adj)
        self.assertIsNotNone(res_far)
        print(f"\nScore adjacent to same item: {res_adj.score:.4f}, Score far away: {res_far.score:.4f}")
        self.assertGreater(res_adj.score, res_far.score, "Placement adjacent to same-item box should receive higher score!")


if __name__ == "__main__":
    unittest.main()
