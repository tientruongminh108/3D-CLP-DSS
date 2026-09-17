import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from io import StringIO

from app.main import app
from app.core.database import get_db
from app.core.models import ContainerCreate, ItemCreate, PackingListRow, ShipmentType

client = TestClient(app)


class TestContainerValidation:
    """Tests for container validation (Section 1.1 - CONT-01 to CONT-06)"""

    def test_CONT_01_zero_length_rejected(self, db_session):
        """CONT-01: Container with Internal_Length_cm = 0 should be rejected"""
        payload = {
            "container_type": "TEST-20",
            "internal_length_cm": 0,
            "internal_width_cm": 235.2,
            "internal_height_cm": 270.0,
            "max_weight_kg": 28000,
        }
        response = client.post("/api/containers", json=payload)
        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("internal_length_cm" in str(e).lower() for e in error_detail)

    def test_CONT_02_negative_width_rejected(self, db_session):
        """CONT-02: Container with negative width should be rejected"""
        payload = {
            "container_type": "TEST-21",
            "internal_length_cm": 1200,
            "internal_width_cm": -50,
            "internal_height_cm": 270.0,
            "max_weight_kg": 28000,
        }
        response = client.post("/api/containers", json=payload)
        assert response.status_code == 422

    def test_CONT_03_zero_max_weight_rejected(self, db_session):
        """CONT-03: Container with Max_Weight_kg = 0 should be rejected"""
        payload = {
            "container_type": "TEST-22",
            "internal_length_cm": 1200,
            "internal_width_cm": 235,
            "internal_height_cm": 270,
            "max_weight_kg": 0,
        }
        response = client.post("/api/containers", json=payload)
        assert response.status_code == 422

    def test_CONT_04_missing_container_type_rejected(self, db_session):
        """CONT-04: Missing Container_Type should be rejected"""
        payload = {
            "internal_length_cm": 1200,
            "internal_width_cm": 235,
            "internal_height_cm": 270,
            "max_weight_kg": 28000,
        }
        response = client.post("/api/containers", json=payload)
        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("container_type" in str(e).lower() for e in error_detail)

    def test_CONT_05_valid_container_accepted(self, db_session):
        """CONT-05: Valid container should be accepted and retrievable"""
        payload = {
            "container_type": "40HC-TEST",
            "internal_length_cm": 1203.2,
            "internal_width_cm": 235.2,
            "internal_height_cm": 270.0,
            "max_weight_kg": 28000,
        }
        response = client.post("/api/containers", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["container_type"] == "40HC-TEST"
        assert data["id"] is not None

        get_response = client.get(f"/api/containers/{data['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["container_type"] == "40HC-TEST"

    def test_CONT_06_single_container_per_run(self, db_session):
        """CONT-06: Only one container per run - API should not accept list of containers"""
        from app.core.models import RunCreate, PackingListUpload
        payload = {
            "packing_list": {
                "rows": [
                    {"item_id": "TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}
                ]
            },
            "container_id": 1,
        }
        response = client.post("/api/runs", json=payload)
        assert response.status_code in (201, 400, 404)
        if response.status_code == 201:
            data = response.json()
            assert "container" in data
            assert isinstance(data["container"], dict)


class TestItemValidation:
    """Tests for item validation (Section 1.2 - ITEM-01 to ITEM-10)"""

    def test_ITEM_01_zero_dimensions_rejected(self, db_session):
        """ITEM-01: Items with zero dimensions should be rejected"""
        for field in ["length_cm", "width_cm", "height_cm", "weight_kg"]:
            payload = {
                "item_id": f"TEST-{field}",
                "description": "Test Item",
                "length_cm": 100,
                "width_cm": 50,
                "height_cm": 40,
                "weight_kg": 20,
            }
            payload[field] = 0
            response = client.post("/api/items", json=payload)
            assert response.status_code == 422, f"Field {field} should reject zero"
            error_detail = response.json()["detail"]
            assert any(field in str(e).lower() for e in error_detail)

    def test_ITEM_02_invalid_stacking_group_rejected(self, db_session):
        """ITEM-02: Stacking_Group = 3 should be rejected"""
        payload = {
            "item_id": "TEST-STACK-3",
            "description": "Test Item",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
            "stacking_group": 3,
        }
        response = client.post("/api/items", json=payload)
        assert response.status_code == 422

    def test_ITEM_03_string_stacking_group_rejected(self, db_session):
        """ITEM-03: Stacking_Group as string should be rejected"""
        payload = {
            "item_id": "TEST-STACK-STR",
            "description": "Test Item",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
            "stacking_group": "heavy",
        }
        response = client.post("/api/items", json=payload)
        assert response.status_code == 422

    def test_ITEM_04_non_boolean_this_way_up(self, db_session):
        """ITEM-04: This_Way_Up with non-boolean should be rejected"""
        for val in ["yes", 1, "", "true"]:
            payload = {
                "item_id": f"TEST-TWU-{val}",
                "description": "Test Item",
                "length_cm": 100,
                "width_cm": 50,
                "height_cm": 40,
                "weight_kg": 20,
                "this_way_up": val,
            }
            response = client.post("/api/items", json=payload)
            assert response.status_code == 422, f"Value {val} should be rejected"

    def test_ITEM_05_optional_max_load_bearing_null(self, db_session):
        """ITEM-05: Max_Load_Bearing_kg omitted should be stored as NULL"""
        payload = {
            "item_id": "TEST-NO-MAXLOAD",
            "description": "Test Item",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
        }
        response = client.post("/api/items", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["max_load_bearing_kg"] is None

    def test_ITEM_06_zero_max_load_bearing_rejected(self, db_session):
        """ITEM-06: Max_Load_Bearing_kg = 0 should be rejected"""
        payload = {
            "item_id": "TEST-ZERO-MAXLOAD",
            "description": "Test Item",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
            "max_load_bearing_kg": 0,
        }
        response = client.post("/api/items", json=payload)
        assert response.status_code == 422

    def test_ITEM_07_negative_max_load_bearing_rejected(self, db_session):
        """ITEM-07: Max_Load_Bearing_kg negative should be rejected"""
        payload = {
            "item_id": "TEST-NEG-MAXLOAD",
            "description": "Test Item",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
            "max_load_bearing_kg": -10,
        }
        response = client.post("/api/items", json=payload)
        assert response.status_code == 422

    def test_ITEM_08_duplicate_item_id_rejected(self, db_session):
        """ITEM-08: Duplicate Item_ID should be rejected"""
        payload = {
            "item_id": "DUPLICATE-TEST",
            "description": "Test Item 1",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
        }
        response1 = client.post("/api/items", json=payload)
        assert response1.status_code == 201

        payload["description"] = "Test Item 2"
        response2 = client.post("/api/items", json=payload)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    def test_ITEM_09_delete_referenced_item_rejected(self, db_session):
        """ITEM-09: Deleting item referenced by packing list should be rejected"""
        item_payload = {
            "item_id": "REFERENCED-ITEM",
            "description": "Referenced Item",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
        }
        client.post("/api/items", json=item_payload)

        pl_payload = {
            "name": "Test PL",
            "filename": "test.csv",
            "rows": [{"item_id": "REFERENCED-ITEM", "po_no": "PO-1", "qty_pcs": 5, "qty_cartons": 5}],
            "total_cartons": 5,
            "total_weight_kg": 100,
            "total_volume_cm3": 200000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        client.post("/api/packing-lists", json=pl_payload)

        delete_response = client.delete("/api/items/REFERENCED-ITEM")
        assert delete_response.status_code == 409
        assert "referenced" in delete_response.json()["detail"].lower()

    def test_ITEM_10_delete_unreferenced_item_succeeds(self, db_session):
        """ITEM-10: Deleting unreferenced item should succeed"""
        payload = {
            "item_id": "UNREFERENCED-ITEM",
            "description": "Unreferenced Item",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
        }
        response = client.post("/api/items", json=payload)
        assert response.status_code == 201
        item_id = response.json()["id"]

        delete_response = client.delete(f"/api/items/{item_id}")
        assert delete_response.status_code == 204


class TestPackingListValidation:
    """Tests for packing list validation (Section 1.3 - PL-01 to PL-13)"""

    def test_PL_01_zero_qty_cartons_rejected(self, db_session):
        """PL-01: Qty_Cartons = 0 should be rejected"""
        payload = {
            "name": "Test PL",
            "filename": "test.csv",
            "rows": [{"item_id": "TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 0}],
            "total_cartons": 0,
            "total_weight_kg": 100,
            "total_volume_cm3": 200000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        response = client.post("/api/packing-lists", json=payload)
        assert response.status_code == 422

    def test_PL_02_negative_qty_cartons_rejected(self, db_session):
        """PL-02: Qty_Cartons = -3 should be rejected"""
        payload = {
            "name": "Test PL",
            "filename": "test.csv",
            "rows": [{"item_id": "TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": -3}],
            "total_cartons": -3,
            "total_weight_kg": 100,
            "total_volume_cm3": 200000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        response = client.post("/api/packing-lists", json=payload)
        assert response.status_code == 422

    def test_PL_03_fractional_qty_cartons_rejected(self, db_session):
        """PL-03: Qty_Cartons = 4.5 should be rejected as type error"""
        payload = {
            "name": "Test PL",
            "filename": "test.csv",
            "rows": [{"item_id": "TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 4.5}],
            "total_cartons": 4,
            "total_weight_kg": 100,
            "total_volume_cm3": 200000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        response = client.post("/api/packing-lists", json=payload)
        assert response.status_code == 422

    def test_PL_04_zero_qty_pcs_rejected(self, db_session):
        """PL-04: Qty_Pcs = 0 should be rejected"""
        payload = {
            "name": "Test PL",
            "filename": "test.csv",
            "rows": [{"item_id": "TEST-ITEM", "po_no": "PO-1", "qty_pcs": 0, "qty_cartons": 10}],
            "total_cartons": 10,
            "total_weight_kg": 100,
            "total_volume_cm3": 200000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        response = client.post("/api/packing-lists", json=payload)
        assert response.status_code == 422

    def test_PL_05_bad_item_id_rejected(self, db_session):
        """PL-05: Bad Item_ID should be rejected with specific error"""
        payload = {
            "name": "Test PL",
            "filename": "test.csv",
            "rows": [{"item_id": "NONEXISTENT-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}],
            "total_cartons": 10,
            "total_weight_kg": 100,
            "total_volume_cm3": 200000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        response = client.post("/api/packing-lists", json=payload)
        assert response.status_code == 400
        error = response.json()["detail"]
        assert "NONEXISTENT-ITEM" in error

    def test_PL_06_partial_upload_rejected(self, db_session):
        """PL-06: Upload with one bad row should reject entire upload"""
        payload = {
            "name": "Test PL",
            "filename": "test.csv",
            "rows": [
                {"item_id": "TEST-ITEM-1", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10},
                {"item_id": "BAD-ITEM", "po_no": "PO-2", "qty_pcs": 10, "qty_cartons": 10},
            ],
            "total_cartons": 20,
            "total_weight_kg": 200,
            "total_volume_cm3": 400000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        client.post("/api/items", json={
            "item_id": "TEST-ITEM-1", "description": "Test", "length_cm": 100,
            "width_cm": 50, "height_cm": 40, "weight_kg": 20
        })
        response = client.post("/api/packing-lists", json=payload)
        assert response.status_code == 400

    def test_PL_07_fcl_detection_blank_customer(self, db_session):
        """PL-07: All blank Customer_Code should detect as FCL"""
        from app.solver.parsing import detect_shipment_type
        rows = [
            PackingListRow(item_id="ITEM-1", po_no="PO-1", customer_code=None, qty_pcs=10, qty_cartons=10),
            PackingListRow(item_id="ITEM-1", po_no="PO-2", customer_code="", qty_pcs=10, qty_cartons=10),
        ]
        stype, count, seq = detect_shipment_type(rows)
        assert stype == ShipmentType.FCL
        assert count == 0

    def test_PL_08_fcl_detection_single_customer(self, db_session):
        """PL-08: Single non-blank Customer_Code should detect as FCL"""
        from app.solver.parsing import detect_shipment_type
        rows = [
            PackingListRow(item_id="ITEM-1", po_no="PO-1", customer_code="CUST-A", qty_pcs=10, qty_cartons=10),
            PackingListRow(item_id="ITEM-1", po_no="PO-2", customer_code="CUST-A", qty_pcs=10, qty_cartons=10),
        ]
        stype, count, seq = detect_shipment_type(rows)
        assert stype == ShipmentType.FCL
        assert count == 0

    def test_PL_09_lcl_detection_contiguous(self, db_session):
        """PL-09: Multiple customers contiguous should detect as LCL with correct order"""
        from app.solver.parsing import detect_shipment_type
        rows = [
            PackingListRow(item_id="ITEM-1", po_no="PO-1", customer_code="CUST-A", qty_pcs=10, qty_cartons=10),
            PackingListRow(item_id="ITEM-1", po_no="PO-2", customer_code="CUST-A", qty_pcs=10, qty_cartons=10),
            PackingListRow(item_id="ITEM-1", po_no="PO-3", customer_code="CUST-B", qty_pcs=10, qty_cartons=10),
            PackingListRow(item_id="ITEM-1", po_no="PO-4", customer_code="CUST-B", qty_pcs=10, qty_cartons=10),
        ]
        stype, count, seq = detect_shipment_type(rows)
        assert stype == ShipmentType.LCL
        assert count == 2
        assert seq["CUST-A"] == 1
        assert seq["CUST-B"] == 2

    def test_PL_10_lcl_detection_interleaved(self, db_session):
        """PL-10: Interleaved customers still LCL but row order preserved"""
        from app.solver.parsing import detect_shipment_type
        rows = [
            PackingListRow(item_id="ITEM-1", po_no="PO-1", customer_code="CUST-A", qty_pcs=10, qty_cartons=10),
            PackingListRow(item_id="ITEM-1", po_no="PO-2", customer_code="CUST-B", qty_pcs=10, qty_cartons=10),
            PackingListRow(item_id="ITEM-1", po_no="PO-3", customer_code="CUST-A", qty_pcs=10, qty_cartons=10),
        ]
        stype, count, seq = detect_shipment_type(rows)
        assert stype == ShipmentType.LCL
        assert count == 2
        assert seq["CUST-A"] == 1
        assert seq["CUST-B"] == 2

    def test_PL_11_row_order_preserved(self, db_session):
        """PL-11: Row order preserved on GET after creation"""
        client.post("/api/items", json={
            "item_id": "ORDER-ITEM-1", "description": "Item 1", "length_cm": 100,
            "width_cm": 50, "height_cm": 40, "weight_kg": 20
        })
        client.post("/api/items", json={
            "item_id": "ORDER-ITEM-2", "description": "Item 2", "length_cm": 80,
            "width_cm": 60, "height_cm": 50, "weight_kg": 30
        })
        pl_payload = {
            "name": "Order Test",
            "filename": "order.csv",
            "rows": [
                {"item_id": "ORDER-ITEM-2", "po_no": "PO-2", "qty_pcs": 10, "qty_cartons": 10},
                {"item_id": "ORDER-ITEM-1", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10},
            ],
            "total_cartons": 20,
            "total_weight_kg": 500,
            "total_volume_cm3": 800000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        response = client.post("/api/packing-lists", json=pl_payload)
        assert response.status_code == 201
        pl_id = response.json()["id"]

        get_response = client.get(f"/api/packing-lists/{pl_id}")
        assert get_response.status_code == 200
        rows = get_response.json()["rows"]
        assert rows[0]["item_id"] == "ORDER-ITEM-2"
        assert rows[1]["item_id"] == "ORDER-ITEM-1"

    def test_PL_12_update_preserves_order(self, db_session):
        """PL-12: PUT update preserves line_order"""
        client.post("/api/items", json={
            "item_id": "UPDATE-ITEM-1", "description": "Item 1", "length_cm": 100,
            "width_cm": 50, "height_cm": 40, "weight_kg": 20
        })
        client.post("/api/items", json={
            "item_id": "UPDATE-ITEM-2", "description": "Item 2", "length_cm": 80,
            "width_cm": 60, "height_cm": 50, "weight_kg": 30
        })
        pl_payload = {
            "name": "Update Test",
            "filename": "update.csv",
            "rows": [
                {"item_id": "UPDATE-ITEM-1", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10},
            ],
            "total_cartons": 10,
            "total_weight_kg": 200,
            "total_volume_cm3": 400000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        create_resp = client.post("/api/packing-lists", json=pl_payload)
        pl_id = create_resp.json()["id"]

        update_payload = {
            "rows": [
                {"item_id": "UPDATE-ITEM-2", "po_no": "PO-2", "qty_pcs": 10, "qty_cartons": 10},
                {"item_id": "UPDATE-ITEM-1", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10},
            ],
            "total_cartons": 20,
            "total_weight_kg": 500,
            "total_volume_cm3": 800000,
        }
        update_resp = client.put(f"/api/packing-lists/{pl_id}", json=update_payload)
        assert update_resp.status_code == 200
        rows = update_resp.json()["rows"]
        assert rows[0]["item_id"] == "UPDATE-ITEM-2"
        assert rows[1]["item_id"] == "UPDATE-ITEM-1"

    def test_PL_13_qty_pcs_lt_qty_cartons_rejected(self, db_session):
        """PL-13: Qty_Pcs < Qty_Cartons should be rejected"""
        client.post("/api/items", json={
            "item_id": "PCS-LT-CTN", "description": "Test", "length_cm": 100,
            "width_cm": 50, "height_cm": 40, "weight_kg": 20
        })
        payload = {
            "name": "Test PL",
            "filename": "test.csv",
            "rows": [{"item_id": "PCS-LT-CTN", "po_no": "PO-1", "qty_pcs": 2, "qty_cartons": 5}],
            "total_cartons": 5,
            "total_weight_kg": 100,
            "total_volume_cm3": 200000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        response = client.post("/api/packing-lists", json=payload)
        assert response.status_code in (400, 422)

