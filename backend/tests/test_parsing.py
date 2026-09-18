import pytest
import pandas as pd
from app.solver.parsing import parse_and_join, parse_container_spec, parse_item_master, detect_shipment_type
from app.solver.sorting import initial_sort
from app.core.models import PackingListRow, ShipmentType


def test_parse_container_spec():
    df = pd.DataFrame([{
        "Container_Type": "40HC",
        "Internal_Length_cm": 1203.2,
        "Internal_Width_cm": 235.2,
        "Internal_Height_cm": 270.0,
        "Max_Weight_kg": 28000,
    }])
    spec = parse_container_spec(df)
    assert spec.container_type == "40HC"
    assert spec.internal_length_cm == 1203.2
    assert spec.usable_length == 1203.2 - 4.0  # 2 * 2.0 gap


def test_parse_item_master():
    df = pd.DataFrame([{
        "Item_ID": "DT-8411",
        "Description": "Dining Table",
        "Length_cm": 110,
        "Width_cm": 70,
        "Height_cm": 15,
        "Weight_kg": 45.5,
        "This_Way_Up": True,
        "Stacking_Group": 1,
        "Max_Load_Bearing_kg": 200,
    }])
    items = parse_item_master(df)
    assert "DT-8411" in items
    item = items["DT-8411"]
    assert item.length_cm == 110
    assert item.this_way_up is True
    assert item.stacking_group == 1


def test_detect_shipment_type_fcl():
    rows = [
        PackingListRow(item_id="DT-8411", po_no="PO-1", customer_code=None, description="", qty_pcs=1, qty_cartons=1),
        PackingListRow(item_id="DT-8411", po_no="PO-1", customer_code=None, description="", qty_pcs=1, qty_cartons=1),
    ]
    stype, count, seq = detect_shipment_type(rows)
    assert stype == ShipmentType.FCL
    assert count == 0


def test_detect_shipment_type_lcl():
    rows = [
        PackingListRow(item_id="DT-8411", po_no="PO-1", customer_code="CUST-A", description="", qty_pcs=1, qty_cartons=1),
        PackingListRow(item_id="DT-8411", po_no="PO-2", customer_code="CUST-B", description="", qty_pcs=1, qty_cartons=1),
        PackingListRow(item_id="DT-8411", po_no="PO-3", customer_code="CUST-C", description="", qty_pcs=1, qty_cartons=1),
    ]
    stype, count, seq = detect_shipment_type(rows)
    assert stype == ShipmentType.LCL
    assert count == 3
    assert seq["CUST-A"] == 1
    assert seq["CUST-B"] == 2
    assert seq["CUST-C"] == 3


def test_initial_sort_fcl():
    from app.solver.parsing import Box
    from app.solver.geometry import Posture

    boxes = [
        Box(
            box_id="A_1", item_id="A", po_no="PO-1", customer_code=None, customer_sequence=0,
            length_cm=100, width_cm=50, height_cm=40, weight_kg=20,
            this_way_up=True, stacking_group=1, max_load_bearing_kg=100,
            permitted_postures=[Posture.LWH, Posture.WLH],
            inflated_length=102, inflated_width=52, inflated_height=40,
        ),
        Box(
            box_id="B_1", item_id="B", po_no="PO-1", customer_code=None, customer_sequence=0,
            length_cm=80, width_cm=60, height_cm=50, weight_kg=30,
            this_way_up=True, stacking_group=2, max_load_bearing_kg=50,
            permitted_postures=[Posture.LWH, Posture.WLH],
            inflated_length=82, inflated_width=62, inflated_height=50,
        ),
        Box(
            box_id="C_1", item_id="C", po_no="PO-1", customer_code=None, customer_sequence=0,
            length_cm=120, width_cm=40, height_cm=30, weight_kg=15,
            this_way_up=False, stacking_group=1, max_load_bearing_kg=100,
            permitted_postures=list(Posture),
            inflated_length=122, inflated_width=42, inflated_height=30,
        ),
    ]

    sorted_boxes = initial_sort(boxes, "FCL")
    # stacking_group 1 (sturdy) comes first, then by volume desc, then weight desc
    assert sorted_boxes[0].box_id == "A_1"  # stacking_group=1, volume=200000
    assert sorted_boxes[1].box_id == "C_1"  # stacking_group=1, volume=144000
    assert sorted_boxes[2].box_id == "B_1"  # stacking_group=2


