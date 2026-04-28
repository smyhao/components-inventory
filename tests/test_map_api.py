from __future__ import annotations

from tests.conftest import make_test_image


class TestMapData:
    def test_returns_boxes_and_cabinets(self, client, sample_box_id, sample_cabinet_id):
        resp = client.get("/api/map")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "boxes" in data
        assert "cabinets" in data


class TestMapBackground:
    def test_upload_success(self, client, tmp_dirs):
        img_buf = make_test_image("bg.png")
        data = {"file": (img_buf, "bg.png")}
        resp = client.post("/api/map/background", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert "url" in resp.get_json()["data"]

    def test_upload_invalid_extension_error(self, client):
        import io

        buf = io.BytesIO(b"not image")
        buf.name = "bg.exe"
        data = {"file": (buf, "bg.exe")}
        resp = client.post("/api/map/background", data=data, content_type="multipart/form-data")
        assert resp.get_json()["code"] == 1

    def test_upload_missing_file_error(self, client):
        resp = client.post("/api/map/background")
        assert resp.get_json()["code"] == 1

    def test_delete_success(self, client, tmp_dirs):
        img_buf = make_test_image("bg.png")
        data = {"file": (img_buf, "bg.png")}
        client.post("/api/map/background", data=data, content_type="multipart/form-data")

        resp = client.delete("/api/map/background")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["deleted"] is True

    def test_delete_when_none_exists(self, client):
        resp = client.delete("/api/map/background")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["deleted"] is False


class TestMapSearch:
    def test_search_returns_matching_components(self, client, sample_box_id):
        # create a component placed in the box
        resp = client.post(
            "/api/components",
            json={"name": "MapResistor", "quantity": 10, "box_id": sample_box_id},
        )
        comp_id = resp.get_json()["data"]["id"]
        # place it in a compartment
        grid_resp = client.get(f"/api/boxes/{sample_box_id}/grid")
        cells = grid_resp.get_json()["data"]["cells"]
        compartment_id = cells[0][0]["id"]
        client.put(f"/api/components/{comp_id}", json={"compartment_id": compartment_id})

        resp = client.post("/api/map/search", json={"keyword": "MapResistor"})
        assert resp.status_code == 200
        results = resp.get_json()["data"]["results"]
        assert len(results) >= 1

    def test_search_empty_keyword(self, client):
        resp = client.post("/api/map/search", json={"keyword": ""})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["results"] == []
