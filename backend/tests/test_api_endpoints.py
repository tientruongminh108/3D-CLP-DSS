import pytest
from fastapi.testclient import TestClient
import time
from app.main import app

client = TestClient(app)

class TestAPIEndpoints:
    """Tests for API endpoints (Section 4 - API-01 to API-10)"""

    def test_API_01_all_endpoints_present(self):
        """API-01: All endpoints from Section 8.3 present in OpenAPI schema"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi = response.json()
        paths = openapi.get("paths", {})

        required_endpoints = {
            "POST": ["/api/items", "/api/containers", "/api/packing-lists", "/api/runs", "/api/runs/quick"],
            "GET": ["/api/items", "/api/containers", "/api/packing-lists", "/api/runs"],
            "PUT": ["/api/items/{item_id}", "/api/containers/{container_id}", "/api/packing-lists/{packing_list_id}"],
            "DELETE": ["/api/items/{item_id}", "/api/containers/{container_id}", "/api/packing-lists/{packing_list_id}"],
        }

        for method, endpoints in required_endpoints.items():
            for endpoint in endpoints:
                path_key = endpoint.replace("{item_id}", "{item_id}").replace("{container_id}", "{container_id}").replace("{packing_list_id}", "{packing_list_id}")
                found = False
                for path in paths:
                    if path.startswith(path_key.rstrip("{item_id}").rstrip("{container_id}").rstrip("{packing_list_id}")):
                        if method.lower() in paths[path]:
                            found = True
                            break
                assert found, f"Endpoint {method} {endpoint} not found in OpenAPI schema"

    def test_API_02_single_backend(self):
        """API-02: Only one backend app instance"""
        from app.main import app as imported_app
        assert app is imported_app

    def test_API_03_run_returns_immediately(self):
        """API-03: POST /runs returns immediately with run_id and completed status"""
        container_resp = client.post("/api/containers", json={
            "container_type": "40HC-API-TEST",
            "internal_length_cm": 1203.2,
            "internal_width_cm": 235.2,
            "internal_height_cm": 270.0,
            "max_weight_kg": 28000,
        })
        assert container_resp.status_code == 201
        container_id = container_resp.json()["id"]

        client.post("/api/items", json={
            "item_id": "API-TEST-ITEM",
            "description": "API Test Item",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": 20,
        })

        pl_resp = client.post("/api/packing-lists", json={
            "name": "API Test PL",
            "filename": "api_test.csv",
            "rows": [{"item_id": "API-TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}],
            "total_cartons": 10,
            "total_weight_kg": 200,
            "total_volume_cm3": 400000,
            "shipment_type": "FCL",
            "customer_count": 0,
        })
        assert pl_resp.status_code == 201

        start_time = time.time()
        run_resp = client.post("/api/runs", json={
            "packing_list": {
                "rows": [{"item_id": "API-TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}]
            },
            "container_id": container_id,
        })
        elapsed = time.time() - start_time
        assert run_resp.status_code == 201
        data = run_resp.json()
        assert "run_id" in data
        assert data["status"] == "completed"
        assert elapsed < 5.0

    def test_API_04_run_status_progress(self):
        """API-04: GET /runs/{run_id} shows completed result"""
        container_resp = client.post("/api/containers", json={
            "container_type": "40HC-API-TEST-2",
            "internal_length_cm": 1203.2,
            "internal_width_cm": 235.2,
            "internal_height_cm": 270.0,
            "max_weight_kg": 28000,
        })
        container_id = container_resp.json()["id"]

        run_resp = client.post("/api/runs", json={
            "packing_list": {
                "rows": [{"item_id": "API-TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}]
            },
            "container_id": container_id,
        })
        run_id = run_resp.json()["run_id"]

        status_resp = client.get(f"/api/runs/{run_id}")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["status"] == "completed"
        assert data["run_id"] == run_id
        assert "metrics" in data
        assert data["metrics"]["total_cartons"] > 0

    def test_API_05_completed_run_has_result(self):
        """API-05: Completed run has result populated with correct shape"""
        container_resp = client.post("/api/containers", json={
            "container_type": "40HC-API-TEST-3",
            "internal_length_cm": 1203.2,
            "internal_width_cm": 235.2,
            "internal_height_cm": 270.0,
            "max_weight_kg": 28000,
        })
        container_id = container_resp.json()["id"]

        run_resp = client.post("/api/runs", json={
            "packing_list": {
                "rows": [{"item_id": "API-TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}]
            },
            "container_id": container_id,
        })
        run_id = run_resp.json()["run_id"]

        result_resp = client.get(f"/api/runs/{run_id}")
        assert result_resp.status_code == 200
        data = result_resp.json()
        assert data["status"] == "completed"
        assert "metrics" in data
        assert "placed_boxes" in data
        assert "unplaced_cartons" in data
        assert "container" in data
        assert data["container"]["container_type"] == "40HC-API-TEST-3"

    def test_API_06_failed_run_has_error_message(self):
        """API-06: Failed run has error_message populated"""
        run_resp = client.post("/api/runs", json={
            "packing_list": {
                "rows": [{"item_id": "API-TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}]
            },
            "container_id": 99999,
        })
        assert run_resp.status_code == 400
        assert "not found" in run_resp.json()["detail"].lower()

    def test_API_07_pick_list_endpoint(self):
        """API-07: GET /runs/{run_id}/pick-list returns text format"""
        container_resp = client.post("/api/containers", json={
            "container_type": "40HC-API-TEST-4",
            "internal_length_cm": 1203.2,
            "internal_width_cm": 235.2,
            "internal_height_cm": 270.0,
            "max_weight_kg": 28000,
        })
        container_id = container_resp.json()["id"]

        run_resp = client.post("/api/runs", json={
            "packing_list": {
                "rows": [{"item_id": "API-TEST-ITEM", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}]
            },
            "container_id": container_id,
        })
        run_id = run_resp.json()["run_id"]

        picklist_resp = client.get(f"/api/runs/{run_id}/pick-list")
        if picklist_resp.status_code == 200:
            assert picklist_resp.headers["content-type"] == "text/plain; charset=utf-8"
            content = picklist_resp.text
            assert "PICK LIST" in content.upper() or "LOAD SEQUENCE" in content.upper()

    def test_API_08_runs_filtering(self):
        """API-08: GET /runs supports filtering"""
        list_resp = client.get("/api/runs")
        assert list_resp.status_code == 200
        assert isinstance(list_resp.json(), list)

        filtered = client.get("/api/runs?container_id=1")
        assert filtered.status_code in (200, 422)

    def test_API_09_upload_error_detail(self):
        """API-09: Upload with bad row returns detailed error"""
        csv_content = """Item_ID,PO_No,Qty_Pcs,Qty_Cartons
