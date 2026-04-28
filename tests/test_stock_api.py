from __future__ import annotations


class TestStockIn:
    def test_stock_in_success(self, client, sample_component_id):
        resp = client.post(
            "/api/stock/in",
            json={"component_id": sample_component_id, "quantity": 50, "reason": "restock"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["quantity_after"] == 150

    def test_stock_in_missing_component_error(self, client):
        resp = client.post(
            "/api/stock/in",
            json={"component_id": 99999, "quantity": 10},
        )
        assert resp.get_json()["code"] == 1

    def test_stock_in_invalid_quantity_error(self, client, sample_component_id):
        resp = client.post(
            "/api/stock/in",
            json={"component_id": sample_component_id, "quantity": 0},
        )
        assert resp.get_json()["code"] == 1


class TestStockOut:
    def test_stock_out_success(self, client, sample_component_id):
        resp = client.post(
            "/api/stock/out",
            json={"component_id": sample_component_id, "quantity": 30, "reason": "usage"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["quantity_after"] == 70

    def test_stock_out_insufficient_error(self, client, sample_component_id):
        resp = client.post(
            "/api/stock/out",
            json={"component_id": sample_component_id, "quantity": 999},
        )
        assert resp.get_json()["code"] == 1

    def test_stock_out_missing_component_error(self, client):
        resp = client.post(
            "/api/stock/out",
            json={"component_id": 99999, "quantity": 10},
        )
        assert resp.get_json()["code"] == 1


class TestStockLogs:
    def test_logs_returns_history(self, client, sample_component_id):
        client.post(
            "/api/stock/in",
            json={"component_id": sample_component_id, "quantity": 10},
        )
        resp = client.get(f"/api/stock/logs/{sample_component_id}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["items"]) >= 1

    def test_logs_pagination(self, client, sample_component_id):
        for i in range(5):
            client.post(
                "/api/stock/in",
                json={"component_id": sample_component_id, "quantity": 1},
            )
        resp = client.get(f"/api/stock/logs/{sample_component_id}?page=1&page_size=2")
        data = resp.get_json()["data"]
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    def test_logs_component_zero_returns_all(self, client, sample_component_id):
        client.post(
            "/api/stock/in",
            json={"component_id": sample_component_id, "quantity": 5},
        )
        resp = client.get("/api/stock/logs/0")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["total"] >= 1
