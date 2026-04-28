from __future__ import annotations


class TestListCabinets:
    def test_empty_list(self, client):
        resp = client.get("/api/cabinets")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_returns_created_cabinet(self, client):
        client.post("/api/cabinets", json={"name": "Cab A"})
        resp = client.get("/api/cabinets")
        assert len(resp.get_json()["data"]) == 1


class TestCreateCabinet:
    def test_create_success(self, client):
        resp = client.post("/api/cabinets", json={"name": "New Cabinet"})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "New Cabinet"
        assert "id" in data

    def test_create_missing_name_error(self, client):
        resp = client.post("/api/cabinets", json={})
        assert resp.get_json()["code"] == 1


class TestGetCabinet:
    def test_get_detail(self, client, sample_cabinet_id):
        resp = client.get(f"/api/cabinets/{sample_cabinet_id}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Test Cabinet"

    def test_not_found_error(self, client):
        resp = client.get("/api/cabinets/99999")
        assert resp.get_json()["code"] == 1


class TestUpdateCabinet:
    def test_update_name(self, client, sample_cabinet_id):
        resp = client.put(
            f"/api/cabinets/{sample_cabinet_id}", json={"name": "Updated"}
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Updated"


class TestDeleteCabinet:
    def test_delete_success(self, client, sample_cabinet_id):
        resp = client.delete(f"/api/cabinets/{sample_cabinet_id}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["id"] == sample_cabinet_id

    def test_delete_with_boxes_error(self, client, sample_cabinet_id):
        client.post(
            "/api/boxes",
            json={"name": "BoxInCabinet", "rows": 2, "cols": 2, "cabinet_id": sample_cabinet_id},
        )
        resp = client.delete(f"/api/cabinets/{sample_cabinet_id}")
        assert resp.get_json()["code"] == 1


class TestUpdateCabinetLayout:
    def test_update_position(self, client, sample_cabinet_id):
        resp = client.put(
            f"/api/cabinets/{sample_cabinet_id}/layout",
            json={"position_x": 100, "position_y": 200},
        )
        assert resp.status_code == 200
