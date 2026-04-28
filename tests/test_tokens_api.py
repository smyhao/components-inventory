from __future__ import annotations


class TestListTokens:
    def test_empty_list(self, client):
        resp = client.get("/api/settings/tokens")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []


class TestCreateToken:
    def test_create_success(self, client):
        resp = client.post("/api/settings/tokens", json={"name": "my-token"})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "my-token"
        assert "token" in data
        assert "id" in data

    def test_create_missing_name_error(self, client):
        resp = client.post("/api/settings/tokens", json={})
        assert resp.get_json()["code"] == 1

    def test_create_duplicate_name_error(self, client):
        client.post("/api/settings/tokens", json={"name": "dup"})
        resp = client.post("/api/settings/tokens", json={"name": "dup"})
        assert resp.get_json()["code"] == 1


class TestDeleteToken:
    def test_delete_success(self, client):
        create_resp = client.post("/api/settings/tokens", json={"name": "to-delete"})
        token_id = create_resp.get_json()["data"]["id"]
        resp = client.delete(f"/api/settings/tokens/{token_id}")
        assert resp.status_code == 200

    def test_delete_not_found_error(self, client):
        resp = client.delete("/api/settings/tokens/99999")
        assert resp.get_json()["code"] == 1


class TestAuthMiddleware:
    def test_valid_token_allows_request(self, client, auth_headers):
        resp = client.get("/api/components", headers=auth_headers)
        assert resp.status_code == 200

    def test_invalid_token_returns_401(self, client, repo):
        repo.create_api_token({"name": "real-token"})
        headers = {
            "Authorization": "Bearer invalid-token",
            "X-Inventory-Source": "inventory-cli",
        }
        resp = client.get("/api/components", headers=headers)
        assert resp.status_code == 401

    def test_cli_source_without_token_when_tokens_exist(self, client, repo):
        import app as app_module

        repo.create_api_token({"name": "some-token"})
        app_module.API_TOKEN = "env-token"

        headers = {"X-Inventory-Source": "inventory-cli"}
        resp = client.get("/api/components", headers=headers)
        assert resp.status_code == 401

        app_module.API_TOKEN = ""
