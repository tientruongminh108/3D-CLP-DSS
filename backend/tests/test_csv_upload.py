import pytest
from io import BytesIO
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Item as DBItem

client = TestClient(app)


class TestCSVUploadEndpoints:
    """Comprehensive tests for CSV upload endpoints across Items, Containers, and Packing Lists."""

    def test_upload_items_csv_success(self, db_session):
        """Verify successful CSV upload for Item Master and proper listing afterwards."""
        csv_content = (
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up,Stacking_Group,Max_Load_Bearing_kg\n"
            "SKU-TEST-01,Table,120.0,80.0,75.0,25.0,True,1,150.0\n"
            "SKU-TEST-02,Chair,45.0,45.0,90.0,6.5,True,2,50.0\n"
            "SKU-TEST-03,Lamp,30.0,30.0,60.0,3.0,False,2,\n"
        )
        files = {"file": ("items.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")}
        response = client.post("/api/items/upload-csv", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] == 3
        assert data["errors"] == []

        # Verify GET /api/items returns 200 and serializes correctly
        list_resp = client.get("/api/items")
        assert list_resp.status_code == 200
        items = list_resp.json()
        item_ids = [i["item_id"] for i in items]
        assert "SKU-TEST-01" in item_ids
        assert "SKU-TEST-02" in item_ids
        assert "SKU-TEST-03" in item_ids

        sku1 = next(i for i in items if i["item_id"] == "SKU-TEST-01")
        assert sku1["stacking_group"] == 1
        assert sku1["max_load_bearing_kg"] == 150.0

        sku3 = next(i for i in items if i["item_id"] == "SKU-TEST-03")
        assert sku3["stacking_group"] == 2
        assert sku3["max_load_bearing_kg"] is None

    def test_upload_items_csv_utf8_bom(self, db_session):
        """Verify CSV upload with UTF-8 BOM encoding (common in Excel exports) works correctly."""
        csv_content = (
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up,Stacking_Group\n"
            "SKU-BOM-01,Sofa,200.0,90.0,85.0,60.0,True,1\n"
        )
        bom_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        files = {"file": ("items_bom.csv", BytesIO(bom_bytes), "text/csv")}
        response = client.post("/api/items/upload-csv", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] == 1

        get_resp = client.get("/api/items/SKU-BOM-01")
        assert get_resp.status_code == 200
        assert get_resp.json()["item_id"] == "SKU-BOM-01"

    def test_upload_items_csv_string_stacking_groups(self, db_session):
        """Verify that textual stacking groups ('STURDY', 'FRAGILE') are accepted."""
        csv_content = (
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up,Stacking_Group\n"
            "SKU-STR-01,Desk,100.0,60.0,75.0,20.0,True,STURDY\n"
            "SKU-STR-02,Vase,20.0,20.0,40.0,2.0,True,FRAGILE\n"
        )
        files = {"file": ("items_str.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")}
        response = client.post("/api/items/upload-csv", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] == 2

        resp1 = client.get("/api/items/SKU-STR-01")
        assert resp1.json()["stacking_group"] == 1

        resp2 = client.get("/api/items/SKU-STR-02")
        assert resp2.json()["stacking_group"] == 2

    def test_upload_items_csv_invalid_stacking_group_reports_error(self, db_session):
        """Verify invalid stacking group values are caught, reported in errors, and not saved."""
        csv_content = (
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up,Stacking_Group\n"
            "SKU-INVALID-5,Item 5,100.0,50.0,40.0,10.0,True,5\n"
            "SKU-VALID-1,Item 1,100.0,50.0,40.0,10.0,True,1\n"
        )
        files = {"file": ("items_invalid.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")}
        response = client.post("/api/items/upload-csv", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 1
        assert len(data["errors"]) == 1
        assert "Stacking group must be 1 (STURDY) or 2 (FRAGILE)" in data["errors"][0]

        # Verify invalid item was NOT created
        check_invalid = client.get("/api/items/SKU-INVALID-5")
        assert check_invalid.status_code == 404

    def test_upload_items_csv_update_existing(self, db_session):
        """Verify updating existing items through CSV upload."""
        csv1 = (
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg\n"
            "SKU-UPDATE-01,Original Description,100.0,50.0,40.0,10.0\n"
        )
        files1 = {"file": ("items.csv", BytesIO(csv1.encode("utf-8")), "text/csv")}
        resp1 = client.post("/api/items/upload-csv", files=files1)
        assert resp1.json()["created"] == 1

        csv2 = (
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg\n"
            "SKU-UPDATE-01,Updated Description,110.0,55.0,45.0,12.0\n"
        )
        files2 = {"file": ("items.csv", BytesIO(csv2.encode("utf-8")), "text/csv")}
        resp2 = client.post("/api/items/upload-csv", files=files2)
        assert resp2.json()["created"] == 0
        assert resp2.json()["updated"] == 1

        updated_item = client.get("/api/items/SKU-UPDATE-01").json()
        assert updated_item["description"] == "Updated Description"
        assert updated_item["length_cm"] == 110.0

    def test_upload_containers_csv_success_and_bom(self, db_session):
        """Verify container spec CSV upload with BOM support."""
        csv_content = (
            "Container_Type,Internal_Length_cm,Internal_Width_cm,Internal_Height_cm,Max_Weight_kg\n"
            "20FT-TEST,589.8,235.2,239.3,28000\n"
            "40FT-TEST,1203.2,235.2,239.3,28000\n"
        )
        bom_bytes = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        files = {"file": ("containers.csv", BytesIO(bom_bytes), "text/csv")}
        response = client.post("/api/containers/upload-csv", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created"] == 2

        list_resp = client.get("/api/containers")
        assert list_resp.status_code == 200
        types = [c["container_type"] for c in list_resp.json()]
        assert "20FT-TEST" in types
        assert "40FT-TEST" in types

    def test_upload_and_save_packing_list_csv(self, db_session):
        """Verify packing list upload, validation against items, and DB save."""
        # Ensure item exists first
        item_csv = (
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up,Stacking_Group\n"
            "PL-ITEM-01,Test SKU,50.0,40.0,30.0,10.0,True,1\n"
        )
        client.post("/api/items/upload-csv", files={"file": ("items.csv", BytesIO(item_csv.encode("utf-8")), "text/csv")})

        # Ensure container exists
        cont_csv = (
            "Container_Type,Internal_Length_cm,Internal_Width_cm,Internal_Height_cm,Max_Weight_kg\n"
            "PL-CONT-01,1200.0,235.0,270.0,28000\n"
        )
        client.post("/api/containers/upload-csv", files={"file": ("containers.csv", BytesIO(cont_csv.encode("utf-8")), "text/csv")})

        pl_csv = (
            "Item_ID,PO_No,Customer_Code,Description,Qty_Pcs,Qty_Cartons\n"
            "PL-ITEM-01,PO-999,CUST-A,Test SKU,10,10\n"
        )
        bom_bytes = b"\xef\xbb\xbf" + pl_csv.encode("utf-8")
        files = {"file": ("orders.csv", BytesIO(bom_bytes), "text/csv")}
        response = client.post("/api/packing-lists/upload-csv-and-save", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rows_parsed"] == 1
        assert data["preview"]["total_cartons"] == 10

    def test_item_response_model_coercion_prevents_500(self):
        """Verify that corrupt legacy stacking_group values (e.g. 5) are safely coerced to STURDY rather than returning 500."""
        from app.core.models import Item as PydanticItem, StackingGroup
        from datetime import datetime

        raw_data = {
            "id": 999,
            "item_id": "LEGACY-CORRUPT-ROW",
            "description": "Corrupt Item",
            "length_cm": 100.0,
            "width_cm": 50.0,
            "height_cm": 40.0,
            "weight_kg": 20.0,
            "this_way_up": True,
            "stacking_group": 5,  # Legacy or corrupt value
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # Should validate without raising ValueError / ResponseValidationError
        item = PydanticItem.model_validate(raw_data)
        assert item.stacking_group == StackingGroup.STURDY
