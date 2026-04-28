from __future__ import annotations

import io


class TestBOMImport:
    def test_import_csv_success(self, client):
        csv_content = "名称,数量,封装,值\nResistor,10,0805,10K\nCapacitor,5,0603,100nF\n"
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "bom.csv")}
        resp = client.post("/api/bom/import", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        result = resp.get_json()["data"]
        assert "items" in result
        assert len(result["items"]) == 2

    def test_import_missing_file_error(self, client):
        resp = client.post("/api/bom/import")
        assert resp.get_json()["code"] == 1


class TestBOMConsume:
    def test_consume_success(self, client, sample_component_id):
        resp = client.post(
            "/api/bom/consume",
            json={
                "items": [
                    {
                        "component_id": sample_component_id,
                        "quantity_needed": 10,
                        "matched": {"id": sample_component_id, "name": "Test Component"},
                    },
                ]
            },
        )
        assert resp.status_code == 200
        result = resp.get_json()["data"]
        assert "results" in result

    def test_consume_insufficient_stock_error(self, client, sample_component_id):
        resp = client.post(
            "/api/bom/consume",
            json={
                "items": [
                    {
                        "component_id": sample_component_id,
                        "quantity_needed": 9999,
                        "matched": {"id": sample_component_id, "name": "Test Component"},
                    },
                ]
            },
        )
        assert resp.get_json()["code"] == 1

    def test_consume_empty_items_error(self, client):
        resp = client.post("/api/bom/consume", json={"items": []})
        assert resp.get_json()["code"] == 1


class TestBOMExport:
    def test_export_returns_xlsx(self, client):
        payload = {
            "items": [
                {
                    "designator": "R1",
                    "comment": "10K",
                    "footprint": "0805",
                    "quantity_needed": 10,
                    "match_level": "exact",
                    "matched": {"quantity": 50, "box_name": "Box1", "cell_label": "1-1"},
                },
            ]
        }
        resp = client.post("/api/bom/export", json=payload)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.content_type
