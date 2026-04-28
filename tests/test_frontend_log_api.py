from __future__ import annotations


class TestFrontendLog:
    def test_log_success(self, client):
        resp = client.post(
            "/api/frontend/log",
            json={"logs": [{"type": "INFO", "detail": "test log"}]},
        )
        assert resp.status_code == 200

    def test_empty_logs_allowed(self, client):
        resp = client.post("/api/frontend/log", json={"logs": []})
        # empty list is accepted but writes nothing
        assert resp.status_code == 200

    def test_too_many_logs_error(self, client):
        logs = [{"level": "info", "message": f"msg{i}"} for i in range(101)]
        resp = client.post("/api/frontend/log", json={"logs": logs})
        assert resp.get_json()["code"] == 1

    def test_non_list_logs_error(self, client):
        resp = client.post("/api/frontend/log", json={"logs": "not a list"})
        assert resp.get_json()["code"] == 1
