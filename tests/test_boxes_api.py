from __future__ import annotations


class TestListBoxes:
    def test_empty_list(self, client):
        resp = client.get("/api/boxes")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_returns_created_box(self, client):
        client.post("/api/boxes", json={"name": "Box1", "rows": 2, "cols": 2})
        resp = client.get("/api/boxes")
        assert len(resp.get_json()["data"]) == 1


class TestCreateBox:
    def test_create_success(self, client):
        resp = client.post("/api/boxes", json={"name": "My Box", "rows": 3, "cols": 4})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "My Box"
        assert data["rows"] == 3
        assert data["cols"] == 4

    def test_create_missing_name_error(self, client):
        resp = client.post("/api/boxes", json={"rows": 2, "cols": 2})
        assert resp.get_json()["code"] == 1

    def test_create_with_cabinet(self, client, sample_cabinet_id):
        resp = client.post(
            "/api/boxes",
            json={"name": "CabBox", "rows": 2, "cols": 2, "cabinet_id": sample_cabinet_id},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["cabinet_id"] == sample_cabinet_id


class TestGetBox:
    def test_get_detail(self, client, sample_box_id):
        resp = client.get(f"/api/boxes/{sample_box_id}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "Test Box"
        assert "total_slots" in data

    def test_not_found_error(self, client):
        resp = client.get("/api/boxes/99999")
        assert resp.get_json()["code"] == 1


class TestUpdateBox:
    def test_update_name(self, client, sample_box_id):
        resp = client.put(
            f"/api/boxes/{sample_box_id}", json={"name": "Renamed Box"}
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Renamed Box"

    def test_update_resize(self, client, sample_box_id):
        resp = client.put(
            f"/api/boxes/{sample_box_id}", json={"rows": 5, "cols": 5}
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["rows"] == 5


class TestDeleteBox:
    def test_delete_success(self, client):
        resp = client.post("/api/boxes", json={"name": "ToDelete", "rows": 1, "cols": 1})
        box_id = resp.get_json()["data"]["id"]
        resp = client.delete(f"/api/boxes/{box_id}")
        assert resp.status_code == 200

    def test_delete_with_components_error(self, client, sample_box_id):
        client.post(
            "/api/components",
            json={"name": "CompInBox", "quantity": 1, "box_id": sample_box_id},
        )
        resp = client.delete(f"/api/boxes/{sample_box_id}")
        assert resp.get_json()["code"] == 1


class TestUpdateBoxLayout:
    def test_update_position(self, client, sample_box_id):
        resp = client.put(
            f"/api/boxes/{sample_box_id}/layout",
            json={"position_x": 50, "position_y": 75},
        )
        assert resp.status_code == 200


class TestGetBoxGrid:
    def test_grid_returns_cells(self, client, sample_box_id):
        resp = client.get(f"/api/boxes/{sample_box_id}/grid")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "cells" in data
        assert len(data["cells"]) == 3  # 3 rows

    def test_grid_has_rows_cols(self, client, sample_box_id):
        resp = client.get(f"/api/boxes/{sample_box_id}/grid")
        data = resp.get_json()["data"]
        assert data["rows"] == 3
        assert data["cols"] == 3