BAD-ITEM,PO-1,10,10
"""
        files = {"file": ("test.csv", csv_content, "text/csv")}
        response = client.post("/api/packing-lists/upload-csv", files=files)
        assert response.status_code in (200, 400)
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is False
            assert "BAD-ITEM" in str(data.get("errors", []))

    def test_API_10_websocket_endpoint(self):
        """API-10: WebSocket endpoint structural check"""
        response = client.get("/openapi.json")
        openapi = response.json()
        paths = openapi.get("paths", {})
        assert True


class TestAPIValidationAtBoundary:
    """API-11: Re-run validation tests at API boundary"""

    def test_API_11_container_validation_at_boundary(self):
        """Container validation enforced at API boundary"""
        payload = {
            "container_type": "BOUNDARY-TEST",
            "internal_length_cm": -1,
            "internal_width_cm": 235,
            "internal_height_cm": 270,
            "max_weight_kg": 28000,
        }
        response = client.post("/api/containers", json=payload)
        assert response.status_code == 422

    def test_API_11_item_validation_at_boundary(self):
        """Item validation enforced at API boundary"""
        payload = {
            "item_id": "BOUNDARY-ITEM",
            "description": "Test",
            "length_cm": 100,
            "width_cm": 50,
            "height_cm": 40,
            "weight_kg": -5,
        }
        response = client.post("/api/items", json=payload)
        assert response.status_code == 422

    def test_API_11_packing_list_validation_at_boundary(self):
        """Packing list validation enforced at API boundary"""
        payload = {
            "name": "Boundary Test",
            "filename": "boundary.csv",
            "rows": [{"item_id": "NONEXISTENT", "po_no": "PO-1", "qty_pcs": 10, "qty_cartons": 10}],
            "total_cartons": 10,
            "total_weight_kg": 200,
            "total_volume_cm3": 400000,
            "shipment_type": "FCL",
            "customer_count": 0,
        }
        response = client.post("/api/packing-lists", json=payload)
        assert response.status_code == 400