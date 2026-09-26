"""
Tests for:
  - geometry.project_point_down  (downward gravity projection)
  - geometry.generate_extreme_points  (no floating anchor points)
  - output.build_layers  (X-axis longitudinal slicing, rear->door ordering)
"""
import pytest
from datetime import datetime
from app.solver.geometry import (
    BoundingBox,
    Dimensions,
    ExtremePoint,
    Position,
    Posture,
    generate_extreme_points,
    project_point_down,
)
from app.solver.output import build_layers
from app.core.models import PlacedBox


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_bbox(min_x, min_y, min_z, max_x, max_y, max_z) -> BoundingBox:
    return BoundingBox(min_x=min_x, min_y=min_y, min_z=min_z,
                       max_x=max_x, max_y=max_y, max_z=max_z)


def make_placed_box(
    box_id, x, y, z, length, width, height, customer_sequence=1
) -> PlacedBox:
    return PlacedBox(
        box_id=box_id,
        item_id="ITEM-TEST",
        po_no="PO-TEST",
        customer_code=None,
        customer_sequence=customer_sequence,
        length_cm=length,
        width_cm=width,
        height_cm=height,
        weight_kg=10.0,
        this_way_up=True,
        permitted_postures=[Posture.LWH],
        inflated_length=length,
        inflated_width=width,
        inflated_height=height,
        x=x, y=y, z=z,
        posture=Posture.LWH,
        actual_length=length,
        actual_width=width,
        actual_height=height,
    )


CONTAINER = Dimensions(length=1200.0, width=240.0, height=270.0)


# ---------------------------------------------------------------------------
# project_point_down
# ---------------------------------------------------------------------------

class TestProjectPointDown:
    def test_already_at_floor_is_unchanged(self):
        """A point at z=0 should stay at z=0 (already on the floor)."""
        pt = ExtremePoint(100.0, 50.0, 0.0)
        result = project_point_down(pt, [], CONTAINER)
        assert result.z == pytest.approx(0.0)
        assert result.x == pytest.approx(100.0)
        assert result.y == pytest.approx(50.0)

    def test_point_on_top_face_of_box_is_unchanged(self):
        """A point resting exactly on a placed box's top face should be kept."""
        box = make_bbox(0, 0, 0, 200, 100, 50)
        pt = ExtremePoint(50.0, 50.0, 50.0)  # exactly on box.max_z
        result = project_point_down(pt, [box], CONTAINER)
        assert result.z == pytest.approx(50.0)

    def test_floating_point_above_single_box_projects_to_top(self):
        """A point floating above a box (no direct support) should project to box top."""
        box = make_bbox(0, 0, 0, 200, 100, 50)   # box top at z=50
        pt = ExtremePoint(50.0, 50.0, 80.0)       # floating at z=80, above (50,50)
        result = project_point_down(pt, [box], CONTAINER)
        assert result.z == pytest.approx(50.0)

    def test_floating_point_no_box_below_projects_to_floor(self):
        """A point with no box below it should project to the floor (z=0)."""
        box = make_bbox(500, 0, 0, 700, 100, 50)  # box somewhere else
        pt = ExtremePoint(100.0, 50.0, 80.0)       # no box covers (100, 50)
        result = project_point_down(pt, [box], CONTAINER)
        assert result.z == pytest.approx(0.0)

    def test_stacked_boxes_projects_to_highest_top(self):
        """When two boxes cover (x,y), point should land on the higher one's top."""
        lower = make_bbox(0, 0, 0, 200, 100, 30)   # top at z=30
        upper = make_bbox(0, 0, 30, 200, 100, 80)  # top at z=80
        pt = ExtremePoint(100.0, 50.0, 120.0)
        result = project_point_down(pt, [lower, upper], CONTAINER)
        assert result.z == pytest.approx(80.0)

    def test_partial_overlap_picks_correct_supporting_box(self):
        """Only boxes whose XY footprint covers the point count as support."""
        covering = make_bbox(0, 0, 0, 200, 100, 60)        # covers (50, 50)
        not_covering = make_bbox(300, 0, 0, 500, 100, 90)  # does NOT cover (50, 50)
        pt = ExtremePoint(50.0, 50.0, 100.0)
        result = project_point_down(pt, [covering, not_covering], CONTAINER)
        # Lands on covering box (top=60), NOT the taller non-covering box
        assert result.z == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# generate_extreme_points -- no floating anchors
# ---------------------------------------------------------------------------

