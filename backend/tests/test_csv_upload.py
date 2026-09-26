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
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up\n"
            "SKU-TEST-01,Table,120.0,80.0,75.0,25.0,True\n"
            "SKU-TEST-02,Chair,45.0,45.0,90.0,6.5,True\n"
            "SKU-TEST-03,Lamp,30.0,30.0,60.0,3.0,False\n"
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
        assert sku1["weight_kg"] == 25.0

    def test_upload_items_csv_utf8_bom(self, db_session):
        """Verify CSV upload with UTF-8 BOM encoding (common in Excel exports) works correctly."""
        csv_content = (
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up\n"
            "SKU-BOM-01,Sofa,200.0,90.0,85.0,60.0,True\n"
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
            "Item_ID,Description,Length_cm,Width_cm,Height_cm,Weight_kg,This_Way_Up\n"
            "PL-ITEM-01,Test SKU,50.0,40.0,30.0,10.0,True\n"
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