def test_initial_sort_lcl():
    from app.solver.parsing import Box
    from app.solver.geometry import Posture

    boxes = [
        Box(
            box_id="A_1", item_id="A", po_no="PO-1", customer_code="CUST-B", customer_sequence=2,
            length_cm=100, width_cm=50, height_cm=40, weight_kg=20,
            this_way_up=True, stacking_group=1, max_load_bearing_kg=100,
            permitted_postures=[Posture.LWH, Posture.WLH],
            inflated_length=102, inflated_width=52, inflated_height=40,
        ),
        Box(
            box_id="B_1", item_id="B", po_no="PO-1", customer_code="CUST-A", customer_sequence=1,
            length_cm=80, width_cm=60, height_cm=50, weight_kg=30,
            this_way_up=True, stacking_group=2, max_load_bearing_kg=50,
            permitted_postures=[Posture.LWH, Posture.WLH],
            inflated_length=82, inflated_width=62, inflated_height=50,
        ),
    ]

    sorted_boxes = initial_sort(boxes, "LCL")
    assert sorted_boxes[0].customer_sequence == 1  # CUST-A first
    assert sorted_boxes[1].customer_sequence == 2  # CUST-B second


# ---------------------------------------------------------------------------
# Issue 3 — Dimension validation in expand_packing_list
# ---------------------------------------------------------------------------

def _make_container_spec(length=1200, width=235, height=270):
    """Helper: build a minimal ContainerSpec for tests."""
    import pandas as pd
    from app.solver.parsing import parse_container_spec
    df = pd.DataFrame([{
        "Container_Type": "40HC",
        "Internal_Length_cm": float(length),
        "Internal_Width_cm": float(width),
        "Internal_Height_cm": float(height),
        "Max_Weight_kg": 28000,
    }])
    return parse_container_spec(df)


def _make_item(length, width, height, this_way_up=False):
    """Helper: build a minimal ItemBase dict for parse_item_master."""
    import pandas as pd
    from app.solver.parsing import parse_item_master
    df = pd.DataFrame([{
        "Item_ID": "TST-001",
        "Description": "Test item",
        "Length_cm": float(length),
        "Width_cm": float(width),
        "Height_cm": float(height),
        "Weight_kg": 10.0,
        "This_Way_Up": this_way_up,
        "Stacking_Group": 1,
        "Max_Load_Bearing_kg": 100.0,
    }])
    return parse_item_master(df)


def test_PRS_10_oversized_item_raises_validation_error():
    """An item that cannot fit in any orientation should raise ValidationError immediately."""
    from app.core.models import PackingListRow
    from app.solver.parsing import expand_packing_list
    from app.core.exceptions import ValidationError

    # Container: 1200 x 235 x 270 cm. Item: 1500 x 100 x 100 cm — too long in every rotation.
    container = _make_container_spec(1200, 235, 270)
    items = _make_item(1500, 100, 100, this_way_up=False)  # all rotations allowed

    packing_rows = [
        PackingListRow(item_id="TST-001", po_no="PO-1", customer_code=None,
                       description="", qty_pcs=1, qty_cartons=1),
    ]

    with pytest.raises(ValidationError, match="does not fit inside the container"):
        expand_packing_list(packing_rows, items, container, {}, tolerance_gap=2.0)


def test_PRS_11_normally_sized_item_passes_validation():
    """An item that fits in at least one orientation should not raise."""
    from app.core.models import PackingListRow
    from app.solver.parsing import expand_packing_list

    container = _make_container_spec(1200, 235, 270)
    items = _make_item(100, 80, 60, this_way_up=False)

    packing_rows = [
        PackingListRow(item_id="TST-001", po_no="PO-1", customer_code=None,
                       description="", qty_pcs=1, qty_cartons=1),
    ]

    boxes, _ = expand_packing_list(packing_rows, items, container, {}, tolerance_gap=2.0)
    assert len(boxes) == 1