from __future__ import annotations

import io


class TestListComponents:
    def test_empty_list(self, client):
        resp = client.get("/api/components")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["items"] == []
        assert "total" in data

    def test_pagination(self, client):
        for i in range(5):
            client.post("/api/components", json={"name": f"Comp{i}", "quantity": 10})
        resp = client.get("/api/components?page=1&page_size=2")
        data = resp.get_json()["data"]
        assert len(data["items"]) == 2
        assert data["total"] == 5

    def test_keyword_filter(self, client):
        client.post("/api/components", json={"name": "Resistor 10K", "quantity": 1})
        client.post("/api/components", json={"name": "Capacitor 100uF", "quantity": 1})
        resp = client.get("/api/components?keyword=Resistor")
        items = resp.get_json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Resistor 10K"

    def test_category_filter(self, client, sample_category_id):
        client.post(
            "/api/components",
            json={"name": "CatComp", "quantity": 1, "category_id": sample_category_id},
        )
        resp = client.get(f"/api/components?category_id={sample_category_id}")
        assert len(resp.get_json()["data"]["items"]) == 1

    def test_box_filter(self, client, sample_box_id):
        client.post(
            "/api/components",
            json={"name": "BoxComp", "quantity": 1, "box_id": sample_box_id},
        )
        resp = client.get(f"/api/components?box_id={sample_box_id}")
        assert len(resp.get_json()["data"]["items"]) == 1

    def test_low_stock_filter(self, client):
        client.post(
            "/api/components",
            json={"name": "LowComp", "quantity": 2, "min_stock": 10},
        )
        client.post(
            "/api/components",
            json={"name": "OkComp", "quantity": 100, "min_stock": 10},
        )
        resp = client.get("/api/components?low_stock=1")
        items = resp.get_json()["data"]["items"]
        assert any(c["name"] == "LowComp" for c in items)
        assert not any(c["name"] == "OkComp" for c in items)


class TestCreateComponent:
    def test_create_minimal(self, client):
        resp = client.post("/api/components", json={"name": "Resistor", "quantity": 50})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "id" in data
        assert data["quantity"] == 50

    def test_create_with_all_fields(self, client, sample_category_id, sample_box_id):
        resp = client.post(
            "/api/components",
            json={
                "name": "Full Comp",
                "quantity": 100,
                "category_id": sample_category_id,
                "model": "LM7805",
                "package": "TO-220",
                "nominal_value": "5V",
                "voltage_rating": "35V",
                "description": "Voltage regulator",
                "min_stock": 10,
                "box_id": sample_box_id,
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "id" in data
        # verify by fetching detail
        detail = client.get(f"/api/components/{data['id']}")
        assert detail.get_json()["data"]["model"] == "LM7805"

    def test_create_with_tags(self, client):
        resp = client.post(
            "/api/components",
            json={"name": "Tagged", "quantity": 1, "tags": ["SMD", "0805"]},
        )
        assert resp.status_code == 200
        comp_id = resp.get_json()["data"]["id"]
        detail = client.get(f"/api/components/{comp_id}")
        assert "SMD" in detail.get_json()["data"]["tags"]

    def test_create_missing_name_error(self, client):
        resp = client.post("/api/components", json={"quantity": 10})
        assert resp.get_json()["code"] == 1


class TestGetComponent:
    def test_get_detail(self, client, sample_component_id):
        resp = client.get(f"/api/components/{sample_component_id}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "Test Component"
        assert "images" in data
        assert "documents" in data
        assert "stock_logs" in data

    def test_not_found_error(self, client):
        resp = client.get("/api/components/99999")
        assert resp.get_json()["code"] == 1


class TestUpdateComponent:
    def test_update_name(self, client, sample_component_id):
        resp = client.put(
            f"/api/components/{sample_component_id}", json={"name": "Updated Comp"}
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Updated Comp"

    def test_update_with_tags(self, client, sample_component_id):
        resp = client.put(
            f"/api/components/{sample_component_id}",
            json={"tags": ["new-tag"]},
        )
        assert resp.status_code == 200
        assert "new-tag" in resp.get_json()["data"]["tags"]


class TestDeleteComponent:
    def test_delete_success(self, client, sample_component_id):
        resp = client.delete(f"/api/components/{sample_component_id}")
        assert resp.status_code == 200

    def test_delete_not_found_error(self, client):
        resp = client.delete("/api/components/99999")
        assert resp.get_json()["code"] == 1


class TestComponentQR:
    def test_qr_svg_returns_svg(self, client, sample_component_id):
        resp = client.get(f"/api/components/{sample_component_id}/qr.svg")
        assert resp.status_code == 200
        assert "svg" in resp.content_type

    def test_qr_svg_not_found(self, client):
        resp = client.get("/api/components/99999/qr.svg")
        assert resp.get_json()["code"] == 1


class TestImportComponents:
    def test_import_csv(self, client):
        csv_content = "name,quantity,model\nImported1,50,ML1\nImported2,30,ML2\n"
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "test.csv")}
        resp = client.post("/api/components/import", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        result = resp.get_json()["data"]
        assert result["success"] == 2

    def test_import_missing_file_error(self, client):
        resp = client.post("/api/components/import")
        assert resp.get_json()["code"] == 1


class TestExportComponents:
    def test_export_returns_xlsx(self, client, sample_component_id):
        resp = client.get("/api/components/export")
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.content_type
