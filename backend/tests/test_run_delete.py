import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Run, Container
from app.core.models import RunStatus

client = TestClient(app)


class TestRunDelete:
    """Tests for DELETE /api/runs/{run_id} endpoint."""

    def test_delete_completed_run_success(self, db_session):
        """Deleting a completed run returns 204 No Content, and run is gone."""
        container = db_session.query(Container).first()
        if not container:
            container = Container(
                container_type=f"TEST-CONT-{uuid.uuid4()}",
                internal_length_cm=1000.0,
                internal_width_cm=200.0,
                internal_height_cm=200.0,
                max_weight_kg=20000.0,
            )
            db_session.add(container)
            db_session.commit()
            db_session.refresh(container)

        test_run_id = f"test-del-{uuid.uuid4()}"
        db_run = Run(
            run_id=test_run_id,
            container_id=container.id,
            packing_list_json='{"rows": []}',
            status=RunStatus.COMPLETED.value,
        )
        db_session.add(db_run)
        db_session.commit()

        # Delete run
        resp = client.delete(f"/api/runs/{test_run_id}")
        assert resp.status_code == 204

        # Confirm 404 on subsequent get
        get_resp = client.get(f"/api/runs/{test_run_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_run_returns_404(self):
        """Deleting a nonexistent run returns 404."""
        resp = client.delete("/api/runs/nonexistent-uuid-12345")
        assert resp.status_code == 404

    def test_delete_running_run_returns_409_conflict(self, db_session):
        """Deleting an in-progress ('running') run is rejected with 409 Conflict."""
        container = db_session.query(Container).first()
        if not container:
            container = Container(
                container_type=f"TEST-CONT-{uuid.uuid4()}",
                internal_length_cm=1000.0,
                internal_width_cm=200.0,
                internal_height_cm=200.0,
                max_weight_kg=20000.0,
            )
            db_session.add(container)
            db_session.commit()
            db_session.refresh(container)

        test_run_id = f"test-running-{uuid.uuid4()}"
        db_run = Run(
            run_id=test_run_id,
            container_id=container.id,
            packing_list_json='{"rows": []}',
            status=RunStatus.RUNNING.value,
        )
        db_session.add(db_run)
        db_session.commit()

        resp = client.delete(f"/api/runs/{test_run_id}")
        assert resp.status_code == 409
        assert "Cannot delete an in-progress run" in resp.json()["detail"]
