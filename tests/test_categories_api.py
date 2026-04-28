from __future__ import annotations


class TestListCategories:
    def test_returns_default_categories(self, client):
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert len(data["data"]) >= 12

    def test_category_has_required_fields(self, client):
        resp = client.get("/api/categories")
        cat = resp.get_json()["data"][0]
        assert "id" in cat
        assert "name" in cat


class TestCreateCategory:
    def test_create_success(self, client):
        resp = client.post("/api/categories", json={"name": "New Category"})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "New Category"
        assert "id" in data

    def test_create_with_parent(self, client):
        parent = client.post("/api/categories", json={"name": "Parent Cat"})
        parent_id = parent.get_json()["data"]["id"]
        resp = client.post(
            "/api/categories", json={"name": "Child Cat", "parent_id": parent_id}
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["parent_id"] == parent_id

    def test_create_missing_name_returns_error(self, client):
        resp = client.post("/api/categories", json={})
        assert resp.get_json()["code"] == 1