class TestGenerateExtremePointsNoFloat:
    def test_origin_always_present(self):
        """The floor-origin (0,0,0) must always appear in the result."""
        pts = generate_extreme_points([], CONTAINER)
        assert any(abs(p.x) < 1e-6 and abs(p.y) < 1e-6 and abs(p.z) < 1e-6 for p in pts)

    def test_no_floating_points_single_box(self):
        """Points generated from a floor-resting box must not float."""
        box = make_bbox(0, 0, 0, 200, 100, 50)
        pts = generate_extreme_points([box], CONTAINER)
        for p in pts:
            if p.z > 1e-6:
                # Must land on a box's top face
                on_top = any(
                    abs(b.max_z - p.z) < 1e-6
                    and b.min_x <= p.x <= b.max_x
                    and b.min_y <= p.y <= b.max_y
                    for b in [box]
                )
                assert on_top, f"Point {p} is floating (z={p.z}) without box top support"

    def test_staggered_boxes_no_floating_points(self):
        """With staggered boxes, extreme points beside upper boxes project down."""
        lower = make_bbox(0, 0, 0, 100, 100, 40)
        upper = make_bbox(0, 0, 40, 80, 100, 80)
        placed = [lower, upper]
        pts = generate_extreme_points(placed, CONTAINER)
        for p in pts:
            if p.z > 1e-6:
                supported = any(
                    abs(b.max_z - p.z) < 1e-6
                    and b.min_x <= p.x <= b.max_x
                    and b.min_y <= p.y <= b.max_y
                    for b in placed
                )
                assert supported, f"Floating extreme point detected: {p}"


# ---------------------------------------------------------------------------
# build_layers -- X-axis slicing, rear->door ordering
# ---------------------------------------------------------------------------

class TestBuildLayersXAxis:
    def test_empty_returns_empty(self):
        assert build_layers([]) == []

    def test_single_box_produces_at_least_one_layer(self):
        box = make_placed_box("B1", x=100, y=0, z=0, length=50, width=50, height=50)
        layers = build_layers([box], layer_depth=50)
        assert len(layers) >= 1
        all_boxes = [b for layer in layers for b in layer.boxes]
        assert any(b.box_id == "B1" for b in all_boxes)

    def test_layer_0_is_deepest_rear_wall(self):
        """Layer 0 must contain boxes nearest the rear wall (highest X values)."""
        rear_box = make_placed_box("REAR", x=900, y=0, z=0, length=100, width=100, height=100)
        door_box = make_placed_box("DOOR", x=10,  y=0, z=0, length=100, width=100, height=100)
        layers = build_layers([rear_box, door_box], layer_depth=50)
        rear_ids = {b.box_id for b in layers[0].boxes}
        last_ids = {b.box_id for b in layers[-1].boxes}
        assert "REAR" in rear_ids, "Rear-wall box must be in Layer 0 (deepest layer)"
        assert "DOOR" in last_ids, "Door-facing box must be in the last layer"

    def test_x_min_x_max_attributes_present(self):
        """Layers must expose x_min and x_max attributes."""
        box = make_placed_box("B1", x=0, y=0, z=0, length=100, width=100, height=100)
        layers = build_layers([box], layer_depth=50)
        for layer in layers:
            assert hasattr(layer, "x_min"), "Layer must have x_min attribute"
            assert hasattr(layer, "x_max"), "Layer must have x_max attribute"
            assert not hasattr(layer, "z_min"), "Layer must NOT have z_min attribute"
            assert not hasattr(layer, "z_max"), "Layer must NOT have z_max attribute"

    def test_layer_x_bands_are_ordered_rear_to_door(self):
        """Layers must be ordered rear->door (descending x_max)."""
        boxes = [
            make_placed_box("B1", x=0,   y=0, z=0, length=50, width=50, height=50),
            make_placed_box("B2", x=200, y=0, z=0, length=50, width=50, height=50),
            make_placed_box("B3", x=500, y=0, z=0, length=50, width=50, height=50),
        ]
        layers = build_layers(boxes, layer_depth=50)
        for i in range(len(layers) - 1):
            assert layers[i].x_max >= layers[i + 1].x_max, (
                f"Layer {i} x_max={layers[i].x_max} < layer {i+1} x_max={layers[i+1].x_max}"
            )

    def test_box_assigned_to_correct_depth_band(self):
        """A box at x=500..550 must appear in a layer whose band covers [500, 550]."""
        box = make_placed_box("MID", x=500, y=0, z=0, length=50, width=50, height=50)
        layers = build_layers([box], layer_depth=50)
        matching = [l for l in layers if any(b.box_id == "MID" for b in l.boxes)]
        assert len(matching) >= 1
        layer = matching[0]
        # Box x-interval [500, 550] must overlap layer band
        assert layer.x_min <= 550 and layer.x_max >= 500

    def test_serialization_uses_x_keys_not_z_keys(self):
        """Serialized layer dicts must have x_min/x_max, not z_min/z_max."""
        box = make_placed_box("B1", x=0, y=0, z=0, length=100, width=100, height=100)
        layers = build_layers([box], layer_depth=50)
        serialized = [
            {"x_min": layer.x_min, "x_max": layer.x_max,
             "boxes": [b.box_id for b in layer.boxes]}
            for layer in layers
        ]
        for entry in serialized:
            assert "x_min" in entry and "x_max" in entry
            assert "z_min" not in entry and "z_max" not in entry
