from __future__ import annotations


class TestStats:
    def test_empty_database(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["total_components"] == 0
        assert data["total_quantity"] == 0

    def test_with_components(self, client, sample_component_id):
        resp = client.get("/api/stats")
        data = resp.get_json()["data"]
        assert data["total_components"] >= 1
        assert data["total_quantity"] >= 100

    def test_with_low_stock_items(self, client):
        client.post(
            "/api/components",
            json={"name": "Low1", "quantity": 1, "min_stock": 10},
        )
        resp = client.get("/api/stats")
        data = resp.get_json()["data"]
        assert data["low_stock_count"] >= 1

    def test_category_stats_populated(self, client, sample_category_id):
        client.post(
            "/api/components",
            json={"name": "CatComp", "quantity": 10, "category_id": sample_category_id},
        )
        resp = client.get("/api/stats")
        data = resp.get_json()["data"]
        assert len(data["category_stats"]) >= 1
